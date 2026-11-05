"""Guarded boot prevents exposure without hiding authorization or compatibility failures."""
import json
from typing import Any
import pytest
from pydantic import ValidationError
from ota_verifier.ab import get_ecu
from ota_verifier.boot import (boot_metadata, change_boot, check_guarded_state, guarded_boot,
                               initial_boot_state, power_loss, set_image)
from ota_verifier.boot_models import GuardedFaultSpec, GuardedOptions, GuardedStressReport
from ota_verifier.boot_recovery import check_guarded_recovery, find_guarded_recovery
from ota_verifier.guarded_simulator import enumerate_guarded_faults, simulate_guarded, stress_guarded
from ota_verifier.models import Image
from ota_verifier.simulation_models import FaultSpec, SimulationOptions
from ota_verifier.simulator import enumerate_faults, simulate_plan
from test_planner import add_constraint, campaign_data, feasible, load_campaign
from test_simulator import authorized_data


def test_nominal_trial_becomes_effective_before_atomic_confirmation() -> None:
    data = campaign_data((1,))
    run = simulate_guarded(load_campaign(data), feasible(data))
    activation = next(event for event in run.trace if event.stage == 'activate')
    metadata = boot_metadata(activation.snapshot, 'a')
    assert not metadata.available and metadata.running_slot is None
    assert metadata.candidate_slot == 'B' and metadata.confirmed_slot == 'A'
    assert get_ecu(activation.snapshot.state, 'a').active_image.version == '1'
    boot = next(event for event in run.trace if event.stage == 'boot')
    assert boot_metadata(boot.snapshot, 'a').confirmed_slot == 'A'
    assert get_ecu(boot.snapshot.state, 'a').active_image.version == '2'
    confirmed = next(event for event in run.trace if event.stage == 'confirm')
    assert boot_metadata(confirmed.snapshot, 'a').confirmed_slot == 'B'
    assert run.assessment == 'passed'


@pytest.mark.parametrize('attempts', [1, 2, 3])
def test_boot_failure_retains_old_version_without_implicit_downgrade(attempts: int) -> None:
    data = campaign_data((1,))
    campaign, plan = load_campaign(data), feasible(data)
    fault = FaultSpec(ecu_id='a', stage='boot', kind='boot_failure')
    baseline = simulate_plan(campaign, plan, fault)
    guarded = simulate_guarded(campaign, plan, fault, guarded_options=GuardedOptions(max_trial_attempts=attempts))
    assert baseline.assessment == 'violations'
    assert guarded.assessment == 'passed'
    assert guarded.recovery.status == 'available'
    assert len([event for event in guarded.trace if event.stage == 'boot_attempt']) == attempts
    assert all(get_ecu(event.snapshot.state, 'a').active_image.version == '1' for event in guarded.trace)
    failed = next(event for event in guarded.trace if event.stage == 'fault')
    assert get_ecu(failed.snapshot.state, 'a').slot_b.valid  # Integrity passed; boot health failed.
    assert boot_metadata(failed.snapshot, 'a').health_b == 'failed'
    assert boot_metadata(guarded.trace[-1].snapshot, 'a').attempts_used == attempts


@pytest.mark.parametrize('when', ['before', 'after'])
def test_confirmation_power_loss_uses_the_correct_durable_pointer(when: str) -> None:
    data = authorized_data((1,))
    result = simulate_guarded(load_campaign(data), feasible(data),
        GuardedFaultSpec(ecu_id='a', stage='confirm', kind='power_loss', when=when))
    fault = next(event for event in result.trace if event.stage == 'fault')
    assert boot_metadata(fault.snapshot, 'a').confirmed_slot == ('A' if when == 'before' else 'B')
    assert not boot_metadata(fault.snapshot, 'a').available
    assert boot_metadata(fault.snapshot, 'a').candidate_slot is None
    reboot = next(event for event in result.trace if event.stage == 'reboot')
    assert get_ecu(reboot.snapshot.state, 'a').active_image.version == ('1' if when == 'before' else '2')
    assert result.assessment == 'passed'
    assert boot_metadata(fault.snapshot, 'a').attempts_used == 1


def test_successful_unconfirmed_trial_does_not_bypass_downgrade_authorization() -> None:
    data = campaign_data((1,))
    result = simulate_guarded(load_campaign(data), feasible(data),
        GuardedFaultSpec(ecu_id='a', stage='confirm', kind='power_loss', when='before'))
    assert result.assessment == 'violations'
    assert result.recovery.status == 'unavailable'
    assert 'unauthorized_downgrade' in {blocker.code for blocker in result.guard_blockers + result.recovery.blockers}
    fault_index = next(index for index, event in enumerate(result.trace) if event.stage == 'fault')
    assert all(get_ecu(event.snapshot.state, 'a').active_image.version == '2' for event in result.trace[fault_index:])
    assert any(finding.invariant == 'rollback_path' for finding in result.findings)


def test_rebooting_ecus_are_unavailable_but_versions_still_count() -> None:
    data = authorized_data()
    add_constraint(data, 'requires', 'a-needs-b', ecu='a', version_spec='>=2', needs='b', needs_version_spec='>=2')
    campaign = load_campaign(data)
    final = simulate_guarded(campaign, feasible(data)).trace[-1].snapshot
    offline = power_loss(final)
    assert all(not item.available and item.running_slot is None for item in offline.boot)
    assert check_guarded_state(campaign, offline) == ()
    candidate, blockers = guarded_boot(campaign, offline, 'a', 'B')
    assert candidate is None
    assert 'dependency_unavailable' in {blocker.code for blocker in blockers}
    provider, blockers = guarded_boot(campaign, offline, 'b', 'B', confirm=True)
    assert provider is not None and not blockers
    dependent, blockers = guarded_boot(campaign, provider, 'a', 'B', confirm=True)
    assert dependent is not None and not blockers
    unsafe, blockers = guarded_boot(campaign, final, 'b', 'A', confirm=True)
    assert unsafe is None
    assert any(blocker.code == 'incompatible_versions' and blocker.constraint_id == 'a-needs-b' for blocker in blockers)


