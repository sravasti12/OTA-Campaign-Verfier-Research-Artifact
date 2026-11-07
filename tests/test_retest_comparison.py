"""Offline consistency of final live comparison; no inference or desired-score assertions."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('compare_retest', ROOT / 'eval/live_extraction/compare_retest.py')
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


def test_comparison_preserves_cases_failures_and_denominators() -> None:
    """A report must retain missing old coverage and distinguish actual successful cases."""
    result = comparison.compare()
    before, after = result['original'], result['retest']
    assert len(before['cases']) == len(after['cases']) == 5
    assert before['summary']['not_run_cases'] == 2
    assert before['total_consumption_known'] is False
    assert before['gate_correct_on_usable_drafts']['numerator'] == 0
    assert result['new_provider_requests_by_analysis'] == 0
    assert after['summary']['http_requests_sent'] <= 10
    assert after['summary']['estimated_tokens_reserved'] <= 63997
    assert after['complete_expected_on_scheduled']['denominator'] == 5
