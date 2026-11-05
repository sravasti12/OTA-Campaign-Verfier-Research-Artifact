"""Headless comparison preserves legacy planning/stress CLI behavior."""
import json
from pathlib import Path
import pytest
from ota_verifier.cli import main
from test_planner import load_campaign
from test_simulator import authorized_data


def test_comparison_cli_reports_both_policies_and_explicit_coverage(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / 'campaign.json'
    path.write_text(load_campaign(authorized_data((1,))).model_dump_json(), encoding='utf-8')
    assert main([str(path), '--compare-boot-policies']) == 4  # Baseline still has a violation.
    report = json.loads(capsys.readouterr().out)
    assert report['baseline']['assessment'] == 'violations'
    assert report['guarded']['assessment'] == 'passed'
    assert len(report['shared_cases']) == 14
    assert len(report['guarded_only_indices']) == 2


def test_invalid_trial_budget_is_an_input_error(tmp_path: Path) -> None:
    path = tmp_path / 'campaign.json'
    path.write_text(load_campaign(authorized_data((1,))).model_dump_json(), encoding='utf-8')
    assert main([str(path), '--compare-boot-policies', '--trial-attempts', '0']) == 1
