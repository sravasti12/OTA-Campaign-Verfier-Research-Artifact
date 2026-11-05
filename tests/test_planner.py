"""Parallel planning integration tests and independent replay checks."""
import json
from pathlib import Path
from typing import Any
import pytest
import z3
from ota_verifier.models import (
    Campaign, FeasibleResult, InfeasibleResult, Plan, PlanningOptions, UnknownResult,
)
from ota_verifier.planner import plan_campaign
from ota_verifier.scheduling import duration_ms, validate_plan


def campaign_data(durations: tuple[float, ...] = (3, 3)) -> dict[str, Any]:
    """Build a small complete campaign with independently updatable ECUs."""
    names = tuple(chr(ord('a') + i) for i in range(len(durations)))
    return {'id': 'parallel-demo', 'ecus': [dict(id=name, current_version='1', target_version='2',
            flash_minutes=duration) for name, duration in zip(names, durations)],
            'initial_state': {'ecus': [dict(ecu_id=name, slot_a=dict(version='1', valid=True),
                slot_b=None, active_slot='A') for name in names], 'battery_percent': 80, 'ignition': 'off'},
            'constraints': []}


def add_constraint(data: dict[str, Any], kind: str, key: str, **fields: Any) -> None:
    """Add a traceable handwritten requirement."""
    data['constraints'].append(dict(type=kind, id=key, source_document_id='manual',
        source_text=f'Requirement {key}.', **fields))


def load_campaign(data: dict[str, Any]) -> Campaign:
    """Validate JSON at the public boundary."""
    return Campaign.model_validate_json(json.dumps(data))


def feasible(data: dict[str, Any], **options: Any) -> Plan:
    """Require a replay-validated optimal plan from a small input."""
    campaign = load_campaign(data)
    result = plan_campaign(campaign, PlanningOptions(**options))
    assert isinstance(result, FeasibleResult), result
    assert result.plan.optimal
    assert validate_plan(campaign, result.plan) == ()
    assert Plan.model_validate_json(result.plan.model_dump_json()) == result.plan
    return result.plan


def test_parallel_writes_reduce_makespan() -> None:
    plan = feasible(campaign_data((3, 5, 2)))
    assert plan.makespan_ms == 5 * 60_000
    assert all(step.start_ms == 0 for step in plan.steps)
    assert [step.ecu_id for step in plan.steps] == ['c', 'a', 'b']


def test_capacity_changes_optimal_schedule() -> None:
    data = campaign_data((3, 2, 2))
    assert feasible(data, max_parallel=2).makespan_ms == 4 * 60_000
    assert feasible(data, max_parallel=1).makespan_ms == 7 * 60_000


def test_mutex_and_touching_intervals() -> None:
    data = campaign_data((3, 2, 2))
    add_constraint(data, 'mutex', 'shared-bus', ecus=['a', 'b'])
    plan = feasible(data)
    assert plan.makespan_ms == 5 * 60_000
    steps = {s.ecu_id: s for s in plan.steps}
    assert steps['a'].end_ms <= steps['b'].start_ms or steps['b'].end_ms <= steps['a'].start_ms
    assert steps['c'].start_ms == 0


def test_order_is_finish_before_start() -> None:
    data = campaign_data()
    add_constraint(data, 'order', 'a-first', before='a', after='b')
    plan = feasible(data)
    assert plan.makespan_ms == 6 * 60_000
    assert plan.steps[0].end_ms == plan.steps[1].start_ms


def test_requires_allows_parallel_writes_with_ordered_tied_activations() -> None:
    data = campaign_data()
    add_constraint(data, 'requires', 'a-needs-b', ecu='a', version_spec='>=2', needs='b', needs_version_spec='>=2')
    plan = feasible(data)
    assert plan.makespan_ms == 3 * 60_000
    assert [s.ecu_id for s in plan.steps] == ['b', 'a']
    assert plan.steps[0].end_ms == plan.steps[1].end_ms
    assert plan.states[1].ecus[0].active_image.version == '1'
    assert plan.states[1].ecus[1].active_image.version == '2'


@pytest.mark.parametrize('fixture', ['compatible', 'order_sensitive', 'recovery_trap'])
def test_existing_feasible_benchmarks(fixture: str) -> None:
    path = Path(__file__).parent / 'fixtures' / f'{fixture}.json'
    data = json.loads(path.read_text(encoding='utf-8'))['campaign']
    feasible(data)