def test_coordinated_recovery_orders_dependent_before_provider() -> None:
    data = authorized_data()
    add_constraint(data, 'requires', 'a-needs-b', ecu='a', version_spec='>=2', needs='b', needs_version_spec='>=2')
    campaign = load_campaign(data)
    final = simulate_guarded(campaign, feasible(data)).trace[-1].snapshot
    recovery = find_guarded_recovery(campaign, final)
    assert recovery.status == 'available'
    assert [step.ecu_id for step in recovery.steps] == ['a', 'b']
    assert check_guarded_recovery(campaign, final, recovery) == ()


def test_exhausted_recovery_search_is_inconclusive() -> None:
    data = authorized_data((1,))
    run = simulate_guarded(load_campaign(data), feasible(data),
        GuardedFaultSpec(ecu_id='a', stage='confirm', kind='power_loss', when='after'),
        SimulationOptions(max_recovery_states=1))
    assert run.recovery.status == 'unknown'
    assert run.assessment == 'inconclusive'
    assert run.findings == ()


def test_integrity_and_boot_health_are_independent_and_both_enforced() -> None:
    data = campaign_data((1,))
    campaign = load_campaign(data)
    snapshot = initial_boot_state(campaign)
    unhealthy = change_boot(snapshot, 'a', health_a='failed')
    assert 'unhealthy_running_image' in {finding.code for finding in check_guarded_state(campaign, unhealthy)}
    corrupted = set_image(snapshot, 'a', 'A', Image(version='1', valid=False), health='passed')
    assert 'invalid_running_image' in {finding.code for finding in check_guarded_state(campaign, corrupted)}
    for bad in (unhealthy, corrupted):
        candidate, blockers = guarded_boot(campaign, bad, 'a', 'A')
        assert candidate is None
        assert blockers[0].code == 'boot_image_unusable'


def test_recovery_does_not_fabricate_healthy_original_images() -> None:
    data = authorized_data((1,))
    campaign = load_campaign(data)
    final = simulate_guarded(campaign, feasible(data)).trace[-1].snapshot
    bad_original = change_boot(final, 'a', health_a='failed')
    result = find_guarded_recovery(campaign, bad_original)
    assert result.status == 'unavailable'
    assert 'boot_image_unusable' in {blocker.code for blocker in result.blockers}


def test_sweep_has_all_common_faults_and_explicit_confirmation_coverage() -> None:
    data = authorized_data((1,))
    campaign, plan = load_campaign(data), feasible(data)
    report = stress_guarded(campaign, plan)
    assert len(report.cases) == 16
    assert report.assessment == 'passed'
    shared = {fault.model_dump_json() for fault in enumerate_faults(plan)}
    actual = {case.fault.model_dump_json() for case in report.cases}
    assert shared <= actual
    assert len(actual - shared) == 2
    assert all(case.status == 'failed' for case in report.cases)
    assert GuardedStressReport.model_validate_json(report.model_dump_json()) == report
    assert report.model_dump_json() == stress_guarded(campaign, plan).model_dump_json()


def test_baseline_fault_schema_and_coverage_are_unchanged() -> None:
    with pytest.raises(ValidationError):
        FaultSpec(ecu_id='a', stage='confirm', kind='power_loss')
    with pytest.raises(ValidationError):
        GuardedFaultSpec(ecu_id='a', stage='confirm', kind='boot_failure')
    data = campaign_data((1,))
    assert len(enumerate_faults(feasible(data))) == 14


def test_guarded_simulator_never_replans_or_calls_a_model(monkeypatch: pytest.MonkeyPatch) -> None:
    data = authorized_data((1,))
    campaign, plan = load_campaign(data), feasible(data)
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError('Guarded simulation invoked a solver or LLM')
    monkeypatch.setattr('ota_verifier.planner.plan_campaign', forbidden)
    monkeypatch.setattr('ota_verifier.llm.client.LLMClient.generate_json', forbidden)
    assert stress_guarded(campaign, plan).assessment == 'passed'


def test_noop_guarded_campaign_has_zero_fault_cases() -> None:
    data = campaign_data((1,))
    data['ecus'][0]['target_version'] = '1'
    report = stress_guarded(load_campaign(data), feasible(data))
    assert report.expected_fault_cases == 0
    assert report.cases == ()
    assert report.assessment == 'passed'


def test_report_rejects_attempt_budget_or_coverage_forgery() -> None:
    data = authorized_data((1,))
    report = stress_guarded(load_campaign(data), feasible(data))
    raw = json.loads(report.model_dump_json())
    raw['guarded_options']['max_trial_attempts'] = 1
    with pytest.raises(ValidationError, match='attempts exceed'):
        GuardedStressReport.model_validate_json(json.dumps(raw))
    raw = json.loads(report.model_dump_json())
    raw['cases'].pop()
    with pytest.raises(ValidationError, match='coverage'):
        GuardedStressReport.model_validate_json(json.dumps(raw))
