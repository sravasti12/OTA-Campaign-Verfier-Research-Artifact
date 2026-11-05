"""Paired-policy evidence keeps regressions, unknowns, and denominators honest."""
import json
from typing import Any
import pytest
from pydantic import ValidationError
from ota_verifier.boot_comparison import PolicyComparison, compare_boot_policies
from ota_verifier.boot_models import GuardedOptions
from ota_verifier.simulation_models import SimulationOptions
from ota_verifier.simulator import stress_test
from test_planner import add_constraint, feasible, load_campaign
from test_simulator import authorized_data


def test_policies_compare_identical_plan_and_all_shared_cases() -> None:
    data = authorized_data((1,))
    campaign, plan = load_campaign(data), feasible(data)
    original = stress_test(campaign, plan)
    comparison = compare_boot_policies(campaign, plan, baseline_report=original)
    assert comparison.baseline.model_dump_json() == original.model_dump_json()
    assert comparison.guarded.plan == plan
    assert comparison.baseline.assessment == 'violations'
    assert comparison.guarded.assessment == 'passed'
    assert len(comparison.shared_cases) == 14
    assert len(comparison.guarded.cases) == 16
    assert len(comparison.guarded_only_indices) == 2
    assert comparison.improved_cases == 1
    row = next(row for row in comparison.shared_cases if row.fault.kind == 'boot_failure')
    assert row.change == 'improved'
    assert row.removed_invariants == ('bootable_image',)
    assert PolicyComparison.model_validate_json(comparison.model_dump_json()) == comparison


def test_availability_cycle_is_reported_as_a_regression_not_hidden() -> None:
    data = authorized_data()
    add_constraint(data, 'requires', 'a-needs-b', ecu='a', version_spec='>=1', needs='b', needs_version_spec='>=1')
    add_constraint(data, 'requires', 'b-needs-a', ecu='b', version_spec='>=1', needs='a', needs_version_spec='>=1')
    comparison = compare_boot_policies(load_campaign(data), feasible(data))
    row = next(row for row in comparison.shared_cases if row.fault.ecu_id == 'a'
               and row.fault.kind == 'power_loss' and row.fault.stage == 'erase' and row.fault.when == 'before')
    assert row.baseline_assessment == 'passed'
    assert row.guarded_assessment == 'violations'
    assert row.change == 'regressed'
    assert comparison.regressed_cases > 0
    case = comparison.guarded.cases[row.guarded_index]
    assert 'dependency_unavailable' in {blocker.code for blocker in case.guard_blockers + case.recovery.blockers}
    assert not any(finding.invariant == 'compatible_versions' for finding in case.findings)


def test_unknown_recovery_pairs_are_not_scored_as_proven_improvements() -> None:
    data = authorized_data((1,))
    comparison = compare_boot_policies(load_campaign(data), feasible(data), SimulationOptions(max_recovery_states=1))
    uncertain = [row for row in comparison.shared_cases if 'inconclusive' in (row.baseline_assessment, row.guarded_assessment)]
    assert uncertain
    assert all(row.change == 'inconclusive' for row in uncertain)
    assert comparison.inconclusive_cases == len(uncertain)
    assert any(comparison.guarded.cases[index].assessment == 'inconclusive' for index in comparison.guarded_only_indices)


@pytest.mark.parametrize('mutation', ['summary', 'row', 'missing_pair', 'hidden_extra'])
def test_comparison_rejects_tampered_improvement_claims(mutation: str) -> None:
    data = authorized_data((1,))
    comparison = compare_boot_policies(load_campaign(data), feasible(data))
    raw = json.loads(comparison.model_dump_json())
    if mutation == 'summary':
        raw['improved_cases'] += 1
    elif mutation == 'row':
        raw['shared_cases'][0]['change'] = 'improved'
    elif mutation == 'missing_pair':
        raw['shared_cases'].pop()
    else:
        raw['guarded_only_indices'].pop()
    with pytest.raises(ValidationError):
        PolicyComparison.model_validate_json(json.dumps(raw))


def test_recovery_limits_and_supplied_baseline_cannot_differ() -> None:
    data = authorized_data((1,))
    campaign, plan = load_campaign(data), feasible(data)
    baseline = stress_test(campaign, plan, SimulationOptions(max_recovery_states=1))
    with pytest.raises(ValueError, match='differs'):
        compare_boot_policies(campaign, plan, baseline_report=baseline)


def test_comparison_is_offline_and_never_replans(monkeypatch: pytest.MonkeyPatch) -> None:
    data = authorized_data((1,))
    campaign, plan = load_campaign(data), feasible(data)
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError('Comparison attempted an LLM or solver call')
    monkeypatch.setattr('ota_verifier.llm.client.LLMClient.generate_json', forbidden)
    monkeypatch.setattr('ota_verifier.planner.plan_campaign', forbidden)
    assert compare_boot_policies(campaign, plan).guarded.assessment == 'passed'
