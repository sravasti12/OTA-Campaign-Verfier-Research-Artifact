"""Concrete replay rejects altered schedules rather than trusting solver metadata."""
import json
from typing import Any
import pytest
from pydantic import ValidationError
from ota_verifier.models import Plan, PlanningOptions
from ota_verifier.scheduling import validate_plan
from test_planner import add_constraint, campaign_data, feasible, load_campaign


@pytest.mark.parametrize(('mutation', 'expected'), [
    ('slot', 'step_metadata'), ('version', 'step_metadata'), ('source', 'step_metadata'),
    ('duration', 'flash_duration'), ('snapshot', 'projected_state'), ('initial', 'initial_state'),
    ('deadline', 'deadline'), ('campaign', 'plan_identity'), ('missing_step', 'plan_identity'),
])
def test_reject_altered_plan(mutation: str, expected: str) -> None:
    data = campaign_data()
    plan = feasible(data)
    raw = json.loads(plan.model_dump_json())
    if mutation == 'slot':
        raw['steps'][0]['write_slot'] = 'A'
    elif mutation == 'version':
        raw['steps'][0]['to_version'] = '99'
    elif mutation == 'source':
        raw['steps'][0]['constraint_ids'] = ['invented']
    elif mutation == 'duration':
        raw['steps'][0]['start_ms'] += 1
    elif mutation == 'snapshot':
        raw['states'][1]['ecus'][0]['slot_b']['valid'] = False
    elif mutation == 'initial':
        raw['states'][0]['battery_percent'] = 79
    elif mutation == 'deadline':
        raw['options']['deadline_ms'] = 0
    elif mutation == 'campaign':
        raw['campaign_id'] = 'other'
    elif mutation == 'missing_step':
        raw['steps'] = []
        raw['states'] = raw['states'][:1]
        raw['makespan_ms'] = 0
    altered = Plan.model_validate_json(json.dumps(raw))
    assert expected in {finding.code for finding in validate_plan(load_campaign(data), altered)}


def test_replay_detects_mutex_order_and_capacity_overlap() -> None:
    data = campaign_data()
    add_constraint(data, 'mutex', 'shared-bus', ecus=['a', 'b'])
    add_constraint(data, 'order', 'a-first', before='a', after='b')
    plan = feasible(data, max_parallel=1)
    raw = json.loads(plan.model_dump_json())
    raw['steps'][1].update(start_ms=0, end_ms=180_000)
    raw['makespan_ms'] = 180_000
    altered = Plan.model_validate_json(json.dumps(raw))
    findings = validate_plan(load_campaign(data), altered)
    assert {f.constraint_id for f in findings if f.constraint_id} == {'shared-bus', 'a-first'}
    assert 'capacity' in {f.code for f in findings}


@pytest.mark.parametrize('options', [dict(max_parallel=0), dict(max_parallel=True),
    dict(deadline_ms=-1), dict(timeout_ms=0), dict(timeout_ms='100')])
def test_reject_bad_options(options: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        PlanningOptions(**options)


@pytest.mark.parametrize('mutation', ['negative_time', 'empty_interval', 'bad_rank', 'bad_makespan', 'missing_state', 'duplicate_ecu'])
def test_plan_model_rejects_malformed_structure(mutation: str) -> None:
    raw = json.loads(feasible(campaign_data()).model_dump_json())
    if mutation == 'negative_time':
        raw['steps'][0]['start_ms'] = -1
    elif mutation == 'empty_interval':
        raw['steps'][0]['start_ms'] = raw['steps'][0]['end_ms']
    elif mutation == 'bad_rank':
        raw['steps'][0]['activation_index'] = 2
    elif mutation == 'bad_makespan':
        raw['makespan_ms'] = 1
    elif mutation == 'missing_state':
        raw['states'].pop()
    elif mutation == 'duplicate_ecu':
        raw['steps'][1]['ecu_id'] = raw['steps'][0]['ecu_id']
    with pytest.raises(ValidationError):
        Plan.model_validate_json(json.dumps(raw))
