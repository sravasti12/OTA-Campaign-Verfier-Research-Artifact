"""Recompute approved pilot metrics from saved evidence; never invoke a provider."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(Path(__file__).resolve().parent)]
from pilot import score, sha
from ota_verifier.benchmark.corpus import corpus_hash, load_corpus
from ota_verifier.data.generate import SyntheticCase
from ota_verifier.evaluation import CaseEvaluation, compare_constraints, constraint_signature
from ota_verifier.llm.evidence import canonical_json, content_hash, evidence_error


def recover() -> dict[str, object]:
    """Verify original hashes and recompute distinct metrics without planning or inference."""
    folder = ROOT / 'eval/live_extraction/synthetic-pilot-v1'
    def read(name: str) -> object:
        return json.loads((folder / name).read_text(encoding='utf-8'))
    index = read('execution-SHA256SUMS.json')
    assert all(sha(folder / name) == digest for name, digest in index.items())
    dataset, approval, manifest = (read(name) for name in ('dataset.json', 'approval.json', 'manifest.json'))
    digest = content_hash(canonical_json(dataset))
    assert digest == approval['dataset_canonical_sha256'] == manifest['dataset_canonical_sha256']
    assert digest == '5908bf34ff185eaaa3a7000b889e4273e6f806b9619af3d71923aead4fd91c52'
    assert corpus_hash(load_corpus()) == manifest['source_corpus_sha256']
    assert all(sha(ROOT / name) == digest for name, digest in manifest['source_hashes'].items())
    cases = [SyntheticCase.model_validate_json(canonical_json(case)) for case in dataset['cases']]
    records = [read(case.id + '.json') for case in cases]
    evaluations = [CaseEvaluation.model_validate_json(canonical_json(row['evaluation'])) for row in records]
    assert all(row['run'] == evaluation.run.model_dump(mode='json') for row, evaluation in zip(records, evaluations))
    assert records == read('outcomes.json')
    for case, evaluation in zip(cases, evaluations):
        assert case.request == evaluation.run.request
        if not case.expected_blocked:
            assert compare_constraints(case.truth_campaign.constraints, tuple(entry.constraint for entry in evaluation.run.draft.constraints)) == evaluation.metrics
    metrics = score(evaluations, cases)
    original = read('summary.json')['metrics']
    assert all(original[key] == value for key, value in metrics.items())
    literal_valid = emitted = bound = gate_correct = complete = reviewed_correct = false_rejections = 0
    per_case = []
    for case, row, evaluation in zip(cases, records, evaluations):
        run = evaluation.run
        def bindings(entries: object) -> Counter:
            return Counter((constraint_signature(entry.constraint), entry.evidence.document_id,
                            entry.evidence.start_char, entry.evidence.end_char) for entry in entries)
        matched = sum((bindings(case.reference_draft.constraints) & bindings(run.draft.constraints)).values())
        exact_draft = bindings(case.reference_draft.constraints) == bindings(run.draft.constraints) and row['exact_expected_issue_set']
        gate_ok = (run.status == 'blocked') == case.expected_blocked
        gate_correct += gate_ok
        complete += exact_draft and gate_ok
        bound += matched
        emitted += len(run.draft.constraints)
        literal_valid += sum(evidence_error(case.request, entry.evidence, entry.constraint.source_text) is None for entry in run.draft.constraints)
        if run.verification is not None and exact_draft:
            reviewed_correct += 1
            false_rejections += not run.verification.faithful
        per_case.append({'case_id': case.id, 'correct_semantic_evidence_bindings': matched,
                         'emitted_constraints': len(run.draft.constraints), 'draft_exact': exact_draft,
                         'gate_correct': gate_ok, 'pipeline_status': run.status,
                         'planner_status': evaluation.planning_status})
    calls = read('calls.json')
    assert len(calls) == 4 and all(call['http_status'] == 200 and call['request_sent'] and
        call['call']['origin'] == 'live' and call['provider'] == 'groq' and call['model'] == 'openai/gpt-oss-20b' for call in calls)
    usage = {key: sum(call['usage'][key] for call in calls) for key in ('prompt_tokens', 'completion_tokens', 'total_tokens')}
    assert usage == original['token_usage']
    return {'recovered_at_utc': datetime.now(timezone.utc).isoformat(), 'mode': 'OFFLINE_SAVED_PREDICTIONS_ONLY',
            'new_api_requests': 0, 'original_execution_hashes_verified': len(index),
            'dataset_canonical_sha256': digest, 'production_sources_unchanged': True, 'corpus_unchanged': True,
            'recomputed_metrics': metrics, 'cases': per_case, 'literal_valid_citations': [literal_valid, emitted],
            'correct_semantic_evidence_bindings': [bound, emitted], 'gate_correctness': [gate_correct, len(cases)],
            'complete_expected_outcome': [complete, len(cases)],
            'verifier_false_rejection_on_correct_reviewed_drafts': [false_rejections, reviewed_correct],
            'historical_api_requests': len(calls), 'token_usage': usage}


if __name__ == '__main__':
    result = recover()
    (ROOT / 'eval/live_extraction/synthetic-pilot-v1/recovery.json').write_text(
        json.dumps(result, indent=2), encoding='utf-8')
    sys.stdout.write(json.dumps(result, indent=2) + '\n')
