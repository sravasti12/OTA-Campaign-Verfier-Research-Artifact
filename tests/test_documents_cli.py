"""Document CLI supports offline review demos and never plans a blocked run."""
import json
from pathlib import Path
from typing import Any
import pytest
from ota_verifier.data.generate import generate_case
from ota_verifier.documents_cli import main


def _case_file(tmp_path: Path, scenario: str = 'clear') -> Path:
    path = tmp_path / f'{scenario}.case.json'
    path.write_text(generate_case(scenario).model_dump_json(), encoding='utf-8')
    return path


def test_fixture_cli_can_gate_and_plan(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _case_file(tmp_path)
    assert main([str(path), '--fixture', '--plan', '--max-parallel', '2']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['extraction']['status'] == 'ready'
    assert result['planning']['status'] == 'feasible'
    assert all(call['origin'] == 'fixture' for call in result['extraction']['calls'])


@pytest.mark.parametrize('scenario', ['ambiguous', 'unsupported'])
def test_blocked_cli_does_not_call_planner(scenario: str, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    path = _case_file(tmp_path, scenario)
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError('Blocked extraction reached planning')
    monkeypatch.setattr('ota_verifier.documents_cli.plan_campaign', forbidden)
    assert main([str(path), '--fixture', '--plan']) == 6
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'blocked'
    assert result['campaign'] is None


def test_audit_file_is_created_but_never_overwritten(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _case_file(tmp_path)
    output = tmp_path / 'run.json'
    assert main([str(path), '--fixture', '--output', str(output)]) == 0
    capsys.readouterr()
    original = output.read_bytes()
    assert json.loads(original)['status'] == 'ready'
    assert main([str(path), '--fixture', '--output', str(output)]) == 1
    assert output.read_bytes() == original


def test_no_credentials_or_model_returns_configuration_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / 'request.json'
    path.write_text(generate_case().request.model_dump_json(), encoding='utf-8')
    def absent(*args: Any, **kwargs: Any) -> Any:
        from ota_verifier.llm.client import LLMError
        raise LLMError('Set LLM_MODEL')
    monkeypatch.setattr('ota_verifier.documents_cli.ClientSettings.from_env', absent)
    assert main([str(path)]) == 1


def test_missing_document_input_returns_error(tmp_path: Path) -> None:
    assert main([str(tmp_path / 'missing.json')]) == 1
