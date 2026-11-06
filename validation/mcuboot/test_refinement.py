"""Policy-review regression tests; mutations below are classifier tests, not native evidence."""
import json
from pathlib import Path
from typing import Any

import pytest

from differential import OUT
from refinement import build_refinement, intentional_policy_review, layer_review, verify_evidence


def recorded_case(identifier: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load an authentic retained pair for review and mutation tests."""
    report = json.loads((OUT / 'comparison.json').read_text(encoding='utf-8'))
    row = next(row for row in report['scenarios'] if row['id'] == identifier)
    trace = json.loads((OUT / row['evidence']['simulator']).read_text(encoding='utf-8'))
    return row, trace


@pytest.mark.parametrize('identifier', ['unauthorized_revert', 'post_confirm_campaign_recovery'])
def test_original_mismatches_are_explained_not_relabelled(identifier: str) -> None:
    """Preserve final-state mismatch and require positive policy evidence."""
    row, trace = recorded_case(identifier)
    assert row['comparison']['status'] == 'MISMATCH'
    review = layer_review(row, trace)
    assert review['disposition'] == 'INTENTIONAL_POLICY_DIFFERENCE'
    assert review['policy_evidence_verified']
    assert any(item['status'] == 'MISMATCH' for item in review['endpoint_properties'])


def test_scenario_label_cannot_hide_invalid_native_image() -> None:
    """A previously intentional label cannot excuse a new image-validity contradiction."""
    row, trace = recorded_case('unauthorized_revert')
    row['mcuboot_actual']['selected_valid'] = False
    review = layer_review(row, trace)
    assert review['disposition'] == 'UNEXPECTED_CONTRADICTION'
    assert review['requires_investigation']


def test_missing_permission_blocker_is_not_intentional() -> None:
    """An unexplained unavailable ECU is not proof of authorization enforcement."""
    row, trace = recorded_case('unauthorized_revert')
    trace['result']['guard_blockers'] = []
    trace['result']['recovery']['blockers'] = []
    assert intentional_policy_review(row, trace)['requires_investigation']


def test_post_confirm_review_requires_actual_intermediate_reboot() -> None:
    """Do not invent an aligned checkpoint to explain final-state divergence."""
    row, trace = recorded_case('post_confirm_campaign_recovery')
    trace['result']['trace'] = [event for event in trace['result']['trace'] if event['stage'] != 'reboot']
    assert layer_review(row, trace)['requires_investigation']


def test_final_confirmation_difference_cannot_be_excused() -> None:
    """Only the reviewed version/objective distinction is an exception."""
    row, trace = recorded_case('post_confirm_campaign_recovery')
    row['simulator_actual']['observation']['confirmed'] = False
    assert layer_review(row, trace)['requires_investigation']


@pytest.mark.parametrize('identifier', ['invalid_signature', 'swap_power_loss', 'interrupted_revert', 'failed_trial'])
def test_unsupported_mechanisms_remain_unsupported(identifier: str) -> None:
    """Endpoint agreement never manufactures mechanism coverage."""
    row, trace = recorded_case(identifier)
    review = layer_review(row, trace)
    assert row['comparison']['status'] == 'UNSUPPORTED'
    assert review['mechanism_equivalence'] == 'UNSUPPORTED'
    assert review['unsupported_reason']


def test_failed_health_exposure_difference_is_observed() -> None:
    """Runtime exposure difference is read from traces rather than guessed from final versions."""
    row, trace = recorded_case('failed_trial')
    observed = layer_review(row, trace)['exposure_difference']
    assert observed['native_trial_selected'] == '1.0.1.1'
    assert not observed['project_ever_effective_candidate']
    assert not observed['application_crash_executed']


def test_corrupt_evidence_is_rejected(tmp_path: Path) -> None:
    """Hash verification fails before policy review."""
    report = json.loads((OUT / 'comparison.json').read_text(encoding='utf-8'))
    report['scenarios'] = []
    report['reference_log_sha256'] = '0' * 64
    (tmp_path / 'reference.log').write_text('altered', encoding='utf-8')
    path = tmp_path / 'comparison.json'
    path.write_text(json.dumps(report), encoding='utf-8')
    with pytest.raises(ValueError, match='hash/path mismatch'):
        verify_evidence(path)


def test_full_review_preserves_evidence_and_reexecutes_python(tmp_path: Path) -> None:
    """Integration gate: retain original C artifacts and compare twelve fresh Python runs."""
    before = verify_evidence(OUT / 'comparison.json')
    report = build_refinement(tmp_path)
    assert verify_evidence(OUT / 'comparison.json') == before
    assert report['original_summary'] == {'MATCH': 6, 'MISMATCH': 2, 'UNSUPPORTED': 4}
    assert report['unexpected_contradictions'] == 0
    assert len(report['scenarios']) == 12
    assert all(row['original_input_unchanged'] for row in report['scenarios'])
