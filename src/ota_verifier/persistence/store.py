"""Transactional local run registry, immutable revisions, receipts, and decisions."""
from contextlib import contextmanager
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
import sqlite3
from typing import Any
from ..llm.evidence import content_hash
from ..workflow_models import ReviewDecision, ReviewSnapshot, ReviewSubmission, WorkflowInput, approval_eligible, snapshot_hash
from .models import RunSummary, VersionManifest
from .recipes import ClientRecipe
from .schema import REQUIRED_V2


class StorageError(RuntimeError):
    """A workspace cannot be safely interpreted or changed."""


class StorageVersionError(StorageError):
    """The database/record schema is unsupported; no implicit migration is performed."""


class RunNotReady(StorageError):
    """An analysis has not reached its complete review snapshot."""


class UncertainModelCall(StorageError):
    """A provider request may have completed; it must not be silently retried."""


def utc_now() -> str:
    """Return an explicit UTC timestamp for durable audit metadata."""
    return datetime.now(UTC).isoformat()


SCHEMA = (
    'CREATE TABLE IF NOT EXISTS ota_meta (id INTEGER PRIMARY KEY CHECK(id=1), schema_version INTEGER NOT NULL)',
    '''CREATE TABLE IF NOT EXISTS ota_runs (
       run_id TEXT PRIMARY KEY, current_revision INTEGER NOT NULL, created_at TEXT NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS ota_revisions (
       run_id TEXT NOT NULL REFERENCES ota_runs(run_id), revision INTEGER NOT NULL,
       thread_id TEXT NOT NULL UNIQUE, campaign_id TEXT NOT NULL, input_json TEXT NOT NULL,
       input_hash TEXT NOT NULL, recipe_json TEXT NOT NULL, recipe_hash TEXT NOT NULL,
       versions_json TEXT NOT NULL, versions_hash TEXT NOT NULL, created_at TEXT NOT NULL,
       status TEXT NOT NULL CHECK(status IN ('pending','paused','ready','uncertain','error')),
       analysis_status TEXT, snapshot_json TEXT, snapshot_hash TEXT,
       completed_nodes_json TEXT NOT NULL DEFAULT '[]', message TEXT,
       PRIMARY KEY(run_id, revision))''',
    '''CREATE TABLE IF NOT EXISTS ota_decisions (
       run_id TEXT NOT NULL, revision INTEGER NOT NULL, idempotency_key TEXT NOT NULL,
       submission_json TEXT NOT NULL, decision_json TEXT NOT NULL,
       PRIMARY KEY(run_id, revision), UNIQUE(run_id,idempotency_key),
       FOREIGN KEY(run_id, revision) REFERENCES ota_revisions(run_id, revision))''',
    '''CREATE TABLE IF NOT EXISTS ota_receipts (
       thread_id TEXT NOT NULL, purpose TEXT NOT NULL, fingerprint TEXT NOT NULL,
       status TEXT NOT NULL CHECK(status IN ('inflight','complete','rejected','uncertain')),
       call_json TEXT, call_hash TEXT, error TEXT,
       PRIMARY KEY(thread_id,purpose,fingerprint))''',
)


