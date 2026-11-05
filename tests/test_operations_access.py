"""Single-host permissions and verified operational lifecycle, entirely offline."""
import json
from pathlib import Path
import sqlite3
from time import time
from typing import Any
import pytest
from ota_verifier.access import AccessDenied, AccessPolicy, Account, authorize, load_access_policy
from ota_verifier.persistence.operations import (archive_run, backup_workspace, export_id,
    migrate_workspace, restore_workspace, verify_database)
from ota_verifier.persistence.service import PersistentWorkflowService
from ota_verifier.persistence.store import StorageError, StorageVersionError
from ota_verifier.shared import SharedWorkflowService
from ota_verifier.workflow_examples import example_input, fixture_dependencies
from ota_verifier.workflow_models import ReviewBundle, ReviewSubmission, WorkflowInput


def policy(path: Path, roles: tuple = ('reader', 'analyst', 'reviewer')) -> AccessPolicy:
    """Create operator-owned grants for one synthetic verified identity."""
    return AccessPolicy(database_path=str(path), accounts=(Account(issuer='https://id.example', subject='subject-1', roles=roles),))


def claims() -> dict[str, Any]:
    """Mock Streamlit's already-verified claims; no raw tokens or live login."""
    return {'iss': 'https://id.example', 'sub': 'subject-1', 'iat': int(time()) - 1, 'exp': int(time()) + 600}


def seed(path: Path) -> ReviewBundle:
    """Create a no-update fixture run before operational migration."""
    request, case = example_input('no_updates')
    with PersistentWorkflowService(path) as service:
        return service.start(WorkflowInput(request=request), fixture_dependencies(case), run_id='run')


def submission(bundle: ReviewBundle, key: str = 'decision') -> ReviewSubmission:
    """Use a spoofed form name to verify the shared boundary overrides it."""
    return ReviewSubmission(run_id=bundle.run_id, revision=bundle.revision, snapshot_hash=bundle.snapshot_hash,
        idempotency_key=key, action='approve', reviewer='spoofed admin', reason='Inspected simulation proposal')


def migrated(tmp_path: Path) -> tuple[Path, ReviewBundle]:
    """Prepare operational schema explicitly, retaining all original evidence."""
    path = tmp_path / 'workspace.sqlite'
    bundle = seed(path)
    migrate_workspace(path, tmp_path / 'before.sqlite')
    return path, bundle


@pytest.mark.parametrize('role,action,allowed', [
    ('reader', 'read', True), ('reader', 'review', False), ('reader', 'analyze', False),
    ('analyst', 'analyze', True), ('analyst', 'review', False),
    ('reviewer', 'review', True), ('reviewer', 'analyze', False),
    ('admin', 'admin', True), ('admin', 'review', True), ('reviewer', 'admin', False),
])
def test_role_matrix(role: str, action: str, allowed: bool, tmp_path: Path) -> None:
    rules = policy(tmp_path / 'db', (role,))
    if allowed:
        assert authorize(rules, claims(), True, action).subject == 'subject-1'
    else:
        with pytest.raises(AccessDenied):
            authorize(rules, claims(), True, action)


@pytest.mark.parametrize('change', [
    {'iss': 'https://evil.example'}, {'sub': 'other'}, {'exp': 0}, {'iat': 0},
    {'iat': None}, {'exp': None}, {'exp': True}, {'iat': float('nan')},
])
def test_invalid_identity_or_expiry_is_denied(tmp_path: Path, change: dict[str, Any]) -> None:
    with pytest.raises(AccessDenied):
        authorize(policy(tmp_path / 'db'), {**claims(), **change}, True, 'read')


def test_no_login_or_role_from_claims_is_accepted(tmp_path: Path) -> None:
    with pytest.raises(AccessDenied):
        authorize(policy(tmp_path / 'db'), claims(), False, 'read')
    with pytest.raises(AccessDenied):
        authorize(policy(tmp_path / 'db', ('reader',)), {**claims(), 'roles': ['admin']}, True, 'review')


def test_duplicate_accounts_and_invalid_config_fail_closed(tmp_path: Path) -> None:
    rules = policy(tmp_path / 'db')
    with pytest.raises(ValueError):
        AccessPolicy(database_path='db', accounts=(*rules.accounts, *rules.accounts))
    with pytest.raises(AccessDenied, match='missing or invalid'):
        load_access_policy(tmp_path / 'missing.json')


