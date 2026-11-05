"""Exact provenance and strict JSON boundaries are deterministic and offline."""
import json
import pytest
from ota_verifier.data.generate import generate_case
from ota_verifier.llm.evidence import evidence_error, source_segments, validate_json
from ota_verifier.llm.models import EvidenceSpan, ExtractionDraft, SourceDocument


def test_unicode_offsets_and_numeric_version_segmentation() -> None:
    document = SourceDocument(id='notes', text='  🚗 gateway >=4.2 requires brake >=4.10.\n\n  Ignition off.  ')
    segments = source_segments(document)
    assert [segment.text for segment in segments] == ['🚗 gateway >=4.2 requires brake >=4.10.', 'Ignition off.']
    for segment in segments:
        assert document.text[segment.evidence.start_char:segment.evidence.end_char] == segment.text
    assert segments[0].evidence.start_char == 2


@pytest.mark.parametrize('change', ['wrong_quote', 'partial_quote', 'outside', 'unknown_document'])
def test_bad_evidence_is_rejected(change: str) -> None:
    case = generate_case()
    entry = case.reference_draft.constraints[0]
    text = entry.constraint.source_text
    raw = entry.evidence.model_dump()
    if change == 'wrong_quote':
        text = text.replace('brake', 'invented')
    elif change == 'partial_quote':
        raw['end_char'] -= 1
        text = text[:-1]
    elif change == 'outside':
        raw['end_char'] += 10000
    else:
        raw['document_id'] = 'missing'
    assert evidence_error(case.request, EvidenceSpan(**raw), text) is not None


@pytest.mark.parametrize('raw', [
    '```json\n{"constraints":[],"issues":[]}\n```',
    '{"constraints":[],"constraints":[],"issues":[]}',
    '{"constraints":[],"issues":[],"extra":NaN}',
    '{"constraints":[],"issues":[],"extra":Infinity}',
    '{"constraints":[],"issues":[],"extra":true}',
    '{"constraints":[]}',
])
def test_non_strict_json_or_schema_is_rejected(raw: str) -> None:
    with pytest.raises(ValueError):
        validate_json(ExtractionDraft, raw)


def test_valid_required_empty_arrays_are_accepted() -> None:
    draft = validate_json(ExtractionDraft, '{"constraints":[],"issues":[]}')
    assert draft.constraints == draft.issues == ()
