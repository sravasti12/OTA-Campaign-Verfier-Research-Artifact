"""Recovery must restore original active images without unsafe intermediate states."""
from itertools import product
import json
from pathlib import Path
from typing import Any
import pytest
from ota_verifier.ab import select_slot, with_image
from ota_verifier.compat import check_compatibility
from ota_verifier.invariants import check_recovery_path
from ota_verifier.models import Campaign, Image
from ota_verifier.recovery import find_recovery
from ota_verifier.simulation_models import SimulationOptions
from test_planner import add_constraint, campaign_data, feasible, load_campaign


def _permissions(data: dict[str, Any], names: tuple[str, ...] = ('a', 'b')) -> None:
    data['downgrade_authorizations'] = [dict(ecu_id=name, version='1', authorized_by='reviewer',
        reason='Restore original simulation images') for name in names]


def test_original_state_has_a_defined_empty_recovery_path() -> None:
    campaign = load_campaign(campaign_data())
    result = find_recovery(campaign, campaign.initial_state)
    assert result.status == 'available'
    assert result.steps == ()
    assert result.states == (campaign.initial_state,)


def test_completed_upgrade_cannot_implicitly_downgrade() -> None:
    data = campaign_data()
    campaign = load_campaign(data)
    final = feasible(data).states[-1]
    result = find_recovery(campaign, final)
    assert result.status == 'unavailable'
    assert result.steps == ()
    assert 'unauthorized_downgrade' in {v.code for v in result.blockers}


def test_recovery_trap_reverts_dependent_before_provider() -> None:
    path = Path(__file__).parent / 'fixtures' / 'recovery_trap.json'
    data = json.loads(path.read_text(encoding='utf-8'))['campaign']
    _permissions(data, ('gateway', 'brake'))
    campaign = load_campaign(data)
    final = feasible(data).states[-1]
    result = find_recovery(campaign, final)
    assert result.status == 'available'
    assert [step.ecu_id for step in result.steps] == ['brake', 'gateway']
    assert all(not check_compatibility(campaign, state) for state in result.states)
    assert check_recovery_path(campaign, final, result) == ()


def test_goal_requires_original_slot_not_only_same_version() -> None:
    campaign = load_campaign(campaign_data())
    state = with_image(campaign.initial_state, 'a', 'B', Image(version='1.0'))
    state = select_slot(state, 'a', 'B')
    result = find_recovery(campaign, state)
    assert result.status == 'available'
    assert len(result.steps) == 1
    assert result.steps[0].to_slot == 'A'


def test_recovery_state_limit_is_unknown_not_unavailable() -> None:
    data = campaign_data()
    _permissions(data)
    campaign = load_campaign(data)
    final = feasible(data).states[-1]
    result = find_recovery(campaign, final, SimulationOptions(max_recovery_states=1))
    assert result.status == 'unknown'
    assert result.examined_states == 1
    assert result.steps == ()
    assert check_recovery_path(campaign, final, result) == ()


def test_invalid_or_absent_original_images_cannot_be_fabricated() -> None:
    data = campaign_data()
    _permissions(data)
    campaign = load_campaign(data)
    final = feasible(data).states[-1]
    final = with_image(final, 'a', 'A', None)
    result = find_recovery(campaign, final)
    assert result.status == 'unavailable'
    assert 'rollback_image_unusable' in {v.code for v in result.blockers}


def test_boot_fault_can_be_repaired_without_erasing_failure_history() -> None:
    data = campaign_data()
    _permissions(data)
    campaign = load_campaign(data)
    failed = feasible(data).states[-1]
    failed = with_image(failed, 'a', 'B', Image(version='2', valid=False))
    result = find_recovery(campaign, failed)
    assert result.status == 'available'
    assert result.steps[0].ecu_id == 'a'
    assert check_recovery_path(campaign, failed, result) == ()


def test_incompatible_recovery_cannot_be_justified_by_final_state_only() -> None:
    data = campaign_data()
    _permissions(data)
    add_constraint(data, 'requires', 'a-needs-b', ecu='a', version_spec='>=2', needs='b', needs_version_spec='>=2')
    campaign = load_campaign(data)
    failed = feasible(data).states[-1]
    failed = with_image(failed, 'b', 'B', Image(version='2', valid=False))
    result = find_recovery(campaign, failed)
    assert result.status == 'unavailable'
    assert 'incompatible_versions' in {v.code for v in result.blockers}
    assert 'invalid_active_image' in {v.code for v in result.blockers}


def test_restore_original_version_can_be_an_upgrade() -> None:
    data = campaign_data()
    data['ecus'][0].update(current_version='2', target_version='1')
    data['initial_state']['ecus'][0]['slot_a']['version'] = '2'
    data['downgrade_authorizations'] = [dict(ecu_id='a', version='1', authorized_by='reviewer', reason='Exercise')]
    campaign = load_campaign(data)
    after = feasible(data).states[-1]
    # Only b needs a rollback downgrade permission; it is deliberately absent.
    after = select_slot(after, 'b', 'A')
    result = find_recovery(campaign, after)
    assert result.status == 'available'
    assert result.steps[0].from_version == '1'
    assert result.steps[0].to_version == '2'


@pytest.mark.parametrize('permission_bits', list(product((False, True), repeat=3)))
def test_recovery_matches_exhaustive_permission_combinations(permission_bits: tuple[bool, ...]) -> None:
    data = campaign_data((1, 1, 1))
    names = ('a', 'b', 'c')
    _permissions(data, tuple(name for name, allowed in zip(names, permission_bits) if allowed))
    campaign = load_campaign(data)
    final = feasible(data).states[-1]
    result = find_recovery(campaign, final)
    assert (result.status == 'available') == all(permission_bits)
    if result.status == 'available':
        assert len(result.steps) == 3
        assert check_recovery_path(campaign, final, result) == ()
