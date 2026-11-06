"""Small package integrity and outcome-parsing tests; no synthetic native execution evidence."""
import json
from pathlib import Path

import pytest

from differential import sha256
from validate import comparison_acceptable, junit_outcome, verify_package


def test_junit_counts_failures_errors_skips_without_claiming_passes(tmp_path: Path) -> None:
    """A failed/skipped test is never added to the passed count."""
    path = tmp_path / 'pytest.xml'
    path.write_text('<testsuites><testsuite tests="7" failures="1" errors="1" skipped="2"/></testsuites>', encoding='utf-8')
    assert junit_outcome(path) == {'tests': 7, 'failures': 1, 'errors': 1, 'skipped': 2, 'passed': 3}


def test_junit_zero_tests_fails_closed(tmp_path: Path) -> None:
    """A zero-test run does not satisfy the regression stage."""
    path = tmp_path / 'pytest.xml'
    path.write_text('<testsuites><testsuite tests="0"/></testsuites>', encoding='utf-8')
    with pytest.raises(ValueError, match='No regression'):
        junit_outcome(path)


def test_manifest_verifies_report_and_detects_tampering(tmp_path: Path) -> None:
    """Include the report in the independent manifest and reject changed artifacts."""
    report = tmp_path / 'validation.json'
    report.write_text('{}', encoding='utf-8')
    log = tmp_path / 'execution.log'
    log.write_text('unit test fixture only', encoding='utf-8')
    manifest = {'validation.json': sha256(report), 'execution.log': sha256(log)}
    (tmp_path / 'SHA256SUMS.json').write_text(json.dumps(manifest), encoding='utf-8')
    assert verify_package(report) == 2
    log.write_text('changed', encoding='utf-8')
    with pytest.raises(ValueError, match='hash mismatch'):
        verify_package(report)


def test_manifest_cannot_reference_outside_package(tmp_path: Path) -> None:
    """An external file cannot be substituted for a packaged artifact."""
    report = tmp_path / 'validation.json'
    report.write_text('{}', encoding='utf-8')
    (tmp_path / 'SHA256SUMS.json').write_text(json.dumps(
        {'validation.json': sha256(report), '../outside.txt': '0' * 64}), encoding='utf-8')
    with pytest.raises(ValueError, match='hash mismatch'):
        verify_package(report)


@pytest.mark.parametrize(('status', 'unexpected', 'review_errors', 'accepted'), [
    ('MISMATCH', False, 0, True),
    ('UNSUPPORTED', True, 0, False),
    ('INCONCLUSIVE', False, 0, False),
    ('MATCH', False, 1, False),
])
def test_package_gate_preserves_differences_but_rejects_unknown_or_unexpected(
    status: str, unexpected: bool, review_errors: int, accepted: bool,
) -> None:
    """Classifier-only fixtures verify that native anomalies cannot be hidden by a category."""
    comparison = {'scenarios': [{'comparison': {'status': status, 'unexpected_contradiction': unexpected}}]}
    assert comparison_acceptable(comparison, {'unexpected_contradictions': review_errors}) is accepted