def test_migration_preserves_evidence_and_backup_restores(tmp_path: Path) -> None:
    path, original = migrated(tmp_path)
    assert verify_database(path) == {'storage_schema': 2, 'runs': 1, 'revisions': 1, 'decisions': 0}
    with PersistentWorkflowService(path) as service:
        assert service.get('run') == original
    restored = tmp_path / 'restored-v1.sqlite'
    assert restore_workspace(tmp_path / 'before.sqlite', restored)['storage_schema'] == 1
    with PersistentWorkflowService(restored) as service:
        assert service.get('run') == original
    with pytest.raises(StorageVersionError):
        migrate_workspace(path, tmp_path / 'not-needed.sqlite')
    assert not (tmp_path / 'not-needed.sqlite').exists()


def test_authenticated_review_identity_and_sql_provenance_commit_together(tmp_path: Path) -> None:
    path, bundle = migrated(tmp_path)
    rules = policy(path)
    with SharedWorkflowService(path, lambda action: authorize(rules, claims(), True, action)) as service:
        # Migration changed runtime/storage metadata: analyze a fresh revision.
        incoming = service.workflow_input('run')
        _, case = example_input('no_updates')
        bundle = service.revise('run', incoming, fixture_dependencies(case))
        result = service.review(submission(bundle))
        assert result.review_state == 'approved'
        assert result.current_decision.submission.reviewer == rules.accounts[0].identity
        assert service.review(submission(bundle)) == result
        with service.store.connect() as connection:
            audit = connection.execute('SELECT * FROM ota_review_auth').fetchone()
            assert audit['identity_json'] == rules.accounts[0].identity
            assert json.loads(audit['roles_json']) == list(rules.accounts[0].roles)
            assert connection.execute('SELECT COUNT(*) FROM ota_decisions').fetchone()[0] == 1
        assert verify_database(path)['decisions'] == 1
        backup_workspace(path, tmp_path / 'reviewed.sqlite')
        original_export = service.export('run')
        assert export_id(original_export) == export_id(service.export('run'))
    restore_workspace(tmp_path / 'reviewed.sqlite', tmp_path / 'restored.sqlite')
    with PersistentWorkflowService(tmp_path / 'restored.sqlite') as service:
        assert service.export('run') == original_export
        assert service.get('run').review_state == 'approved'


def test_reader_cannot_review_or_analyze_even_if_ui_is_bypassed(tmp_path: Path) -> None:
    path, bundle = migrated(tmp_path)
    rules = policy(path, ('reader',))
    with SharedWorkflowService(path, lambda action: authorize(rules, claims(), True, action)) as service:
        assert service.get('run') == bundle
        with pytest.raises(AccessDenied):
            service.review(submission(bundle))
        with pytest.raises(AccessDenied):
            service.revise('run', bundle.snapshot.artifacts.input)
        with pytest.raises(AccessDenied):
            service.resume('run')
        assert service.allowed('review') is False
        assert verify_database(path)['decisions'] == 0


def test_revocation_is_checked_again_at_the_commit_boundary(tmp_path: Path) -> None:
    path, _ = migrated(tmp_path)
    rules = policy(path)
    deny_review = False
    def check(action: Any) -> Account:
        nonlocal deny_review
        if action == 'review':
            if deny_review:
                raise AccessDenied('Revoked')
            deny_review = True
        return authorize(rules, claims(), True, action)
    with SharedWorkflowService(path, check) as service:
        request, case = example_input('no_updates')
        bundle = service.revise('run', WorkflowInput(request=request), fixture_dependencies(case))
        with pytest.raises(AccessDenied):
            service.review(submission(bundle))
        assert service.get('run').current_decision is None
        assert verify_database(path)['decisions'] == 0


def test_shared_mode_requires_explicit_migration(tmp_path: Path) -> None:
    path = tmp_path / 'workspace.sqlite'
    seed(path)
    with pytest.raises(AccessDenied, match='schema 2'):
        SharedWorkflowService(path, lambda action: policy(path).accounts[0])
    assert verify_database(path)['storage_schema'] == 1


def test_archive_preserves_all_data_and_blocks_mutations(tmp_path: Path) -> None:
    path, _ = migrated(tmp_path)
    with PersistentWorkflowService(path) as service:
        request, case = example_input('no_updates')
        bundle = service.revise('run', WorkflowInput(request=request), fixture_dependencies(case))
        bundle = service.review(submission(bundle))
        before = service.export('run')
        archive_run(path, 'run', actor='host-operator', reason='Retain completed portfolio review')
        assert service.export('run') == before
        assert service.get_revision('run', 1)
        for action in (lambda: service.review(submission(bundle)), lambda: service.resume('run'),
                       lambda: service.revise('run', WorkflowInput(request=request), fixture_dependencies(case))):
            with pytest.raises(StorageError, match='archived'):
                action()
        assert len(service.revisions('run')) == 2
        backup_workspace(path, tmp_path / 'archived.sqlite')
    restore_workspace(tmp_path / 'archived.sqlite', tmp_path / 'archived-restored.sqlite')
    with PersistentWorkflowService(tmp_path / 'archived-restored.sqlite') as service:
        with pytest.raises(StorageError, match='archived'):
            service.resume('run')


