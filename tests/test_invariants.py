"""Pure state, installation, authorization, and recovery-path invariant tests."""
import json
from typing import Any
import pytest
from ota_verifier.ab import get_ecu, select_slot, with_image
from ota_verifier.invariants import check_recovery_path, check_state, check_transition
from ota_verifier.models import Image, VehicleState
from ota_verifier.policy import version_change_allowed
from ota_verifier.recovery import find_recovery
from ota_verifier.simulation_models import RecoveryResult, RecoveryStep
from test_planner import add_constraint, campaign_data, feasible, load_campaign


def _authorized_data() -> dict[str, Any]:
    data = campaign_data()
    data['downgrade_authorizations'] = [dict(ecu_id=ecu, version='1.0', authorized_by='reviewer',
        reason='Explicit simulation rollback authorization') for ecu in ('a', 'b')]
    return data


def test_state_checks_invalid_active_and_shared_dependency() -> None:
    data = campaign_data()
    add_constraint(data, 'requires', 'a-needs-b', ecu='a', version_spec='>=2', needs='b', needs_version_spec='>=2')
    campaign = load_campaign(data)
    state = with_image(campaign.initial_state, 'a', 'A', Image(version='2', valid=False))
    findings = check_state(campaign, state)
    assert {f.code for f in findings} == {'invalid_active_image', 'incompatible_versions'}
    dependency = next(f for f in findings if f.code == 'incompatible_versions')
    assert dependency.constraint_id == 'a-needs-b'
    assert dependency.source_text == 'Requirement a-needs-b.'
    assert dependency.actual_version == '1'


@pytest.mark.parametrize('authorized', [True, False])
def test_active_downgrade_permission(authorized: bool) -> None:
    data = _authorized_data() if authorized else campaign_data()
    campaign = load_campaign(data)
    before = feasible(data).states[-1]
    after = select_slot(before, 'a', 'A')
    findings = check_transition(campaign, before, after)
    assert bool(findings) is not authorized
    if findings:
        assert findings[0].code == 'unauthorized_downgrade'
        assert findings[0].ecu_ids == ('a',)


def test_verifying_an_older_image_needs_permission_before_activation() -> None:
    campaign = load_campaign(campaign_data())
    before = with_image(campaign.initial_state, 'a', 'B', Image(version='0', valid=False))
    after = with_image(before, 'a', 'B', Image(version='0', valid=True))
    assert check_transition(campaign, before, after)[0].code == 'unauthorized_downgrade'
    assert get_ecu(after, 'a').active_slot == 'A'


def test_existing_older_inactive_image_is_not_a_new_installation() -> None:
    campaign = load_campaign(campaign_data())
    state = feasible(campaign_data()).states[-1]
    assert check_transition(campaign, state, state) == ()


def test_recovery_upgrade_needs_no_downgrade_permission() -> None:
    campaign = load_campaign(campaign_data())
    assert version_change_allowed(campaign, 'a', '1', '2')
    assert version_change_allowed(campaign, 'a', '1', '1.0')
    assert not version_change_allowed(campaign, 'a', '2', '1')
    with pytest.raises(ValueError, match='Unknown ECU'):
        version_change_allowed(campaign, 'other', '1', '2')


def test_state_and_transition_reject_incomplete_coverage() -> None:
    campaign = load_campaign(campaign_data())
    raw = json.loads(campaign.initial_state.model_dump_json())
    raw['ecus'].pop()
    state = VehicleState.model_validate_json(json.dumps(raw))
    with pytest.raises(ValueError, match='exactly'):
        check_state(campaign, state)
    with pytest.raises(ValueError, match='exactly'):
        check_transition(campaign, campaign.initial_state, state)


def test_recovery_checker_rejects_forged_available_empty_path() -> None:
    campaign = load_campaign(campaign_data())
    state = feasible(campaign_data()).states[-1]
    forged = RecoveryResult(status='available', states=(state,), examined_states=1, reason='Forged')
    assert 'rollback_goal_missing' in {f.code for f in check_recovery_path(campaign, state, forged)}


def test_recovery_checker_rejects_metadata_and_snapshot_tampering() -> None:
    data = _authorized_data()
    campaign = load_campaign(data)
    state = feasible(data).states[-1]
    recovery = find_recovery(campaign, state)
    raw = json.loads(recovery.model_dump_json())
    raw['steps'][0]['from_version'] = '99'
    forged = RecoveryResult.model_validate_json(json.dumps(raw))
    assert check_recovery_path(campaign, state, forged)[0].code == 'rollback_path_invalid'
    raw = json.loads(recovery.model_dump_json())
    raw['states'][1]['battery_percent'] = 1
    forged = RecoveryResult.model_validate_json(json.dumps(raw))
    assert 'rollback_path_invalid' in {f.code for f in check_recovery_path(campaign, state, forged)}


def test_recovery_checker_detects_unauthorized_actual_switch() -> None:
    campaign = load_campaign(campaign_data())
    before = feasible(campaign_data()).states[-1]
    after = select_slot(before, 'a', 'A')
    path = RecoveryResult(status='available', states=(before, after), examined_states=2,
        steps=(RecoveryStep(ecu_id='a', from_slot='B', to_slot='A', from_version='2', to_version='1'),), reason='Forged')
    assert 'unauthorized_downgrade' in {v.code for v in check_recovery_path(campaign, before, path)}