def test_impossible_direct_does_not_gain_atomic_activation() -> None:
    path = Path(__file__).parent / 'fixtures' / 'impossible_direct.json'
    data = json.loads(path.read_text(encoding='utf-8'))['campaign']
    result = plan_campaign(load_campaign(data))
    assert isinstance(result, InfeasibleResult)
    assert result.conflict.subset_minimal
    ids = {item.id for item in result.conflict.items}
    assert ids == {'brake-needs-gateway', 'gateway-needs-brake'}
    for item in result.conflict.items:
        assert item.source_document_id == 'release-2'
        assert item.source_text
        reduced = dict(data, constraints=[c for c in data['constraints'] if c['id'] != item.id])
        assert isinstance(plan_campaign(load_campaign(reduced)), FeasibleResult)


def test_deadline_mutex_conflict_is_minimal_and_traceable() -> None:
    data = campaign_data()
    add_constraint(data, 'mutex', 'shared-bus', ecus=['a', 'b'])
    result = plan_campaign(load_campaign(data), PlanningOptions(deadline_ms=180_000))
    assert isinstance(result, InfeasibleResult)
    assert result.conflict.subset_minimal
    assert {(item.kind, item.id) for item in result.conflict.items} == {
        ('constraint', 'shared-bus'), ('resource', 'deadline')}
    feasible(data)
    feasible(dict(data, constraints=[]), deadline_ms=180_000)


def test_capacity_deadline_conflict() -> None:
    result = plan_campaign(load_campaign(campaign_data()), PlanningOptions(max_parallel=1, deadline_ms=180_000))
    assert isinstance(result, InfeasibleResult)
    assert {item.id for item in result.conflict.items} == {'max_parallel', 'deadline'}
    feasible(campaign_data(), max_parallel=1, deadline_ms=360_000)


@pytest.mark.parametrize(('ignition', 'battery'), [('on', 80), ('off', 29)])
def test_environment_failure(ignition: str, battery: int) -> None:
    data = campaign_data()
    add_constraint(data, 'precondition', 'parked-charged', ecu='a', ignition='off', minimum_battery_percent=30)
    data['initial_state']['ignition'] = ignition
    data['initial_state']['battery_percent'] = battery
    result = plan_campaign(load_campaign(data))
    assert isinstance(result, InfeasibleResult)
    assert [item.id for item in result.conflict.items] == ['parked-charged']


def test_environment_boundary() -> None:
    data = campaign_data()
    add_constraint(data, 'precondition', 'parked-charged', ecu='a', ignition='off', minimum_battery_percent=30)
    data['initial_state']['battery_percent'] = 30
    feasible(data)


@pytest.mark.parametrize('stage', ['initial', 'target'])
def test_incompatible_endpoints_rejected(stage: str) -> None:
    data = campaign_data()
    add_constraint(data, 'requires', 'bad-state', ecu='a', version_spec='>=1' if stage == 'initial' else '>=2',
                   needs='b', needs_version_spec='>=3')
    result = plan_campaign(load_campaign(data))
    assert isinstance(result, InfeasibleResult)
    assert [item.id for item in result.conflict.items] == ['bad-state']


def test_cyclic_order_conflict() -> None:
    data = campaign_data()
    add_constraint(data, 'order', 'a-first', before='a', after='b')
    add_constraint(data, 'order', 'b-first', before='b', after='a')
    result = plan_campaign(load_campaign(data))
    assert isinstance(result, InfeasibleResult)
    assert {item.id for item in result.conflict.items} == {'a-first', 'b-first'}


@pytest.mark.parametrize('permission', [None, ('b', '1'), ('a', '0')])
def test_downgrade_requires_matching_permission(permission: tuple[str, str] | None) -> None:
    data = campaign_data()
    data['ecus'][0].update(current_version='2', target_version='1')
    data['initial_state']['ecus'][0]['slot_a']['version'] = '2'
    if permission:
        data['downgrade_authorizations'] = [dict(ecu_id=permission[0], version=permission[1],
            authorized_by='reviewer', reason='Simulation recovery exercise')]
    result = plan_campaign(load_campaign(data))
    assert isinstance(result, InfeasibleResult)
    assert [item.id for item in result.conflict.items] == ['downgrade:a']


