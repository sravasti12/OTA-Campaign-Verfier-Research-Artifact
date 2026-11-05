"""Verified SQLite backup/restore, explicit migration, and non-destructive retention."""
import argparse
from contextlib import contextmanager
from collections.abc import Iterator
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any
from langgraph.checkpoint.sqlite import SqliteSaver
from ..llm.evidence import canonical_json, content_hash
from ..llm.models import CallRecord
from ..workflow_models import ReviewDecision, ReviewSnapshot, WorkflowInput, snapshot_hash
from .locks import execution_lock
from .models import PersistentBundle, VersionManifest
from .recipes import ClientRecipe
from .schema import REQUIRED_V2, SCHEMA_V2
from .store import StorageError, StorageVersionError, utc_now


@contextmanager
def readonly(path: Path) -> Iterator[sqlite3.Connection]:
    """Open an existing database without creating or modifying its contents."""
    connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


def verify_database(path: Path) -> dict[str, Any]:
    """Check SQLite, hashes, decisions, and published checkpoint evidence read-only."""
    with readonly(path) as connection:
        if [row[0] for row in connection.execute('PRAGMA integrity_check')] != ['ok']:
            raise StorageError('Database integrity check failed')
        if connection.execute('PRAGMA foreign_key_check').fetchall():
            raise StorageError('Database foreign-key check failed')
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required = {'ota_meta', 'ota_runs', 'ota_revisions', 'ota_decisions', 'ota_receipts'}
        if not required <= tables:
            raise StorageVersionError('Not a complete OTA workspace')
        version = connection.execute('SELECT schema_version FROM ota_meta WHERE id=1').fetchone()[0]
        if version not in (1, 2) or version == 2 and not REQUIRED_V2 <= tables:
            raise StorageVersionError('Unsupported or incomplete operational schema')
        saver = SqliteSaver(connection)
        # Tables are validated before decoding; avoid saver.setup mutating this
        # read-only connection. get_tuple only reads checkpoint records.
        saver.is_setup = True
        revisions = connection.execute('SELECT * FROM ota_revisions ORDER BY run_id,revision').fetchall()
        for row in revisions:
            for raw, digest in (('input_json', 'input_hash'), ('recipe_json', 'recipe_hash'), ('versions_json', 'versions_hash')):
                if content_hash(row[raw]) != row[digest]:
                    raise StorageError('Revision content hash mismatch')
            incoming = WorkflowInput.model_validate_json(row['input_json'])
            ClientRecipe.model_validate_json(row['recipe_json'])
            VersionManifest.model_validate_json(row['versions_json'])
            if row['thread_id'] != f"{row['run_id']}:{row['revision']}" or row['campaign_id'] != incoming.request.campaign.id:
                raise StorageError('Revision thread/campaign identity mismatch')
            if row['status'] != 'ready':
                receipt = connection.execute('SELECT 1 FROM ota_receipts WHERE thread_id=? LIMIT 1', (row['thread_id'],)).fetchone()
                checkpoint = saver.get_tuple({'configurable': {'thread_id': row['thread_id']}}) if {'checkpoints', 'writes'} <= tables else None
                if checkpoint is None:
                    if receipt or json.loads(row['completed_nodes_json']):
                        raise StorageError('Interrupted checkpoint evidence is missing')
                else:
                    values = checkpoint.checkpoint['channel_values']
                    if (values.get('input') != json.loads(row['input_json']) or values.get('run_id') != row['run_id']
                            or values.get('revision') != row['revision']):
                        raise StorageError('Interrupted checkpoint differs from revision identity')
            if row['status'] == 'ready':
                if not {'checkpoints', 'writes'} <= tables:
                    raise StorageError('Published checkpoint tables are missing')
                snapshot = ReviewSnapshot.model_validate_json(row['snapshot_json'])
                if snapshot.artifacts.input != incoming or snapshot_hash(row['run_id'], row['revision'], snapshot) != row['snapshot_hash']:
                    raise StorageError('Published snapshot differs from revision identity')
                checkpoint = saver.get_tuple({'configurable': {'thread_id': row['thread_id']}})
                if checkpoint is None or checkpoint.checkpoint['channel_values'].get('snapshot') != snapshot.model_dump(mode='json'):
                    raise StorageError('Published checkpoint evidence is missing or changed')
        indexed = {(row['run_id'], row['revision']): row for row in revisions}
        for run in connection.execute('SELECT * FROM ota_runs'):
            if (run['run_id'], run['current_revision']) not in indexed:
                raise StorageError('Run registry points to a missing revision')
        for row in connection.execute('SELECT * FROM ota_decisions'):
            decision = ReviewDecision.model_validate_json(row['decision_json'])
            revision = indexed[(row['run_id'], row['revision'])]
            if (decision.submission.model_dump_json() != row['submission_json']
                    or decision.submission.run_id != row['run_id'] or decision.submission.revision != row['revision']
                    or decision.submission.idempotency_key != row['idempotency_key']
                    or decision.submission.snapshot_hash != revision['snapshot_hash']):
                raise StorageError('Decision identity/hash mismatch')
            from ..workflow_models import approval_eligible
            if decision.submission.action == 'approve' and not approval_eligible(ReviewSnapshot.model_validate_json(revision['snapshot_json'])):
                raise StorageError('Stored approval covers nonpassing evidence')
        for row in connection.execute('SELECT * FROM ota_receipts'):
            if row['call_json'] is not None:
                if content_hash(row['call_json']) != row['call_hash']:
                    raise StorageError('Model receipt hash mismatch')
                CallRecord.model_validate_json(row['call_json'])
        if version == 2:
            for row in connection.execute('SELECT a.*, d.decision_json FROM ota_review_auth a JOIN ota_decisions d USING(run_id,revision)'):
                decision = ReviewDecision.model_validate_json(row['decision_json'])
                if decision.submission.reviewer != row['identity_json'] or decision.recorded_at_utc != row['recorded_at']:
                    raise StorageError('Authenticated review provenance differs from decision')
                identity = json.loads(row['identity_json'])
                roles = json.loads(row['roles_json'])
                if set(identity) != {'issuer', 'subject'} or not all(isinstance(value, str) and value for value in identity.values()) or not set(roles) & {'admin', 'reviewer'}:
                    raise StorageError('Invalid authenticated review provenance')
        return {'storage_schema': version, 'runs': connection.execute('SELECT COUNT(*) FROM ota_runs').fetchone()[0],
                'revisions': len(revisions), 'decisions': connection.execute('SELECT COUNT(*) FROM ota_decisions').fetchone()[0]}


