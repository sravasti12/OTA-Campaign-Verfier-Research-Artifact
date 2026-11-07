"""Offline candidate integrity does not grant semantic review or evaluation approval."""
import hashlib
import json
from pathlib import Path
import pytest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'eval/live_extraction'))
from verify_reference_assets import check_asset
from ota_verifier.llm.evidence import evidence_error, source_segments
from ota_verifier.llm.models import DocumentRequest, ExtractionDraft
from ota_verifier.llm.verifier import validate_draft
from ota_verifier.versions import matches

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / 'eval/live_extraction/real-review-v2'


@pytest.mark.parametrize('index', range(5))
def test_proposed_case_schema_provenance_and_offsets_without_approval(index: int) -> None:
    """Each proposed rule/issue is exactly cited; no case is admitted by these checks."""
    packet = json.loads((PACKET / 'candidates.json').read_text(encoding='utf-8'))
    assert packet['live_requests'] == 0 and packet['admitted_cases'] == 0
    row = packet['cases'][index]
    assert row['review_status'] == 'UNREVIEWED' and row['admitted'] is False
    source = PACKET / row['source_file']
    source_status = check_asset(ROOT, source, row['source_sha256'])
    if source_status == 'UNAVAILABLE_EXTERNAL_REFERENCE':
        import warnings
        warnings.warn('Flysky external reference unavailable; schema/citation/gate checks still run', UserWarning)
    if row['source_character_span'] is not None:
        start, end = row['source_character_span']
        assert source.read_text(encoding='utf-8')[start:end] == row['raw_source_excerpt']
    request = DocumentRequest.model_validate_json(json.dumps(row['request_scaffold']))
    draft = ExtractionDraft.model_validate_json(json.dumps(row['proposed_draft']))
    for entry in draft.constraints:
        assert evidence_error(request, entry.evidence, entry.constraint.source_text) is None
    for issue in draft.issues:
        assert evidence_error(request, issue.evidence, issue.source_text) is None
    assert len(source_segments(request.documents[0])) == 1
    codes = {issue.code for issue in validate_draft(request, draft)}
    assert codes == ({'unsupported_requirement'} if row['expected_gate'] == 'blocked' else set())


def test_incompatible_pair_label_does_not_assert_full_major_version_support() -> None:
    """A proposed exclusion is necessary only, not an exhaustive compatibility rule."""
    row = json.loads((PACKET / 'candidates.json').read_text(encoding='utf-8'))['cases'][1]
    rule = row['proposed_draft']['constraints'][0]['constraint']
    assert rule['version_spec'] == '==3.2.0' and rule['needs_version_spec'] == '!=2.4.0'
    assert not matches('2.4.0', rule['needs_version_spec'])
    assert matches('3.0.1', rule['needs_version_spec'])