def test_authorized_downgrade_and_active_b() -> None:
    data = campaign_data()
    data['ecus'][0].update(current_version='2', target_version='1')
    data['initial_state']['ecus'][0].update(slot_a=None, slot_b=dict(version='2', valid=True), active_slot='B')
    data['downgrade_authorizations'] = [dict(ecu_id='a', version='1.0', authorized_by='reviewer', reason='Exercise')]
    plan = feasible(data)
    step = next(step for step in plan.steps if step.ecu_id == 'a')
    assert step.write_slot == 'A'
    assert plan.states[-1].ecus[0].active_slot == 'A'


def test_noop_and_numeric_equivalence() -> None:
    data = campaign_data()
    for ecu in data['ecus']:
        ecu['target_version'] = '1.0'
    add_constraint(data, 'precondition', 'unused-condition', ecu='a', ignition='on', minimum_battery_percent=100)
    add_constraint(data, 'order', 'unused-order', before='a', after='b')
    plan = feasible(data, deadline_ms=0)
    assert plan.steps == ()
    assert plan.states == (load_campaign(data).initial_state,)
    assert plan.makespan_ms == 0


def test_unchanged_ecu_still_constrains_updated_ecu() -> None:
    data = campaign_data()
    data['ecus'][1]['target_version'] = '1'
    add_constraint(data, 'requires', 'a-needs-b', ecu='a', version_spec='>=2', needs='b', needs_version_spec='>=2')
    assert isinstance(plan_campaign(load_campaign(data)), InfeasibleResult)


def test_invalid_active_image_blocked_even_if_unchanged() -> None:
    data = campaign_data()
    data['ecus'][0]['target_version'] = '1'
    data['initial_state']['ecus'][0]['slot_a']['valid'] = False
    result = plan_campaign(load_campaign(data))
    assert isinstance(result, InfeasibleResult)
    assert [item.id for item in result.conflict.items] == ['bootable:a']


def test_submillisecond_duration_rounds_up() -> None:
    data = campaign_data((0.00001,))
    campaign = load_campaign(data)
    assert duration_ms(campaign.ecus[0]) == 1
    assert feasible(data).makespan_ms == 1


def test_stable_schedule_and_collision_free_core_labels() -> None:
    data = campaign_data()
    add_constraint(data, 'mutex', 'deadline', ecus=['a', 'b'])
    assert feasible(data).model_dump_json() == feasible(data).model_dump_json()
    result = plan_campaign(load_campaign(data), PlanningOptions(deadline_ms=180_000))
    assert isinstance(result, InfeasibleResult)
    assert {(item.kind, item.id) for item in result.conflict.items} == {
        ('constraint', 'deadline'), ('resource', 'deadline')}


def test_unknown_is_not_infeasible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('ota_verifier.planner._Budget.check', lambda *args, **kwargs: z3.unknown)
    result = plan_campaign(load_campaign(campaign_data()))
    assert isinstance(result, UnknownResult)
    assert result.reason


def test_timeout_during_optimization_preserves_feasible_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    from ota_verifier.planner import _Budget
    original = _Budget.check
    calls = 0

    def interrupt(self: _Budget, *args: Any, **kwargs: Any) -> z3.CheckSatResult:
        nonlocal calls
        calls += 1
        return original(self, *args, **kwargs) if calls == 1 else z3.unknown

    monkeypatch.setattr(_Budget, 'check', interrupt)
    campaign = load_campaign(campaign_data())
    result = plan_campaign(campaign)
    assert isinstance(result, FeasibleResult)
    assert not result.plan.optimal
    assert result.note
    assert validate_plan(campaign, result.plan) == ()


def test_timeout_during_core_shrinking_preserves_proven_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    from ota_verifier.planner import _Budget
    original = _Budget.check
    calls = 0

    def interrupt(self: _Budget, *args: Any, **kwargs: Any) -> z3.CheckSatResult:
        nonlocal calls
        calls += 1
        return original(self, *args, **kwargs) if calls == 1 else z3.unknown

    monkeypatch.setattr(_Budget, 'check', interrupt)
    data = campaign_data()
    add_constraint(data, 'order', 'a-first', before='a', after='b')
    add_constraint(data, 'order', 'b-first', before='b', after='a')
    result = plan_campaign(load_campaign(data))
    assert isinstance(result, InfeasibleResult)
    assert not result.conflict.subset_minimal
    assert result.note
