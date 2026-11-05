"""Parallel A/B transitions, one-fault effects, and end-to-end bounded coverage."""
import json
from typing import Any
import pytest
from pydantic import ValidationError
from ota_verifier.ab import get_ecu
from ota_verifier.invariants import check_state
from ota_verifier.models import Campaign, Plan
from ota_verifier.simulation_models import FaultSpec, SimulationOptions, SimulationResult, StressReport
from ota_verifier.simulator import enumerate_faults, simulate_plan, stress_test
from test_planner import add_constraint, campaign_data, feasible, load_campaign


def authorized_data(durations: tuple[float, ...] = (3, 3)) -> dict[str, Any]:
    """Explicitly authorize restoring the original versions for this test campaign."""
    data = campaign_data(durations)
    data['downgrade_authorizations'] = [dict(ecu_id=ecu['id'], version='1', authorized_by='reviewer',
        reason='Fault simulation recovery') for ecu in data['ecus']]
    return data


def test_nominal_parallel_trace_has_actual_inactive_writes() -> None:
    data = campaign_data()
    campaign = load_campaign(data)
    plan = feasible(data)
    result = simulate_plan(campaign, plan)
    assert result.status == 'completed'
    assert result.assessment == 'passed'
    assert result.findings == ()
    assert len(result.trace) == 1 + 5 * len(plan.steps)
    assert result.trace[-1].state == plan.states[-1]
    assert any(event.writing_ecus == ('a', 'b') for event in result.trace)
    erase = next(event for event in result.trace if event.stage == 'erase')
    assert get_ecu(erase.state, erase.ecu_id).slot_b.valid is False
    assert get_ecu(erase.state, erase.ecu_id).active_slot == 'A'
    verify = next(event for event in result.trace if event.stage == 'verify')
    assert get_ecu(verify.state, verify.ecu_id).slot_b.valid is True
    assert get_ecu(verify.state, verify.ecu_id).active_slot == 'A'
    assert [event.time_ms for event in result.trace] == sorted(event.time_ms for event in result.trace)
    assert SimulationResult.model_validate_json(result.model_dump_json()) == result


def test_tied_completions_follow_dependency_order() -> None:
    data = campaign_data()
    add_constraint(data, 'requires', 'a-needs-b', ecu='a', version_spec='>=2', needs='b', needs_version_spec='>=2')
    campaign = load_campaign(data)
    result = simulate_plan(campaign, feasible(data))
    assert [event.ecu_id for event in result.trace if event.stage == 'activate'] == ['b', 'a']
    assert all(check_state(campaign, event.state) == () for event in result.trace)


def test_finish_events_precede_new_starts_at_same_time() -> None:
    data = campaign_data()
    add_constraint(data, 'order', 'a-first', before='a', after='b')
    result = simulate_plan(load_campaign(data), feasible(data))
    at_boundary = [(event.ecu_id, event.stage) for event in result.trace if event.time_ms == 180_000]
    assert at_boundary == [('a', 'verify'), ('a', 'activate'), ('a', 'boot'), ('b', 'erase')]


def test_one_millisecond_write_still_erases_before_writing() -> None:
    data = campaign_data((0.00001,))
    result = simulate_plan(load_campaign(data), feasible(data))
    assert [e.stage for e in result.trace] == ['initial', 'erase', 'write', 'verify', 'activate', 'boot']
    assert [e.time_ms for e in result.trace] == [0, 0, 0, 1, 1, 1]


def test_power_loss_invalidates_every_concurrent_write() -> None:
    data = campaign_data()
    campaign = load_campaign(data)
    result = simulate_plan(campaign, feasible(data), FaultSpec(ecu_id='a', stage='write', kind='power_loss'))
    fault = next(event for event in result.trace if event.stage == 'fault')
    assert fault.writing_ecus == ()
    assert all(ecu.slot_b is not None and not ecu.slot_b.valid for ecu in fault.state.ecus)
    assert all(ecu.active_slot == 'A' and ecu.active_image.valid for ecu in fault.state.ecus)
    assert result.recovery.status == 'available'
    assert result.recovery.steps == ()
    assert result.assessment == 'passed'