def test_unreviewed_run_cannot_be_archived(tmp_path: Path) -> None:
    path, _ = migrated(tmp_path)
    with pytest.raises(StorageError, match='completed, reviewed'):
        archive_run(path, 'run', actor='operator', reason='not yet reviewed')


def test_live_wal_backup_captures_latest_commits_without_overwrite(tmp_path: Path) -> None:
    path = tmp_path / 'workspace.sqlite'
    bundle = seed(path)
    with PersistentWorkflowService(path) as service:
        reviewed = service.review(submission(bundle))
        backup = tmp_path / 'live.sqlite'
        backup_workspace(path, backup)
        with pytest.raises(StorageError, match='overwrite'):
            backup_workspace(path, backup)
        with pytest.raises((StorageError, FileExistsError)):
            restore_workspace(backup, path)
    restore_workspace(backup, tmp_path / 'copy.sqlite')
    with PersistentWorkflowService(tmp_path / 'copy.sqlite') as service:
        assert service.get('run') == reviewed


def test_corrupt_backup_and_existing_target_fail_without_overwrite(tmp_path: Path) -> None:
    path = tmp_path / 'workspace.sqlite'
    seed(path)
    backup = tmp_path / 'backup.sqlite'
    backup_workspace(path, backup)
    with backup.open('ab') as stream:
        stream.write(b'changed')
    target = tmp_path / 'must-not-create.sqlite'
    with pytest.raises(StorageError, match='hash'):
        restore_workspace(backup, target)
    assert not target.exists()


def test_failed_migration_rolls_back_all_schema_changes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / 'workspace.sqlite'
    original = seed(path)
    import ota_verifier.persistence.operations as operations
    monkeypatch.setattr(operations, 'SCHEMA_V2', (*operations.SCHEMA_V2, 'INVALID SQL'))
    with pytest.raises(sqlite3.Error):
        migrate_workspace(path, tmp_path / 'before.sqlite')
    assert verify_database(path)['storage_schema'] == 1
    with sqlite3.connect(path) as connection:
        assert not connection.execute("SELECT 1 FROM sqlite_master WHERE name='ota_review_auth'").fetchone()
    with PersistentWorkflowService(path) as service:
        assert service.get('run') == original


def test_export_id_changes_with_review_decision(tmp_path: Path) -> None:
    path = tmp_path / 'workspace.sqlite'
    bundle = seed(path)
    with PersistentWorkflowService(path) as service:
        before = export_id(service.export('run'))
        service.review(submission(bundle))
        assert export_id(service.export('run')) != before


def test_sql_auth_provenance_failure_rolls_back_decision(tmp_path: Path) -> None:
    path, _ = migrated(tmp_path)
    rules = policy(path)
    with SharedWorkflowService(path, lambda action: authorize(rules, claims(), True, action)) as service:
        request, case = example_input('no_updates')
        bundle = service.revise('run', WorkflowInput(request=request), fixture_dependencies(case))
        with service.store.transaction() as connection:
            connection.execute("CREATE TRIGGER reject_auth BEFORE INSERT ON ota_review_auth BEGIN SELECT RAISE(ABORT,'test failure'); END")
        with pytest.raises(sqlite3.Error):
            service.review(submission(bundle))
        assert service.get('run').current_decision is None
        with service.store.connect() as connection:
            assert connection.execute('SELECT COUNT(*) FROM ota_decisions').fetchone()[0] == 0
            assert connection.execute('SELECT COUNT(*) FROM ota_review_auth').fetchone()[0] == 0


