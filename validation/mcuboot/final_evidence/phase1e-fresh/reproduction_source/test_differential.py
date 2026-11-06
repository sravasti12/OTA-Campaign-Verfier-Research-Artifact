"""Comparator contracts plus integration against retained actual C observations.

Synthetic dictionaries below test classification only; they are not execution evidence.
"""
import json
from pathlib import Path
from typing import Any

import pytest

from differential import (OUT, SCENARIOS, Scenario, build_report, compare, make_campaign,
                          read_reference, run_simulator)


def outcome(version: str | None = '1.0.1.1', *, boot_ok: bool = True) -> dict[str, Any]:
    """Construct unit-test comparator input, never reference evidence."""
    return {'selected_version': version, 'selected_valid': True if version else None,
            'confirmed': False, 'boot_ok': boot_ok}


def test_numeric_identity_ignores_trailing_zero_not_slot_address() -> None:
    """Version normalization compares image identities, not region names."""
    result = compare(Scenario('test_upgrade', ''), outcome('0.0.1.0'), outcome('0.0.1'))
    assert result['status'] == 'MATCH'


def test_unexpected_difference_cannot_be_hidden() -> None:
    """A supported-property disagreement is a failing contradiction."""
    result = compare(Scenario('test_upgrade', ''), outcome(), outcome('0.0.1.0'))
    assert result['status'] == 'MISMATCH' and result['unexpected_contradiction']


def test_unsupported_is_never_promoted_to_validated_match() -> None:
    """Matching endpoints do not prove an unimplemented mechanism."""
    case = next(case for case in SCENARIOS if case.id == 'invalid_signature')
    result = compare(case, outcome(), outcome())
    assert result['status'] == 'UNSUPPORTED'
    assert all(item['status'] == 'MATCH' for item in result['properties'])


def test_failed_reference_boot_is_inconclusive() -> None:
    """A failed C boot must not become a guessed firmware outcome."""
    assert compare(SCENARIOS[0], outcome(boot_ok=False), outcome())['status'] == 'INCONCLUSIVE'


def test_missing_reference_evidence_is_rejected(tmp_path: Path) -> None:
    """A success footer without observed scenarios proves nothing."""
    path = tmp_path / 'incomplete.log'
    path.write_text('test result: ok. 1 passed; 0 failed', encoding='utf-8')
    with pytest.raises(ValueError, match='Missing or unexpected'):
        read_reference(path)


def test_zero_test_native_success_is_rejected(tmp_path: Path) -> None:
    """Cargo filter mistakes must fail closed."""
    path = tmp_path / 'empty.log'
    path.write_text('test result: ok. 0 passed; 0 failed', encoding='utf-8')
    with pytest.raises(ValueError, match='did not execute'):
        read_reference(path)


def test_rollback_authorization_is_an_explicit_input() -> None:
    """The harness never grants a downgrade based on native output."""
    assert make_campaign(True).downgrade_authorizations
    assert not make_campaign(False).downgrade_authorizations


def test_python_nominal_is_sampled_before_auto_confirmation(tmp_path: Path) -> None:
    """The trial checkpoint must not be confused with the final confirmed state."""
    result = run_simulator(SCENARIOS[0], tmp_path / 'python.json')
    assert result['observation']['selected_version'] == '1.0.1.1'
    assert result['observation']['confirmed'] is False


def test_real_reference_comparison_covers_every_manifest(tmp_path: Path) -> None:
    """Integration gate: requires actual retained C logs, never a mocked fallback."""
    report = build_report(tmp_path)
    assert len(report['scenarios']) == len(SCENARIOS) == 12
    assert all(row['mcuboot_actual']['boot_ok'] for row in report['scenarios'])
    assert all(row['comparison']['reference_expectation_met'] for row in report['scenarios'])
    assert not any(row['comparison'].get('unexpected_contradiction') for row in report['scenarios'])
    # Preserve expected, explicitly scoped differences rather than forcing equality.
    results = {row['id']: row['comparison']['status'] for row in report['scenarios']}
    assert results['unauthorized_revert'] == 'MISMATCH'
    assert results['post_confirm_campaign_recovery'] == 'MISMATCH'
    assert results['invalid_signature'] == 'UNSUPPORTED'
    assert results['swap_power_loss'] == 'UNSUPPORTED'


def test_truncated_reset_sequence_is_rejected(tmp_path: Path) -> None:
    """Even a success footer cannot excuse a missing required checkpoint."""
    text = (OUT / 'reference.log').read_text(encoding='utf-8')
    truncated = '\n'.join(line for line in text.splitlines()
                          if not ('DIFF_JSON ' in line and '"checkpoint":"reset_3"' in line))
    path = tmp_path / 'truncated.log'
    path.write_text(truncated, encoding='utf-8')
    with pytest.raises(ValueError, match='terminal'):
        read_reference(path)