def test_corruption_is_detected_at_verification_before_activation() -> None:
    data = campaign_data()
    result = simulate_plan(load_campaign(data), feasible(data),
        FaultSpec(ecu_id='a', stage='write', when='after', kind='write_corruption'))
    assert result.status == 'failed'
    assert result.assessment == 'passed'
    assert not any(event.stage == 'activate' and event.ecu_id == 'a' for event in result.trace)
    detection = next(event for event in result.trace if event.stage == 'verify' and event.ecu_id == 'a')
    assert 'Corrupted' in detection.message
    assert get_ecu(detection.state, 'a').slot_b.valid is False


def test_verification_failure_retains_valid_old_image() -> None:
    data = campaign_data()
    result = simulate_plan(load_campaign(data), feasible(data),
        FaultSpec(ecu_id='a', stage='verify', kind='verification_failure'))
    assert result.assessment == 'passed'
    assert get_ecu(result.trace[-1].state, 'a').active_image.version == '1'


def test_activation_failure_preserves_verified_staged_image() -> None:
    data = campaign_data()
    result = simulate_plan(load_campaign(data), feasible(data),
        FaultSpec(ecu_id='a', stage='activate', kind='activation_failure'))
    fault = next(event for event in result.trace if event.stage == 'fault')
    ecu = get_ecu(fault.state, 'a')
    assert ecu.active_slot == 'A'
    assert ecu.slot_b.valid
    assert result.assessment == 'passed'


def test_boot_failure_retains_historical_violation_after_successful_recovery() -> None:
    data = authorized_data()
    result = simulate_plan(load_campaign(data), feasible(data),
        FaultSpec(ecu_id='a', stage='boot', kind='boot_failure'))
    assert result.recovery.status == 'available'
    assert result.assessment == 'violations'
    assert 'bootable_image' in {finding.invariant for finding in result.findings}
    assert all(ecu.active_image.valid for ecu in result.trace[-1].state.ecus)
    assert get_ecu(result.trace[-1].state, 'a').active_image.version == '1'


def test_unauthorized_rollback_is_reported_not_performed() -> None:
    data = campaign_data()
    result = simulate_plan(load_campaign(data), feasible(data),
        FaultSpec(ecu_id='a', stage='activate', when='after', kind='power_loss'))
    assert result.recovery.status == 'unavailable'
    assert result.assessment == 'violations'
    assert any(finding.violation.code == 'rollback_unavailable' for finding in result.findings)
    assert not any(event.stage == 'recover' for event in result.trace)
    assert get_ecu(result.trace[-1].state, 'a').active_image.version == '2'
    assert 'unauthorized_downgrade' in {v.code for v in result.recovery.blockers}


def test_authorized_recovery_is_executed_as_recorded() -> None:
    data = authorized_data()
    result = simulate_plan(load_campaign(data), feasible(data),
        FaultSpec(ecu_id='a', stage='activate', when='after', kind='power_loss'))
    assert result.recovery.status == 'available'
    assert result.assessment == 'passed'
    assert result.trace[-1].stage == 'recover'
    assert result.trace[-1].state == result.recovery.states[-1]
    assert get_ecu(result.trace[-1].state, 'a').active_image.version == '1'


def test_recovery_limit_is_inconclusive_without_false_violation() -> None:
    data = authorized_data()
    result = simulate_plan(load_campaign(data), feasible(data),
        FaultSpec(ecu_id='a', stage='activate', when='after', kind='power_loss'),
        SimulationOptions(max_recovery_states=1))
    assert result.recovery.status == 'unknown'
    assert result.assessment == 'inconclusive'
    assert result.findings == ()