class RunStore:
    """SQLite WAL workspace; SQL transactions never surround external model calls."""

    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if tables and 'ota_meta' not in tables:
                raise StorageVersionError('Existing database is not an OTA review workspace')
            if 'ota_meta' in tables:
                row = connection.execute('SELECT schema_version FROM ota_meta WHERE id=1').fetchone()
                if row is None or row[0] not in (1, 2):
                    raise StorageVersionError('Unsupported workspace schema version; explicit migration is required')
            if 'ota_meta' in tables and row[0] == 2 and not REQUIRED_V2 <= tables:
                raise StorageVersionError('Operational schema tables are missing; restore a verified backup')
            connection.execute('PRAGMA journal_mode=WAL')
            connection.execute('BEGIN IMMEDIATE')
            try:
                for statement in SCHEMA:
                    connection.execute(statement)
                connection.execute('INSERT OR IGNORE INTO ota_meta VALUES (1,1)')
                row = connection.execute('SELECT schema_version FROM ota_meta WHERE id=1').fetchone()
                if row[0] not in (1, 2):
                    raise StorageVersionError('Unsupported workspace schema version')
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    @property
    def schema_version(self) -> int:
        """Read the current schema without triggering an implicit migration."""
        with self.connect() as connection:
            return int(connection.execute('SELECT schema_version FROM ota_meta WHERE id=1').fetchone()[0])

    def assert_writable(self, run_id: str) -> None:
        """Archived evidence remains readable but cannot be revised or reviewed."""
        with self.connect() as connection:
            if self.schema_version == 2 and connection.execute(
                    'SELECT 1 FROM ota_retention WHERE run_id=?', (run_id,)).fetchone():
                raise StorageError('Run is archived; its retained evidence is read-only')

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Open a short-lived connection with foreign keys and bounded contention."""
        connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA synchronous=FULL')
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Commit an application mutation atomically or roll it back completely."""
        with self.connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            try:
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    def allocate(self, run_id: str, incoming: WorkflowInput, recipe: ClientRecipe,
                 versions: VersionManifest, *, revise: bool = False) -> int:
        """Create an immutable revision and advance the current revision atomically."""
        self.assert_writable(run_id)
        with self.transaction() as connection:
            row = connection.execute('SELECT current_revision FROM ota_runs WHERE run_id=?', (run_id,)).fetchone()
            if revise and row is None:
                raise StorageError('Unknown persistent run')
            if not revise and row is not None:
                raise StorageError('Run ID already exists; create a revision instead')
            revision = row[0] + 1 if row else 1
            created = utc_now()
            if row:
                connection.execute('UPDATE ota_runs SET current_revision=? WHERE run_id=?', (revision, run_id))
            else:
                connection.execute('INSERT INTO ota_runs VALUES (?,?,?)', (run_id, revision, created))
            raw_input, raw_recipe, raw_versions = incoming.model_dump_json(), recipe.model_dump_json(), versions.model_dump_json()
            connection.execute('''INSERT INTO ota_revisions
                (run_id,revision,thread_id,campaign_id,input_json,input_hash,recipe_json,recipe_hash,
                 versions_json,versions_hash,created_at,status) VALUES (?,?,?,?,?,?,?,?,?,?,?,'pending')''',
                (run_id, revision, f'{run_id}:{revision}', incoming.request.campaign.id, raw_input,
                 content_hash(raw_input), raw_recipe, content_hash(raw_recipe), raw_versions,
                 content_hash(raw_versions), created))
            return revision

    def revision(self, run_id: str, revision: int | None = None) -> dict[str, Any]:
        """Read and validate immutable input/recipe/version data before use."""
        with self.connect() as connection:
            if revision is None:
                current = connection.execute('SELECT current_revision FROM ota_runs WHERE run_id=?', (run_id,)).fetchone()
                if current is None:
                    raise StorageError('Unknown persistent run')
                revision = current[0]
            row = connection.execute('SELECT * FROM ota_revisions WHERE run_id=? AND revision=?', (run_id, revision)).fetchone()
            if row is None:
                raise StorageError('Unknown persistent revision')
            result = dict(row)
        for value, digest in (('input_json', 'input_hash'), ('recipe_json', 'recipe_hash'), ('versions_json', 'versions_hash')):
            if content_hash(result[value]) != result[digest]:
                raise StorageError(f'Corrupt persistent revision: {value} hash mismatch')
        try:
            WorkflowInput.model_validate_json(result['input_json'])
            ClientRecipe.model_validate_json(result['recipe_json'])
            VersionManifest.model_validate_json(result['versions_json'])
        except ValueError:
            raise StorageVersionError('Unsupported or malformed persistent record; no reinterpretation was performed') from None
        return result

    def mark(self, run_id: str, revision: int, status: str, message: str | None = None,
             completed_nodes_json: str | None = None) -> None:
        """Persist an interrupted/paused outcome without inventing a successful snapshot."""
        with self.transaction() as connection:
            connection.execute('''UPDATE ota_revisions SET status=?,message=?,
                completed_nodes_json=COALESCE(?,completed_nodes_json) WHERE run_id=? AND revision=?''',
                (status, message, completed_nodes_json, run_id, revision))

    def publish(self, run_id: str, revision: int, snapshot: ReviewSnapshot, nodes_json: str) -> None:
        """Publish complete analysis exactly once; later reviews cannot mutate it."""
        raw = snapshot.model_dump_json()
        digest = snapshot_hash(run_id, revision, snapshot)
        with self.transaction() as connection:
            row = connection.execute('SELECT snapshot_json,snapshot_hash FROM ota_revisions WHERE run_id=? AND revision=?',
                                     (run_id, revision)).fetchone()
            if row is None:
                raise StorageError('Cannot publish an unknown revision')
            if row['snapshot_json'] is not None:
                if row['snapshot_json'] != raw or row['snapshot_hash'] != digest:
                    raise StorageError('Cannot overwrite immutable published analysis')
                return
            connection.execute('''UPDATE ota_revisions SET status='ready',snapshot_json=?,snapshot_hash=?,
                analysis_status=?,completed_nodes_json=?,message=NULL WHERE run_id=? AND revision=?''',
                (raw, digest, snapshot.artifacts.status, nodes_json, run_id, revision))

    def decisions(self, run_id: str, through_revision: int) -> tuple[ReviewDecision, ...]:
        """Read immutable decisions up to the selected revision."""
        with self.connect() as connection:
            rows = connection.execute('SELECT decision_json FROM ota_decisions WHERE run_id=? AND revision<=? ORDER BY revision',
                                      (run_id, through_revision)).fetchall()
        return tuple(ReviewDecision.model_validate_json(row[0]) for row in rows)

    def record_decision(self, submission: ReviewSubmission, snapshot: ReviewSnapshot,
                        *, identity_json: str | None = None, roles_json: str | None = None) -> ReviewDecision:
        """CAS current revision/hash and commit one idempotent decision in one transaction."""
        self.assert_writable(submission.run_id)
        if identity_json is not None and (self.schema_version != 2 or submission.reviewer != identity_json or roles_json is None):
            raise StorageError('Authenticated decisions require operational schema and matching identity')
        with self.transaction() as connection:
            current = connection.execute('SELECT current_revision FROM ota_runs WHERE run_id=?', (submission.run_id,)).fetchone()
            row = connection.execute('SELECT status,snapshot_hash,snapshot_json FROM ota_revisions WHERE run_id=? AND revision=?',
                                     (submission.run_id, submission.revision)).fetchone()
            if (current is None or current[0] != submission.revision or row is None or row['status'] != 'ready'
                    or row['snapshot_hash'] != submission.snapshot_hash
                    or snapshot_hash(submission.run_id, submission.revision, snapshot) != submission.snapshot_hash
                    or row['snapshot_json'] != snapshot.model_dump_json()):
                raise StorageError('Review is stale or does not cover the current immutable snapshot')
            previous = connection.execute('SELECT submission_json,decision_json FROM ota_decisions WHERE run_id=? AND idempotency_key=?',
                                          (submission.run_id, submission.idempotency_key)).fetchone()
            if previous:
                if ReviewSubmission.model_validate_json(previous[0]) != submission:
                    raise StorageError('Idempotency key already belongs to another decision')
                return ReviewDecision.model_validate_json(previous[1])
            if connection.execute('SELECT 1 FROM ota_decisions WHERE run_id=? AND revision=?',
                                  (submission.run_id, submission.revision)).fetchone():
                raise StorageError('This revision already has a final decision')
            if submission.action == 'approve' and not approval_eligible(snapshot):
                raise StorageError('Violations or inconclusive analysis cannot be approved')
            decision = ReviewDecision(submission=submission, recorded_at_utc=utc_now())
            connection.execute('INSERT INTO ota_decisions VALUES (?,?,?,?,?)',
                (submission.run_id, submission.revision, submission.idempotency_key,
                 submission.model_dump_json(), decision.model_dump_json()))
            if identity_json is not None:
                connection.execute('INSERT INTO ota_review_auth VALUES (?,?,?,?,?)',
                    (submission.run_id, submission.revision, identity_json, roles_json, decision.recorded_at_utc))
            return decision

    def receipt(self, thread_id: str, purpose: str, fingerprint: str) -> dict[str, Any] | None:
        """Read a response receipt without constructing a provider client."""
        with self.connect() as connection:
            row = connection.execute('SELECT * FROM ota_receipts WHERE thread_id=? AND purpose=? AND fingerprint=?',
                                     (thread_id, purpose, fingerprint)).fetchone()
        return dict(row) if row else None

    def begin_receipt(self, thread_id: str, purpose: str, fingerprint: str) -> None:
        """Commit intent before a provider request; a crash leaves an uncertain marker."""
        with self.transaction() as connection:
            connection.execute("INSERT INTO ota_receipts(thread_id,purpose,fingerprint,status) VALUES (?,?,?,'inflight')",
                               (thread_id, purpose, fingerprint))

    def finish_receipt(self, thread_id: str, purpose: str, fingerprint: str, status: str,
                       call_json: str | None, error: str | None) -> None:
        """Save available response evidence or an explicit nonretryable outcome."""
        with self.transaction() as connection:
            connection.execute('UPDATE ota_receipts SET status=?,call_json=?,call_hash=?,error=? WHERE thread_id=? AND purpose=? AND fingerprint=?',
                               (status, call_json, content_hash(call_json) if call_json else None, error, thread_id, purpose, fingerprint))

    def summaries(self, run_id: str | None = None) -> tuple[RunSummary, ...]:
        """List latest runs or every revision, without deserializing full fault traces."""
        with self.connect() as connection:
            if run_id is None:
                rows = connection.execute('''SELECT r.* FROM ota_revisions r JOIN ota_runs u
                    ON r.run_id=u.run_id AND r.revision=u.current_revision ORDER BY r.created_at DESC''').fetchall()
            else:
                rows = connection.execute('SELECT * FROM ota_revisions WHERE run_id=? ORDER BY revision', (run_id,)).fetchall()
            result = []
            for row in rows:
                decision = connection.execute('SELECT decision_json FROM ota_decisions WHERE run_id=? AND revision=?',
                                              (row['run_id'], row['revision'])).fetchone()
                older = connection.execute('SELECT 1 FROM ota_decisions WHERE run_id=? AND revision<? LIMIT 1',
                                           (row['run_id'], row['revision'])).fetchone()
                if decision:
                    action = ReviewDecision.model_validate_json(decision[0]).submission.action
                    review = {'approve': 'approved', 'reject': 'rejected', 'review_with_findings': 'reviewed_with_findings'}[action]
                else:
                    review = 'invalidated' if older else 'awaiting_review'
                result.append(RunSummary(run_id=row['run_id'], revision=row['revision'], campaign_id=row['campaign_id'],
                    status=row['status'], analysis_status=row['analysis_status'], review_state=review,
                    created_at_utc=row['created_at'], snapshot_hash=row['snapshot_hash'], message=row['message']))
            return tuple(result)
