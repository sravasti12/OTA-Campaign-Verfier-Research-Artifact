"""The demo and CLI remain usable without services, credentials, or an LLM."""
import json
from pathlib import Path
from typing import Any
import pytest
from ota_verifier.cli import main
from ota_verifier.models import UnknownResult

DEMO = Path(__file__).parents[1] / 'examples' / 'parallel_campaign.json'


def test_cli_demo(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(DEMO), '--max-parallel', '2']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'feasible'
    assert result['plan']['optimal']
    assert result['plan']['makespan_ms'] == 300_000


def test_cli_blocked_demo(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(DEMO), '--max-parallel', '2', '--deadline-ms', '240000']) == 2
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'infeasible'
    assert {item['id'] for item in result['conflict']['items']} == {'shared-flash-channel', 'deadline'}


def test_cli_invalid_input(capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture) -> None:
    assert main([str(DEMO), '--max-parallel', '0']) == 1
    assert capsys.readouterr().out == ''
    assert 'Cannot load planning input' in caplog.text


def test_cli_missing_file(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    assert main([str(tmp_path / 'missing.json')]) == 1
    assert 'Cannot load planning input' in caplog.text


def test_cli_unknown(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr('ota_verifier.cli.plan_campaign', lambda *args: UnknownResult(reason='Test interruption'))
    assert main([str(DEMO)]) == 3
    assert json.loads(capsys.readouterr().out)['status'] == 'unknown'