def test_simultaneous_authenticated_decisions_commit_one_actor_record(tmp_path: Path) -> None:
    import subprocess
    import sys
    path, _ = migrated(tmp_path)
    rules = policy(path)
    with PersistentWorkflowService(path) as service:
        request, case = example_input('no_updates')
        bundle = service.revise('run', WorkflowInput(request=request), fixture_dependencies(case))
    scripts = []
    for key in ('first', 'second'):
        raw = submission(bundle, key).model_dump_json()
        scripts.append(f'''from pathlib import Path
from ota_verifier.access import Account
from ota_verifier.shared import SharedWorkflowService
from ota_verifier.workflow_models import ReviewSubmission
account=Account(issuer='https://id.example',subject='subject-1',roles=('reviewer',))
with SharedWorkflowService(Path({str(path)!r}),lambda action: account) as service:
 service.review(ReviewSubmission.model_validate_json({raw!r}))
''')
    processes = [subprocess.Popen([sys.executable, '-c', script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for script in scripts]
    results = [(process.communicate(timeout=40), process.returncode) for process in processes]
    assert sorted(code for _, code in results) == [0, 1], results
    assert verify_database(path)['decisions'] == 1
    with sqlite3.connect(path) as connection:
        assert connection.execute('SELECT COUNT(*) FROM ota_review_auth').fetchone()[0] == 1


def test_authenticated_export_retains_validated_provenance(tmp_path: Path) -> None:
    from ota_verifier.persistence.models import PersistentBundle
    path, _ = migrated(tmp_path)
    rules = policy(path)
    with SharedWorkflowService(path, lambda action: authorize(rules, claims(), True, action)) as service:
        request, case = example_input('no_updates')
        bundle = service.revise('run', WorkflowInput(request=request), fixture_dependencies(case))
        service.review(submission(bundle))
        envelope = service.export('run')
        assert envelope.format_version == 'persistent-review-v2'
        assert len(envelope.review_authentication) == 1
        assert envelope.review_authentication[0].subject == 'subject-1'
        assert PersistentBundle.model_validate_json(envelope.model_dump_json()) == envelope
        raw = envelope.model_dump(mode='json')
        raw['review_authentication'][0]['subject'] = 'another-user'
        with pytest.raises(ValueError):
            PersistentBundle.model_validate_json(json.dumps(raw))


def test_legacy_export_shape_remains_unchanged(tmp_path: Path) -> None:
    path = tmp_path / 'workspace.sqlite'
    seed(path)
    with PersistentWorkflowService(path) as service:
        envelope = service.export('run')
        assert envelope.format_version == 'persistent-review-v1'
        assert 'review_authentication' not in envelope.model_dump(mode='json')


def test_corrupt_registry_prevents_backup(tmp_path: Path) -> None:
    path = tmp_path / 'workspace.sqlite'
    seed(path)
    with sqlite3.connect(path) as connection:
        connection.execute('UPDATE ota_runs SET current_revision=99')
    with pytest.raises(StorageError, match='missing revision'):
        backup_workspace(path, tmp_path / 'must-not-create.sqlite')
    assert not (tmp_path / 'must-not-create.sqlite').exists()


def test_interrupted_checkpoint_survives_verified_backup(tmp_path: Path) -> None:
    path = tmp_path / 'workspace.sqlite'
    request, case = example_input('no_updates')
    with PersistentWorkflowService(path) as service:
        service.begin(WorkflowInput(request=request), fixture_dependencies(case), run_id='paused')
    backup_workspace(path, tmp_path / 'paused.sqlite')
    restore_workspace(tmp_path / 'paused.sqlite', tmp_path / 'restored.sqlite')
    with PersistentWorkflowService(tmp_path / 'restored.sqlite') as service:
        assert service.resume('paused').snapshot.artifacts.status == 'simulation_passed'


def test_maintenance_cli_does_not_overwrite(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from ota_verifier.persistence.operations import main
    path = tmp_path / 'workspace.sqlite'
    seed(path)
    assert main(['verify', str(path)]) == 0
    assert json.loads(capsys.readouterr().out)['runs'] == 1
    destination = tmp_path / 'backup.sqlite'
    assert main(['backup', str(path), '--destination', str(destination)]) == 0
    capsys.readouterr()
    original = destination.read_bytes()
    assert main(['backup', str(path), '--destination', str(destination)]) == 1
    assert destination.read_bytes() == original


def test_shared_stale_review_is_denied(tmp_path: Path) -> None:
    path, _ = migrated(tmp_path)
    rules = policy(path)
    with SharedWorkflowService(path, lambda action: authorize(rules, claims(), True, action)) as service:
        request, case = example_input('no_updates')
        first = service.revise('run', WorkflowInput(request=request), fixture_dependencies(case))
        _, case = example_input('no_updates')
        service.revise('run', WorkflowInput(request=request), fixture_dependencies(case))
        with pytest.raises(StorageError, match='stale'):
            service.review(submission(first))
        assert verify_database(path)['decisions'] == 0
