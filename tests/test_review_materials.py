"""Offline review-candidate integrity, never annotation approval or model accuracy."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from ota_verifier.benchmark.corpus import corpus_hash, load_corpus

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prepare_review_materials',ROOT/'eval/prepare_review_materials.py')
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
MATERIALS = ROOT/'eval/live_extraction/review-materials-v1'


def test_review_artifact_hashes_and_all_synthetic_cases_pending() -> None:
    """Every frozen artifact verifies, but no automatic check grants a human sign-off."""
    manifest = json.loads((MATERIALS/'SHA256SUMS.json').read_text())
    for name,expected in manifest.items():
        assert (MATERIALS/name).resolve().is_relative_to(MATERIALS.resolve())
        assert hashlib.sha256((MATERIALS/name).read_bytes()).hexdigest() == expected
    audit = json.loads((MATERIALS/'synthetic-checks.json').read_text())
    assert audit['corpus_sha256'] == corpus_hash(load_corpus())
    assert len(audit['cases']) == 12
    assert all(row['human_review'] == 'PENDING' for row in audit['cases'])
    template = json.loads((MATERIALS/'review-signoff.template.json').read_text())
    assert template['reviewer'] is None and template['status'] == 'PENDING'
    assert not any(row['approved'] for row in template['case_reviews'])


def test_twenty_real_candidates_are_proposed_and_not_scored() -> None:
    """Do not promote source discovery into real-document positive coverage or approval."""
    data = json.loads((MATERIALS/'real-candidates.json').read_text())
    assert len(data['cases']) == data['candidate_count'] == 20
    assert data['expressible_positive_cases'] == data['live_inference_requests'] == 0
    assert {row['project'] for row in data['cases']} == {'MCUboot','Zephyr','PX4'}
    for raw in data['cases']:
        candidate = module.Candidate.model_validate(raw)
        assert candidate.review_status == 'PROPOSED_UNREVIEWED'
        assert candidate.origin == 'real_document'
        assert candidate.inventory_mapping == 'UNRESOLVED_NOT_AN_EXECUTABLE_CASE'
        assert candidate.proposed_constraints == []
        assert candidate.admission_blockers


def test_source_tampering_and_span_changes_rejected() -> None:
    """Changing an exact quote or its derived citation cannot silently retain the label artifact."""
    raw = json.loads((MATERIALS/'real-candidates.json').read_text())['cases'][0]
    raw['excerpt'] += ' modified'
    with pytest.raises(ValueError,match='hash'):
        module.Candidate.model_validate(raw)
    raw['excerpt_sha256'] = hashlib.sha256(raw['excerpt'].encode()).hexdigest()
    with pytest.raises(ValueError,match='segments'):
        module.Candidate.model_validate(raw)


def test_paragraph_preserves_exact_source_substring() -> None:
    """Raw-source offsets preserve original newlines and complete paragraph context."""
    text = 'Heading\n\nAlpha must use beta.\nConditional context.\n\nNext.'
    start,end = module.paragraph(text,'must use')
    assert text[start:end] == 'Alpha must use beta.\nConditional context.'