def export_id(bundle: PersistentBundle) -> str:
    """Content-address the exact portable export, including decision history."""
    return 'sha256:' + content_hash(canonical_json(bundle.model_dump(mode='json')))


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _copy_database(source: Path, destination: Path) -> None:
    if source.resolve() == destination.resolve():
        raise StorageError('Source and destination must differ')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('xb'):
        pass
    with readonly(source) as original, sqlite3.connect(destination) as target:
        original.backup(target)


def _backup_locked(source: Path, destination: Path) -> dict[str, Any]:
    manifest_path = destination.with_name(destination.name + '.manifest.json')
    if destination.exists() or manifest_path.exists():
        raise StorageError('Backup destination or manifest already exists; refusing overwrite')
    verify_database(source)
    _copy_database(source, destination)
    verified = verify_database(destination)
    manifest = {'format_version': 'workspace-backup-v1', 'sha256': _file_hash(destination),
                'created_at_utc': utc_now(), 'verified': verified}
    with manifest_path.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(manifest, indent=2) + '\n')
    return manifest


def backup_workspace(source: Path, destination: Path) -> dict[str, Any]:
    """Snapshot a live WAL workspace consistently under its execution lock."""
    with execution_lock(source.with_name(source.name + '.execution.lock')):
        return _backup_locked(source, destination)


