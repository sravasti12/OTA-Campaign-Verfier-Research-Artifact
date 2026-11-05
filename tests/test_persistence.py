"""Durability tests, including real process termination and concurrent decisions."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from typing import Any
import pytest
from ota_verifier.persistence.diff import compare_revisions
from ota_verifier.persistence.recipes import capture_recipe
from ota_verifier.persistence.service import PersistentWorkflowService
from ota_verifier.persistence.store import RunNotReady, StorageError, StorageVersionError, UncertainModelCall
from ota_verifier.workflow_examples import example_input, fixture_dependencies
from ota_verifier.workflow_models import ReviewBundle, ReviewSubmission, WorkflowInput


def incoming(name: str = 'no_updates') -> tuple[WorkflowInput, Any]:
    """Build an explicitly synthetic request and fresh fixture clients."""
    request, case = example_input(name)
    return WorkflowInput(request=request), fixture_dependencies(case)


def submission(bundle: ReviewBundle, key: str = 'decision', action: str = 'approve') -> ReviewSubmission:
    """Bind a human-entered simulation decision to exact evidence."""
    return ReviewSubmission(run_id=bundle.run_id, revision=bundle.revision, snapshot_hash=bundle.snapshot_hash,
        idempotency_key=key, action=action, reviewer='Test reviewer', reason='Inspected simulation evidence')


def child(path: Path, source: str) -> subprocess.CompletedProcess[str]:
    """Execute an independent Python interpreter against one local workspace."""
    prelude = '''from pathlib import Path
import os, sys
from ota_verifier.persistence.service import PersistentWorkflowService
from ota_verifier.persistence.store import RunStore
from ota_verifier.workflow_models import ReviewSubmission
path=Path(sys.argv[1])
'''
    return subprocess.run([sys.executable, '-c', prelude + source, str(path)], capture_output=True, text=True, timeout=40)


def test_reopen_review_and_export_without_clients(tmp_path: Path) -> None:
    path = tmp_path / 'workspace.sqlite'
    value, clients = incoming()
    with PersistentWorkflowService(path) as service:
        original = service.start(value, clients, run_id='run')
    def forbidden(*args: Any) -> Any:
        raise AssertionError('Reading/reviewing replayed a model')
    with PersistentWorkflowService(path, client_factory=forbidden) as service:
        assert service.resume('run') == original
        reviewed = service.review(submission(original))
        assert reviewed.review_state == 'approved'
        assert service.review(submission(original)) == reviewed
        assert service.export('run').review == reviewed
        assert service.export('run').versions.storage_schema == 1
    with PersistentWorkflowService(path, client_factory=forbidden) as service:
        assert len(service.get('run').decisions) == 1


def test_process_restart_resumes_committed_analysis(tmp_path: Path) -> None:
    path = tmp_path / 'workspace.sqlite'
    result = child(path, '''from ota_verifier.workflow_examples import example_input, fixture_dependencies
from ota_verifier.workflow_models import WorkflowInput
request,case=example_input('no_updates')
with PersistentWorkflowService(path) as s:
 s.begin(WorkflowInput(request=request),fixture_dependencies(case),run_id='run',pause_after='extract')
''')
    assert result.returncode == 0, result.stderr
    with PersistentWorkflowService(path) as service:
        with pytest.raises(RunNotReady):
            service.get('run')
        with service.store.connect() as connection:
            original = connection.execute('SELECT call_json FROM ota_receipts ORDER BY purpose').fetchall()
        assert len(original) == 2
        bundle = service.resume('run')
        assert bundle.snapshot.artifacts.status == 'simulation_passed'
        with service.store.connect() as connection:
            assert connection.execute('SELECT COUNT(*) FROM ota_receipts').fetchone()[0] == 3
            assert connection.execute("SELECT call_json FROM ota_receipts WHERE purpose!='explanation' ORDER BY purpose").fetchall() == original


def test_crash_after_model_receipts_reuses_both_outputs(tmp_path: Path) -> None:
    path = tmp_path / 'workspace.sqlite'
    result = child(path, '''import ota_verifier.graph as graph
from ota_verifier.workflow_examples import example_input, fixture_dependencies
from ota_verifier.workflow_models import WorkflowInput
original=graph._visited
def crash(state,node):
 if node=='extract': os._exit(31)
 return original(state,node)
graph._visited=crash
request,case=example_input('no_updates')
with PersistentWorkflowService(path) as s:
 s.start(WorkflowInput(request=request),fixture_dependencies(case),run_id='run')
''')
    assert result.returncode == 31, result.stderr
    with PersistentWorkflowService(path) as service:
        with service.store.connect() as connection:
            records = connection.execute('SELECT call_json FROM ota_receipts ORDER BY purpose').fetchall()
        assert len(records) == 2
        assert service.resume('run').snapshot.artifacts.status == 'simulation_passed'
        with service.store.connect() as connection:
            assert connection.execute("SELECT call_json FROM ota_receipts WHERE purpose!='explanation' ORDER BY purpose").fetchall() == records


def test_crash_inside_model_call_requires_explicit_new_revision(tmp_path: Path) -> None:
    path = tmp_path / 'workspace.sqlite'
    result = child(path, '''from ota_verifier.workflow_examples import example_input, fixture_dependencies
from ota_verifier.workflow_models import WorkflowInput
from ota_verifier.persistence.recipes import capture_recipe
from ota_verifier.graph import WorkflowClients
class Crash:
 def generate_json(self,**kwargs): os._exit(32)
request,case=example_input('no_updates')
clients=fixture_dependencies(case)
with PersistentWorkflowService(path) as s:
 s.start(WorkflowInput(request=request),WorkflowClients(extractor=Crash()),run_id='run',recipe=capture_recipe(clients))
''')
    assert result.returncode == 32, result.stderr
    with PersistentWorkflowService(path) as service:
        with pytest.raises(UncertainModelCall):
            service.resume('run')
        assert service.list_runs()[0].status == 'uncertain'
        assert service.partial_evidence('run')['checkpoint']['input']
        with pytest.raises(UncertainModelCall):
            service.resume('run')
        value, clients = incoming()
        assert service.revise('run', value, clients).revision == 2
        assert len(service.revisions('run')) == 2


def test_crash_after_decision_commit_preserves_authoritative_decision(tmp_path: Path) -> None:
    path = tmp_path / 'workspace.sqlite'
    value, clients = incoming()
    with PersistentWorkflowService(path) as service:
        bundle = service.start(value, clients, run_id='run')
    raw = submission(bundle).model_dump_json()
    result = child(path, f'''original=RunStore.record_decision
def crash(self,submission,snapshot):
 original(self,submission,snapshot)
 os._exit(33)
RunStore.record_decision=crash
with PersistentWorkflowService(path) as s:
 s.review(ReviewSubmission.model_validate_json({raw!r}))
''')
    assert result.returncode == 33, result.stderr
    with PersistentWorkflowService(path) as service:
        recovered = service.get('run')
        assert recovered.review_state == 'approved'
        assert len(recovered.decisions) == 1
        assert service.review(submission(bundle)) == recovered
        assert service.resume('run') == recovered


def test_uncommitted_sql_decision_is_rolled_back_on_process_death(tmp_path: Path) -> None:
    path = tmp_path / 'workspace.sqlite'
    value, clients = incoming()
    with PersistentWorkflowService(path) as service:
        bundle = service.start(value, clients, run_id='run')
    raw = submission(bundle).model_dump_json()
    result = child(path, f'''from ota_verifier.workflow_models import ReviewDecision
sub=ReviewSubmission.model_validate_json({raw!r})
decision=ReviewDecision(submission=sub,recorded_at_utc='2026-11-05T00:00:00+00:00')
store=RunStore(path)
with store.transaction() as c:
 c.execute('INSERT INTO ota_decisions VALUES (?,?,?,?,?)',('run',1,sub.idempotency_key,sub.model_dump_json(),decision.model_dump_json()))
 os._exit(34)
''')
    assert result.returncode == 34, result.stderr
    with PersistentWorkflowService(path) as service:
        assert service.get('run').review_state == 'awaiting_review'
        assert service.review(submission(bundle)).review_state == 'approved'


@pytest.mark.parametrize('duplicate', [True, False])
def test_concurrent_process_review_has_one_decision(tmp_path: Path, duplicate: bool) -> None:
    path = tmp_path / 'workspace.sqlite'
    value, clients = incoming()
    with PersistentWorkflowService(path) as service:
        bundle = service.start(value, clients, run_id='run')
    scripts = []
    for key in ('same', 'same' if duplicate else 'different'):
        raw = submission(bundle, key).model_dump_json()
        scripts.append(f'''from pathlib import Path
from ota_verifier.persistence.service import PersistentWorkflowService
from ota_verifier.workflow_models import ReviewSubmission
with PersistentWorkflowService(Path({str(path)!r})) as s:
 s.review(ReviewSubmission.model_validate_json({raw!r}))
''')
    processes = [subprocess.Popen([sys.executable, '-c', source], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for source in scripts]
    results = [(process.communicate(timeout=40), process.returncode) for process in processes]
    assert sorted(code for _, code in results) == ([0, 0] if duplicate else [0, 1]), results
    with PersistentWorkflowService(path) as service:
        assert len(service.get('run').decisions) == 1


def test_revision_history_diff_and_stale_review(tmp_path: Path) -> None:
    value, clients = incoming()
    with PersistentWorkflowService(tmp_path / 'workspace.sqlite') as service:
        first = service.start(value, clients, run_id='run')
        service.review(submission(first))
        changed, clients = incoming('dependency_only')
        second = service.revise('run', changed, clients)
        assert second.review_state == 'invalidated'
        assert service.get_revision('run', 1).review_state == 'approved'
        assert service.get_revision('run', 1).snapshot_hash == first.snapshot_hash
        with pytest.raises(StorageError, match='stale'):
            service.review(submission(first, 'new'))
        sections = {entry.section for entry in compare_revisions(first, second).changes}
        assert {'documents', 'inventory', 'constraints', 'plan', 'findings', 'outcome'} <= sections
        with pytest.raises((StorageError, ValueError)):
            service.review(submission(second))
        assert service.get('run').current_decision is None


def test_future_database_schema_is_rejected_without_rewrite(tmp_path: Path) -> None:
    path = tmp_path / 'workspace.sqlite'
    with PersistentWorkflowService(path):
        pass
    with sqlite3.connect(path) as connection:
        connection.execute('UPDATE ota_meta SET schema_version=99')
    with pytest.raises(StorageVersionError):
        PersistentWorkflowService(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute('SELECT schema_version FROM ota_meta').fetchone()[0] == 99


@pytest.mark.parametrize('field', ['input_json', 'recipe_json', 'versions_json', 'snapshot_hash'])
def test_corrupt_evidence_cannot_be_reviewed(tmp_path: Path, field: str) -> None:
    value, clients = incoming()
    with PersistentWorkflowService(tmp_path / 'workspace.sqlite') as service:
        service.start(value, clients, run_id='run')
        with service.store.transaction() as connection:
            connection.execute(f'UPDATE ota_revisions SET {field}=?', ('corrupted',))
        with pytest.raises(StorageError):
            service.get('run')


def test_runtime_change_allows_read_but_blocks_new_decision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from ota_verifier.persistence.versions import current_manifest
    value, clients = incoming()
    with PersistentWorkflowService(tmp_path / 'workspace.sqlite') as service:
        bundle = service.start(value, clients, run_id='run')
        changed = current_manifest().model_copy(update={'python_version': 'future'})
        monkeypatch.setattr('ota_verifier.persistence.service.current_manifest', lambda: changed)
        assert service.get('run') == bundle
        with pytest.raises(StorageVersionError):
            service.review(submission(bundle))


def test_public_recipe_excludes_api_key_and_rejects_secret_endpoint() -> None:
    from ota_verifier.graph import WorkflowClients
    from ota_verifier.llm.client import ClientSettings, LLMClient
    from ota_verifier.persistence.recipes import PublicSettings
    from pydantic import SecretStr
    settings = ClientSettings(provider='groq', model='test-model', api_key=SecretStr('never-save-this'))
    recipe = capture_recipe(WorkflowClients(extractor=LLMClient(settings)))
    assert 'never-save-this' not in recipe.model_dump_json()
    assert 'api_key' not in recipe.model_dump_json()
    with pytest.raises(ValueError):
        PublicSettings.capture(settings.model_copy(update={'ollama_base_url': 'http://user:secret@localhost:11434'}))


def test_pending_runtime_change_blocks_resume(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from ota_verifier.persistence.versions import current_manifest
    value, clients = incoming()
    with PersistentWorkflowService(tmp_path / 'workspace.sqlite') as service:
        service.begin(value, clients, run_id='run')
        manifest = current_manifest().model_copy(update={'python_version': 'future'})
        monkeypatch.setattr('ota_verifier.persistence.service.current_manifest', lambda: manifest)
        with pytest.raises(StorageVersionError):
            service.resume('run')
        assert service.list_runs()[0].status == 'paused'


def test_corrupt_receipt_blocks_replay(tmp_path: Path) -> None:
    path = tmp_path / 'workspace.sqlite'
    result = child(path, '''import ota_verifier.graph as graph
from ota_verifier.workflow_examples import example_input, fixture_dependencies
from ota_verifier.workflow_models import WorkflowInput
original=graph._visited
def crash(state,node):
 if node=='extract': os._exit(31)
 return original(state,node)
graph._visited=crash
request,case=example_input('no_updates')
with PersistentWorkflowService(path) as s:
 s.start(WorkflowInput(request=request),fixture_dependencies(case),run_id='run')
''')
    assert result.returncode == 31, result.stderr
    with PersistentWorkflowService(path) as service:
        with service.store.transaction() as connection:
            connection.execute("UPDATE ota_receipts SET call_json='{}' WHERE purpose='extraction'")
        with pytest.raises(StorageError, match='receipt hash'):
            service.resume('run')
        assert service.list_runs()[0].status == 'error'


def test_sqlite_export_contains_no_configured_provider_key(tmp_path: Path) -> None:
    from ota_verifier.graph import WorkflowClients
    from ota_verifier.llm.client import ClientSettings, LLMClient
    from pydantic import SecretStr
    secret = 'this-provider-secret-must-stay-out-of-sqlite'
    def transport(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}]}
    client = LLMClient(ClientSettings(provider='groq', model='mock-model', api_key=SecretStr(secret)), transport=transport)
    value, _ = incoming()
    with PersistentWorkflowService(tmp_path / 'workspace.sqlite') as service:
        bundle = service.start(value, WorkflowClients(extractor=client), run_id='run')
        assert bundle.snapshot.artifacts.status == 'extraction_blocked'
        with service.store.connect() as connection:
            dump = '\n'.join(connection.iterdump())
        assert secret not in dump
        assert 'api_key' not in service.store.revision('run')['recipe_json']
        assert secret not in service.export('run').model_dump_json()


def test_foreign_sqlite_database_is_left_intact(tmp_path: Path) -> None:
    path = tmp_path / 'other.sqlite'
    with sqlite3.connect(path) as connection:
        connection.execute('CREATE TABLE important (value TEXT)')
        connection.execute("INSERT INTO important VALUES ('keep')")
    with pytest.raises(StorageVersionError):
        PersistentWorkflowService(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute('SELECT value FROM important').fetchone()[0] == 'keep'
        assert connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='ota_meta'").fetchone()[0] == 0


def test_mutation_lock_is_released_when_process_dies(tmp_path: Path) -> None:
    from ota_verifier.persistence.locks import execution_lock
    path = tmp_path / 'workspace.sqlite'
    result = child(path, '''from ota_verifier.persistence.locks import execution_lock
with execution_lock(path): os._exit(35)
''')
    assert result.returncode == 35, result.stderr
    with execution_lock(path, timeout=0.5):
        pass


def test_permissions_options_and_guarded_policy_are_visible_in_diff(tmp_path: Path) -> None:
    from ota_verifier.boot_models import GuardedOptions
    value, clients = incoming('clear')
    with PersistentWorkflowService(tmp_path / 'workspace.sqlite') as service:
        first = service.start(value, clients, run_id='run')
        changed, clients = incoming('authorized_rollback')
        changed = changed.model_copy(update={'boot_comparison': GuardedOptions()})
        second = service.revise('run', changed, clients)
        sections = {change.section for change in compare_revisions(first, second).changes}
        assert {'permissions', 'options', 'comparison'} <= sections
        assert second.snapshot.artifacts.status == 'simulation_violations'
        assert second.current_decision is None
