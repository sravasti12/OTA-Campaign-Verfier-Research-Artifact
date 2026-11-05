"""Validation boundaries and compatibility semantics."""
import json
from pathlib import Path
from typing import Any
import pytest
from pydantic import ValidationError
from ota_verifier.compat import check_compatibility
from ota_verifier.models import Campaign, VehicleState


def payload() -> dict[str, Any]:
    """Load a fresh campaign mapping for each mutation."""
    path = Path(__file__).parent / 'fixtures' / 'order_sensitive.json'
    return json.loads(path.read_text(encoding='utf-8'))['campaign']


def validate(data: dict[str, Any]) -> Campaign:
    """Use the JSON boundary, retaining strict scalar validation."""
    return Campaign.model_validate_json(json.dumps(data))


@pytest.mark.parametrize(('field', 'value'), [
    ('flash_minutes', 0), ('flash_minutes', -1), ('flash_minutes', '3'),
    ('current_version', 'v1'), ('target_version', '2-beta'), ('id', '  '),
])
def test_bad_ecu_fields(field: str, value: object) -> None:
    data = payload()
    data['ecus'][0][field] = value
    with pytest.raises(ValidationError):
        validate(data)


@pytest.mark.parametrize('mutation', [
    'duplicate_ecu', 'duplicate_runtime', 'duplicate_constraint', 'missing_runtime',
    'unknown_runtime', 'empty_ecus', 'bad_slot', 'empty_active', 'version_disagreement',
    'bad_spec', 'unknown_field', 'unknown_type', 'missing_source', 'bad_battery',
    'bad_ignition', 'unknown_authorization',
])
def test_invalid_campaigns(mutation: str) -> None:
    data = payload()
    if mutation == 'duplicate_ecu':
        data['ecus'].append(data['ecus'][0])
    elif mutation == 'duplicate_runtime':
        data['initial_state']['ecus'].append(data['initial_state']['ecus'][0])
    elif mutation == 'duplicate_constraint':
        data['constraints'].append(data['constraints'][0])
    elif mutation == 'missing_runtime':
        data['initial_state']['ecus'].pop()
    elif mutation == 'unknown_runtime':
        data['initial_state']['ecus'][0]['ecu_id'] = 'other'
    elif mutation == 'empty_ecus':
        data['ecus'] = []
    elif mutation == 'bad_slot':
        data['initial_state']['ecus'][0]['active_slot'] = 'C'
    elif mutation == 'empty_active':
        data['initial_state']['ecus'][0]['slot_a'] = None
    elif mutation == 'version_disagreement':
        data['ecus'][0]['current_version'] = '9'
    elif mutation == 'bad_spec':
        data['constraints'][0]['version_spec'] = '2'
    elif mutation == 'unknown_field':
        data['constraints'][0]['invented'] = True
    elif mutation == 'unknown_type':
        data['constraints'][0]['type'] = 'invented'
    elif mutation == 'missing_source':
        del data['constraints'][0]['source_text']
    elif mutation == 'bad_battery':
        data['initial_state']['battery_percent'] = 101
    elif mutation == 'bad_ignition':
        data['initial_state']['ignition'] = 'running'
    elif mutation == 'unknown_authorization':
        data['downgrade_authorizations'] = [dict(ecu_id='unknown', version='1',
            authorized_by='engineer', reason='Recovery exercise')]
    with pytest.raises(ValidationError):
        validate(data)


@pytest.mark.parametrize('constraint', [
    {'type': 'mutex', 'ecus': ['gateway', 'brake']},
    {'type': 'precondition', 'ecu': 'brake', 'ignition': 'off', 'minimum_battery_percent': 30},
    {'type': 'order', 'before': 'gateway', 'after': 'brake'},
])
def test_constraint_roundtrip(constraint: dict[str, Any]) -> None:
    data = payload()
    data['constraints'].append(dict(id='extra', source_document_id='manual',
        source_text='A test requirement.', **constraint))
    data['downgrade_authorizations'] = [dict(ecu_id='gateway', version='1',
        authorized_by='engineer', reason='Recovery exercise')]
    campaign = validate(data)
    assert Campaign.model_validate_json(campaign.model_dump_json()) == campaign
    assert check_compatibility(campaign, campaign.initial_state) == ()


@pytest.mark.parametrize('constraint', [
    {'type': 'mutex', 'ecus': ['gateway', 'gateway']},
    {'type': 'mutex', 'ecus': ['gateway']},
    {'type': 'mutex', 'ecus': ['gateway', 'unknown']},
    {'type': 'order', 'before': 'gateway', 'after': 'gateway'},
    {'type': 'order', 'before': 'unknown', 'after': 'brake'},
    {'type': 'precondition', 'ecu': 'unknown', 'ignition': 'off', 'minimum_battery_percent': 30},
    {'type': 'precondition', 'ecu': 'brake', 'ignition': 'off', 'minimum_battery_percent': -1},
])
def test_invalid_other_constraints(constraint: dict[str, Any]) -> None:
    data = payload()
    data['constraints'] = [dict(id='extra', source_document_id='manual',
        source_text='A test requirement.', **constraint)]
    with pytest.raises(ValidationError):
        validate(data)


def test_uses_active_b_and_reports_all_constraints() -> None:
    data = payload()
    data['constraints'].append(dict(data['constraints'][0], id='second-source'))
    campaign = validate(data)
    state_data = data['initial_state']
    brake = state_data['ecus'][1]
    brake['slot_b']['version'] = '2'
    brake['active_slot'] = 'B'
    state = VehicleState.model_validate_json(json.dumps(state_data))
    findings = check_compatibility(campaign, state)
    assert [f.constraint_id for f in findings] == ['brake-needs-gateway', 'second-source']
    assert findings[0].actual_version == '1'
    assert findings[0].expected_version_spec == '>=2'
    assert findings[0].ecu_ids == ('brake', 'gateway')
    assert 'brake@2' in findings[0].message


def test_inactive_images_do_not_trigger_requires() -> None:
    data = payload()
    data['initial_state']['ecus'][1]['slot_b']['version'] = '2'
    campaign = validate(data)
    assert check_compatibility(campaign, campaign.initial_state) == ()


def test_incompatible_initial_state_is_analyzable() -> None:
    data = payload()
    data['ecus'][1]['current_version'] = '2'
    data['initial_state']['ecus'][1]['slot_a']['version'] = '2'
    campaign = validate(data)
    assert len(check_compatibility(campaign, campaign.initial_state)) == 1


def test_bootability_is_separate_from_compatibility() -> None:
    data = payload()
    data['initial_state']['ecus'][0]['slot_a']['valid'] = False
    campaign = validate(data)
    assert not campaign.initial_state.ecus[0].active_image.valid
    assert check_compatibility(campaign, campaign.initial_state) == ()


def test_incomplete_state_raises_instead_of_passing() -> None:
    campaign = validate(payload())
    state_data = json.loads(campaign.initial_state.model_dump_json())
    state_data['ecus'].pop()
    state = VehicleState.model_validate_json(json.dumps(state_data))
    with pytest.raises(ValueError, match='exactly'):
        check_compatibility(campaign, state)


def test_records_are_frozen() -> None:
    campaign = validate(payload())
    with pytest.raises(ValidationError):
        campaign.id = 'changed'
