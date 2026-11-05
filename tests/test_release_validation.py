"""Release demos and operational rehearsal stay offline and never grant approval."""
import hashlib
import json
from pathlib import Path
from typing import Any
import pytest
from ota_verifier.release_validation import build_release_pack, demo_summary, main
from ota_verifier.workflow_models import ReviewBundle


@pytest.fixture(scope='module')
def pack(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the actual release artifacts once for integrity and semantics checks."""
    path = tmp_path_factory.mktemp('release') / 'evidence'
    build_release_pack(path)
    return path


def test_release_pack_retains_pending_external_gates_and_human_review(pack: Path) -> None:
    report = json.loads((pack / 'release-validation.json').read_text(encoding='utf-8'))
    assert report['local_checks_passed']
    assert report['release_ready'] is False
    assert set(report['pending_external_checks']) == {'remote_windows_linux_ci_matrix', 'live_oidc_login_roles_logout'}
    for name in ('parallel', 'intermediate_conflict', 'guarded_recovery'):
        bundle = ReviewBundle.model_validate_json((pack / f'{name}.json').read_text(encoding='utf-8'))
        assert bundle.current_decision is None
        assert bundle.review_state == 'awaiting_review'
        assert demo_summary(name, bundle)['checks_passed']


def test_all_release_artifact_hashes_match(pack: Path) -> None:
    index = json.loads((pack / 'artifact-index.json').read_text(encoding='utf-8'))
    for name, expected in index['files'].items():
        assert hashlib.sha256((pack / name).read_bytes()).hexdigest() == expected, name


def test_rehearsal_keeps_receipts_and_restore_evidence(pack: Path) -> None:
    result = json.loads((pack / 'release-validation.json').read_text(encoding='utf-8'))['recovery_rehearsal']
    assert result['receipts_reused'] and result['restored_export_identical']
    assert result['human_review_still_required']
    assert result['verification']['decisions'] == 0
    assert result['storage_schema'] == 2


def test_offline_pack_cannot_call_a_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError('Release rehearsal tried a live model')
    monkeypatch.setattr('ota_verifier.llm.client.LLMClient.generate_json', forbidden)
    assert build_release_pack(tmp_path / 'offline')['local_checks_passed']


def test_existing_output_is_never_overwritten(pack: Path) -> None:
    original = (pack / 'release-validation.json').read_bytes()
    with pytest.raises(FileExistsError):
        build_release_pack(pack)
    assert (pack / 'release-validation.json').read_bytes() == original


def test_cli_reports_existing_destination(pack: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as error:
        main(['--output', str(pack)])
    assert error.value.code == 1
    assert 'new writable directory' in capsys.readouterr().err
