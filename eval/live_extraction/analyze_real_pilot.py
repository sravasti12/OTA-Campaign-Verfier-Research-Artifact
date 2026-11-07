"""Recover real-pilot metrics from saved outputs, retaining provider and coverage failures."""
from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(Path(__file__).resolve().parent)]
from real_pilot import score_case
from pilot import ratio, sha
from ota_verifier.llm.evidence import canonical_json, content_hash, validate_json
from ota_verifier.llm.models import ExtractionDraft, ExtractionRun

FOLDER = ROOT / 'eval/live_extraction/real-pilot-v1'


def analyze() -> dict[str, Any]:
    """Verify frozen execution evidence and separate usable predictions from transport failure."""
    def read(name: str) -> Any:
        return json.loads((FOLDER / name).read_text(encoding='utf-8'))
    index = read('execution-SHA256SUMS.json')
    assert all(sha(FOLDER / name) == digest for name, digest in index.items())
    data, outcomes, calls = read('dataset.json'), read('outcomes.json'), read('calls.json')
    assert content_hash(canonical_json(data)) == read('approval.json')['dataset_canonical_sha256']
    by_id = {row['id']: row for row in data['cases']}
    parsed = []
    attempted = []
    for outcome in outcomes:
        if outcome['status'] == 'NOT_RUN':
            continue
        row = by_id[outcome['case_id']]
        run = ExtractionRun.model_validate_json(canonical_json(outcome['run']))
        assert score_case(row, run) == outcome['score']
        attempted.append(outcome)
        if run.draft is not None:
            extraction = next(c for c in run.calls if c.purpose == 'extraction')
            assert validate_json(ExtractionDraft, extraction.response_text) == run.draft
            parsed.append(outcome)
        assert all(c.origin == 'live' and c.provider == 'groq' for c in run.calls)
    for call in calls:
        if call.get('call'):
            record = call['call']
            assert record['origin'] == 'live' and record['provider'] == 'groq'
            assert content_hash(record['request_json']) == record['request_hash'] == call['request_sha256']
    usage_known = [call for call in calls if call.get('usage') is not None]
    return {'mode': 'OFFLINE_RECOVERY_OF_EXISTING_LIVE_OUTPUTS', 'new_api_requests': 0,
        'execution_hashes_verified': len(index), 'scheduled_cases': 5, 'attempted_cases': len(attempted),
        'usable_extraction_cases': len(parsed), 'not_run_cases': [o['case_id'] for o in outcomes if o['status'] == 'NOT_RUN'],
        'schema_valid_extraction_json_received': ratio(len(parsed), len(parsed)),
        'usable_extraction_response_coverage': ratio(len(parsed), len(attempted)),
        'semantic_exact_on_usable_extractions': ratio(sum(o['score']['semantic_exact'] for o in parsed), len(parsed)),
        'semantic_exact_on_attempted_cases': ratio(sum(o['score']['semantic_exact'] for o in attempted), len(attempted)),
        'mechanical_gate_agreement_on_attempted_cases': ratio(sum(o['score']['gate_correct'] for o in attempted), len(attempted)),
        'gate_agreement_on_usable_extractions': ratio(sum(o['score']['gate_correct'] for o in parsed), len(parsed)),
        'complete_expected_outcome_on_attempted_cases': ratio(sum(o['score']['complete_expected_outcome'] for o in attempted), len(attempted)),
        'expected_unsupported_cases': 2, 'expected_unsupported_cases_with_usable_extraction': sum(
            by_id[o['case_id']]['expected_gate'] == 'blocked' for o in parsed),
        'correct_unsupported_abstention_on_usable_expected_unsupported_cases': ratio(
            sum(o['score']['complete_expected_outcome'] for o in parsed if by_id[o['case_id']]['expected_gate'] == 'blocked'),
            sum(by_id[o['case_id']]['expected_gate'] == 'blocked' for o in parsed)),
        'false_unsupported_abstention_on_usable_supported_positive_cases': ratio(
            sum('unsupported_requirement' in o['score']['actual_issue_kinds'] for o in parsed if o['score']['gold_constraints'] > 0),
            sum(o['score']['gold_constraints'] > 0 for o in parsed)),
        'descriptive_case': 'NOT_RUN', 'z3_cases': sum(o['planning'] is not None for o in attempted),
        'provider_http_success': ratio(sum(c['http_status'] == 200 for c in calls), len(calls)),
        'usage_coverage_requests': ratio(len(usage_known), len(calls)),
        'reported_tokens_on_usage_known_requests': sum(c['usage']['total_tokens'] for c in usage_known),
        'failed_request_tokens': None,
        'failed_request_usage_note': 'HTTP400 response supplies no usage. Reported 6337 tokens cover three successful requests only, not necessarily total consumed/billed tokens.',
        'mechanical_gate_note': 'Case03 blocked on provider failure, not a successful unsupported_requirement classification. Raw 1/3 gate-state agreement is not a validated pass.',
        'provider_error_codes': [json.loads(c['error_body'])['error']['code'] for c in calls if c.get('error_body')]}


if __name__ == '__main__':
    result = analyze()
    (FOLDER / 'analysis.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    sys.stdout.write(json.dumps(result, indent=2) + '\n')