def test_single_fault_sweep_is_complete_deterministic_and_isolated() -> None:
    data = authorized_data((1,))
    campaign = load_campaign(data)
    plan = feasible(data)
    original = campaign.model_dump_json()
    faults = enumerate_faults(plan)
    assert len(faults) == 14
    assert len(set(faults)) == 14
    report = stress_test(campaign, plan)
    assert report.expected_fault_cases == len(report.cases) == 14
    assert tuple(case.fault for case in report.cases) == faults
    assert all(case.status == 'failed' for case in report.cases)
    assert report.nominal.assessment == 'passed'
    assert all(case.assessment == ('violations' if case.fault.kind == 'boot_failure' else 'passed')
               for case in report.cases)
    assert campaign.model_dump_json() == original
    assert all(case.trace[0].state == campaign.initial_state for case in report.cases)
    assert StressReport.model_validate_json(report.model_dump_json()) == report
    assert report.model_dump_json() == stress_test(campaign, plan).model_dump_json()


def test_fault_sweep_covers_every_parallel_ecu_and_each_stage_boundary() -> None:
    data = authorized_data((3, 2, 4))
    report = stress_test(load_campaign(data), feasible(data, max_parallel=2))
    assert report.expected_fault_cases == len(report.cases) == 42
    assert all(sum(case.fault.ecu_id == ecu for case in report.cases) == 14 for ecu in ('a', 'b', 'c'))
    assert report.assessment == 'violations'  # Boot faults are observable violations under the strict invariant.


def test_noop_campaign_has_no_fault_cases() -> None:
    data = campaign_data()
    for ecu in data['ecus']:
        ecu['target_version'] = '1'
    report = stress_test(load_campaign(data), feasible(data))
    assert report.cases == ()
    assert report.expected_fault_cases == 0
    assert report.assessment == 'passed'
    assert len(report.nominal.trace) == 1


def test_simulator_does_not_call_planner(monkeypatch: pytest.MonkeyPatch) -> None:
    data = campaign_data()
    campaign = load_campaign(data)
    plan = feasible(data)

    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError('Simulator must not replan')

    monkeypatch.setattr('ota_verifier.planner.plan_campaign', forbidden)
    assert simulate_plan(campaign, plan).assessment == 'passed'


def test_invalid_plan_and_unknown_fault_ecu_rejected() -> None:
    data = campaign_data()
    campaign = load_campaign(data)
    plan = feasible(data)
    with pytest.raises(ValueError, match='scheduled ECU'):
        simulate_plan(campaign, plan, FaultSpec(ecu_id='unknown', stage='write', kind='power_loss'))
    raw = json.loads(plan.model_dump_json())
    raw['steps'][0]['write_slot'] = 'A'
    bad = Plan.model_validate_json(json.dumps(raw))
    with pytest.raises(ValueError, match='invalid plan'):
        simulate_plan(campaign, bad)


@pytest.mark.parametrize(('kind', 'stage', 'when'), [
    ('boot_failure', 'erase', 'before'), ('write_corruption', 'write', 'before'),
    ('verification_failure', 'verify', 'after'), ('activation_failure', 'activate', 'after'),
])
def test_reject_undefined_fault_boundaries(kind: str, stage: str, when: str) -> None:
    with pytest.raises(ValidationError):
        FaultSpec(ecu_id='a', kind=kind, stage=stage, when=when)


def test_active_b_authorized_downgrade_can_recover_to_newer_original() -> None:
    data = campaign_data((1,))
    data['ecus'][0].update(current_version='2', target_version='1')
    data['initial_state']['ecus'][0].update(slot_a=None, slot_b=dict(version='2', valid=True), active_slot='B')
    data['downgrade_authorizations'] = [dict(ecu_id='a', version='1', authorized_by='reviewer', reason='Exercise')]
    campaign = load_campaign(data)
    plan = feasible(data)
    nominal = simulate_plan(campaign, plan)
    final = get_ecu(nominal.trace[-1].state, 'a')
    assert final.active_slot == 'A'
    assert final.active_image.version == '1'
    assert final.slot_b.version == '2'
    faulted = simulate_plan(campaign, plan, FaultSpec(ecu_id='a', stage='activate', when='after', kind='power_loss'))
    assert faulted.assessment == 'passed'
    assert faulted.recovery.status == 'available'
    assert faulted.recovery.steps[0].to_version == '2'
    assert get_ecu(faulted.trace[-1].state, 'a').active_slot == 'B'
