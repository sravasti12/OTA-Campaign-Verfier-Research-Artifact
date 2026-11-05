"""Stress CLI produces diagnostic JSON and distinct verdict exit codes."""
import json
from pathlib import Path
import pytest
from ota_verifier.cli import main

DEMO = Path(__file__).parents[1] / 'examples' / 'parallel_campaign.json'


def test_cli_stress_reports_full_fault_coverage(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(DEMO), '--max-parallel', '2', '--stress-test']) == 4
    report = json.loads(capsys.readouterr().out)
    assert report['assessment'] == 'violations'
    assert report['nominal']['assessment'] == 'passed'
    assert report['expected_fault_cases'] == len(report['cases']) == 42
    assert any(case['recovery']['status'] == 'unavailable' for case in report['cases'])


def test_cli_stress_infeasible_plan_does_not_run_simulation(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(DEMO), '--deadline-ms', '240000', '--stress-test']) == 2
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'infeasible'
    assert 'cases' not in result


def test_cli_rejects_bad_recovery_budget(capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture) -> None:
    assert main([str(DEMO), '--stress-test', '--max-recovery-states', '0']) == 1
    assert capsys.readouterr().out == ''
    assert 'Cannot load planning input' in caplog.text
