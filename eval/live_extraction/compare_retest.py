"""Offline versioned comparison of saved real-document runs; never inference."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(Path(__file__).resolve().parent)]
from pilot import ratio, sha
from real_pilot import score_case
from ota_verifier.llm.evidence import canonical_json
from ota_verifier.llm.models import ExtractionRun


def measurements(folder: Path) -> dict[str, Any]:
    """Recompute each score and retain missing-response/NOT_RUN denominators."""
    dataset = json.loads((folder / 'dataset.json').read_text(encoding='utf-8'))
    summary = json.loads((folder / 'summary.json').read_text())
    rows = {row['id']: row for row in dataset['cases']}
    outcomes = json.loads((folder / 'outcomes.json').read_text())
    calls = json.loads((folder / 'calls.json').read_text())
    for call in calls:
        if call.get('call'):
            record = call['call']
            assert record['origin'] == 'live' and record['provider'] == 'groq'
            assert hashlib.sha256(record['request_json'].encode('utf-8')).hexdigest() == record['request_hash'] == call['request_sha256']
    details = []
    for outcome in outcomes:
        if outcome['status'] == 'NOT_RUN':
            details.append({'case_id': outcome['case_id'], 'status': 'NOT_RUN', 'reason': outcome['reason']})
            continue
        run = ExtractionRun.model_validate_json(canonical_json(outcome['run']))
        score = score_case(rows[outcome['case_id']], run)
        assert score == outcome['score']
        assert all(call.origin == 'live' and call.provider == 'groq' for call in run.calls)
        details.append({'case_id': outcome['case_id'], 'status': 'ATTEMPTED', 'usable_extraction': run.draft is not None,
            'score': score, 'gate_issues': [i.model_dump(mode='json') for i in run.issues],
            'planning_status': outcome['planning']['status'] if outcome['planning'] else 'not_run',
            'plan_step_count': len(outcome['planning']['plan']['steps']) if outcome['planning'] and outcome['planning']['status'] == 'feasible' else None,
            'extracted_constraints': [e.model_dump(mode='json') for e in run.draft.constraints] if run.draft else None,
            'extraction_issues': [i.model_dump(mode='json') for i in run.draft.issues] if run.draft else None,
            'verdict': run.verification.model_dump(mode='json') if run.verification else None})
    attempted = [d for d in details if d['status'] == 'ATTEMPTED']
    parsed = [d for d in attempted if d['usable_extraction']]
    unsupported = [d for d in parsed if rows[d['case_id']]['expected_gate'] == 'blocked']
    descriptive = [d for d in parsed if not rows[d['case_id']]['proposed_draft']['constraints'] and rows[d['case_id']]['expected_gate'] != 'blocked']
    usage = [c for c in calls if c.get('usage') is not None]
    successful = [c for c in calls if c.get('http_status') == 200]
    return {'summary': summary, 'cases': details, 'parsed_extraction_cases': len(parsed),
        'semantic_case_exact_on_usable_drafts': ratio(sum(d['score']['semantic_exact'] for d in parsed), len(parsed)),
        'gate_correct_on_usable_drafts': ratio(sum(d['score']['gate_correct'] for d in parsed), len(parsed)),
        'complete_expected_on_attempted': ratio(sum(d['score']['complete_expected_outcome'] for d in attempted), len(attempted)),
        'complete_expected_on_scheduled': ratio(sum(d['score']['complete_expected_outcome'] for d in attempted), 5),
        'correct_unsupported_abstention_on_usable_unsupported': ratio(sum(d['score']['complete_expected_outcome'] for d in unsupported), len(unsupported)),
        'descriptive_case_correctness': ratio(sum(d['score']['complete_expected_outcome'] for d in descriptive), len(descriptive)),
        'usage_coverage': ratio(len(usage), len(calls)), 'total_consumption_known': len(usage) == len(calls),
        'provider_success': ratio(len(successful), len(calls)),
        'provider_errors': [{'case_id': c['case_id'], 'purpose': c['purpose'], 'http_status': c['http_status'],
                             'error_body': c.get('error_body'), 'error': c.get('error')} for c in calls if c.get('error')],
        'successful_latency_ms': {role: [c['latency_ms'] for c in successful if c['purpose'] == role] for role in ('extraction', 'verification')}}


def compare() -> dict[str, Any]:
    """Compare same-case observations without combining pilots or claiming causality."""
    old = ROOT / 'eval/live_extraction/real-pilot-v1'
    new = ROOT / 'eval/live_extraction/real-retest-v2'
    original_index = json.loads((old / 'FINAL_SHA256SUMS.json').read_text())
    assert all(sha(old / name) == digest for name, digest in original_index.items())
    assert sha(old / 'dataset.json') == sha(new / 'dataset.json')
    manifest = json.loads((new / 'manifest.json').read_text())
    assert manifest['source_hashes'] == {str(p.relative_to(ROOT)): sha(p) for p in (ROOT / 'src/ota_verifier').rglob('*.py')}
    assert sha(new / 'runner.py') == manifest['runner_sha256']
    before, after = measurements(old), measurements(new)
    paired = []
    for old_case, new_case in zip(before['cases'], after['cases']):
        assert old_case['case_id'] == new_case['case_id']
        if old_case.get('usable_extraction') and new_case.get('usable_extraction'):
            paired.append({'case_id': old_case['case_id'],
                'old_complete': old_case['score']['complete_expected_outcome'],
                'new_complete': new_case['score']['complete_expected_outcome'],
                'old_semantic': old_case['score']['semantic'], 'new_semantic': new_case['score']['semantic']})
    return {'version': 'real-document-retest-comparison-v2', 'new_provider_requests_by_analysis': 0,
        'dataset_canonical_sha256': before['summary']['dataset_canonical_sha256'],
        'original': before, 'retest': after, 'paired_usable_extraction_cases': paired,
        'limits': ['Owner-reviewed tiny embedded-document development corpus, not automotive-domain expert validation',
                   'Prompt versions, completion cap, spacing and repeated-error policy differ: cannot isolate the cause of any change',
                   'Old NOT_RUN cases are missing coverage, not old semantic successes/failures',
                   'Any planner results use synthetic no-update inventory scaffolding; not vendor schedules',
                   'No automatic additional repair or retest is authorized']}


if __name__ == '__main__':
    result = compare()
    output = ROOT / 'eval/live_extraction/real-retest-v2/comparison.json'
    output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    sys.stdout.write('Saved offline versioned comparison; zero new provider requests.\n')