def restore_workspace(backup: Path, destination: Path) -> dict[str, Any]:
    """Restore only verified artifacts to a new path; never replace a live database."""
    manifest = json.loads(backup.with_name(backup.name + '.manifest.json').read_text(encoding='utf-8-sig'))
    if manifest.get('format_version') != 'workspace-backup-v1' or _file_hash(backup) != manifest.get('sha256'):
        raise StorageError('Backup manifest/hash mismatch')
    verified = verify_database(backup)
    if verified != manifest.get('verified'):
        raise StorageError('Backup verification summary mismatch')
    _copy_database(backup, destination)
    if verify_database(destination) != verified:
        raise StorageError('Restored verification summary mismatch')
    return verified


def migrate_workspace(path: Path, backup: Path) -> dict[str, Any]:
    """Explicit, backed-up, transactional v1-to-v2 migration; no evidence rewrites."""
    with execution_lock(path.with_name(path.name + '.execution.lock')):
        if verify_database(path)['storage_schema'] != 1:
            raise StorageVersionError('Migration requires schema 1; schema 2 is already current')
        manifest = _backup_locked(path, backup)
        with sqlite3.connect(path, isolation_level=None) as connection:
            connection.execute('PRAGMA foreign_keys=ON')
            connection.execute('BEGIN IMMEDIATE')
            try:
                if connection.execute('SELECT schema_version FROM ota_meta WHERE id=1').fetchone()[0] != 1:
                    raise StorageVersionError('Workspace schema changed concurrently')
                for statement in SCHEMA_V2:
                    connection.execute(statement)
                connection.execute('INSERT INTO ota_migrations VALUES (2,?,?)', (utc_now(), manifest['sha256']))
                connection.execute('UPDATE ota_meta SET schema_version=2 WHERE id=1')
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
        return verify_database(path)


def archive_run(path: Path, run_id: str, *, actor: str, reason: str) -> None:
    """Freeze a fully reviewed run without deleting evidence, checkpoints, or history."""
    if not actor.strip() or not reason.strip():
        raise StorageError('Archive actor and reason are required')
    with execution_lock(path.with_name(path.name + '.execution.lock')):
        if verify_database(path)['storage_schema'] != 2:
            raise StorageVersionError('Archiving requires explicit schema 2 migration')
        with sqlite3.connect(path) as connection:
            connection.execute('PRAGMA foreign_keys=ON')
            row = connection.execute('''SELECT r.status,d.revision FROM ota_runs u JOIN ota_revisions r
                ON r.run_id=u.run_id AND r.revision=u.current_revision LEFT JOIN ota_decisions d
                ON d.run_id=r.run_id AND d.revision=r.revision WHERE u.run_id=?''', (run_id,)).fetchone()
            if row is None or row[0] != 'ready' or row[1] is None:
                raise StorageError('Only completed, reviewed runs can be archived')
            connection.execute('INSERT INTO ota_retention VALUES (?,?,?,?)', (run_id, utc_now(), actor, reason))


def main(argv: list[str] | None = None) -> int:
    """Trusted-host maintenance commands; stop the UI for migration and cutover."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('verify', 'backup', 'restore', 'migrate', 'archive'):
        item = sub.add_parser(command)
        item.add_argument('database', type=Path)
        if command in ('backup', 'restore', 'migrate'):
            item.add_argument('--destination', type=Path, required=True)
        if command == 'archive':
            item.add_argument('--run-id', required=True)
            item.add_argument('--actor', required=True)
            item.add_argument('--reason', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'verify':
            result = verify_database(args.database)
        elif args.command == 'backup':
            result = backup_workspace(args.database, args.destination)
        elif args.command == 'restore':
            result = restore_workspace(args.database, args.destination)
        elif args.command == 'migrate':
            result = migrate_workspace(args.database, args.destination)
        else:
            archive_run(args.database, args.run_id, actor=args.actor, reason=args.reason)
            result = {'archived': args.run_id}
        sys.stdout.write(json.dumps(result, indent=2) + '\n')
        return 0
    except (StorageError, OSError, ValueError, sqlite3.Error):
        sys.stderr.write('Maintenance failed; verify paths, schema, and evidence. No existing destination is overwritten.\n')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
