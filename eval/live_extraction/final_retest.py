"""Final bounded real-document retest; separately frozen v3 prompts and 4096-token profile."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
import subprocess
import sys
from time import monotonic, perf_counter, sleep
from typing import Any
from urllib.request import HTTPErrorProcessor, HTTPRedirectHandler, build_opener, install_opener

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(Path(__file__).resolve().parent)]
from pilot import sha, write, ratio
from continuation_plan import proposed_settings, budget
from ota_verifier.evaluation import compare_constraints, constraint_signature
from ota_verifier.llm.client import ClientSettings, HttpRequest, LLMClient, LLMError, http_transport
from ota_verifier.llm.evidence import canonical_json, content_hash, evidence_error
from ota_verifier.llm.extractor import SYSTEM_PROMPT as EXTRACT, PROMPT_VERSION as EXTRACT_VERSION, extraction_prompt
from ota_verifier.llm.verifier import SYSTEM_PROMPT as VERIFY, PROMPT_VERSION as VERIFY_VERSION, verification_prompt
from ota_verifier.llm.models import CallRecord, DocumentRequest, ExtractionDraft, FaithfulnessVerdict, Purpose, ExtractionRun
from ota_verifier.llm.pipeline import extract_and_verify, verified_campaign
from ota_verifier.models import PlanningOptions
from ota_verifier.planner import plan_campaign

LOG = logging.getLogger(__name__)
APPROVED_HASH = '2800892519dddf8ccbe7291db6109a7e41acfbde1cd5ed638d2b529eb57e9004'
IDS = [f'real-v2-0{i}' for i in range(1, 6)]


def configuration() -> dict[str, ClientSettings]:
    """Use exactly the approved, offline-tested 4096-token profile."""
    return {role: proposed_settings(role) for role in ('extraction', 'verification')}


def freeze(output: Path) -> None:
    """Freeze the final authorization, unchanged dataset, repaired prompts and controls."""
    source = ROOT / 'eval/live_extraction/real-review-v3'
    index = json.loads((source / 'SHA256SUMS.json').read_text())
    assert all(sha(source / name) == digest for name, digest in index.items())
    plan_path = ROOT / 'eval/live_extraction/reliability-repair-v1/continuation-plan.json'
    approved_plan = json.loads(plan_path.read_text())
    plan = budget()
    assert plan['prompt_hashes'] == approved_plan['prompt_hashes']
    assert plan['rough_worst_case_tokens_including_completion_caps'] == 63997
    raw = json.loads((source / 'candidates.json').read_text(encoding='utf-8'))
    assert content_hash(canonical_json(raw)) == APPROVED_HASH
    assert [row['id'] for row in raw['cases']] == IDS
    configuration()
    assert subprocess.run(['git', 'check-ignore', '-q', '--', '.env'], cwd=ROOT).returncode == 0
    assert not subprocess.run(['git', 'ls-files', '--', '.env'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    prior = ROOT / 'eval/live_extraction/real-pilot-v1/approval.json'
    assert json.loads(prior.read_text())['dataset_canonical_sha256'] == APPROVED_HASH
    output.mkdir(parents=True, exist_ok=False)
    (output / 'dataset.json').write_bytes((source / 'candidates.json').read_bytes())
    (output / 'approved-offline-plan.json').write_bytes(plan_path.read_bytes())
    write(output / 'approval.json', {'status': 'APPROVED_BY_PROJECT_OWNER', 'recorded_at_utc': datetime.now(timezone.utc).isoformat(),
        'timestamp_meaning': 'Time explicit final-retest chat approval was recorded, not authenticated signature time',
        'scope': 'ONE FINAL FIVE-CASE REAL-DOCUMENT DEVELOPMENT RETEST', 'dataset_canonical_sha256': APPROVED_HASH,
        'case_ids': IDS, 'automotive_domain_expert_validation': False, 'maximum_api_requests': 10, 'automatic_retries': 0,
        'maximum_completion_tokens_per_request': 4096, 'estimated_combined_token_budget': 63997,
        'prior_corpus_approval_sha256': sha(prior), 'approval_basis': 'User explicitly approved the final bounded live retest using repaired instructions and offline-tested profile',
        'stop_policy': 'No retry. Stop on second provider/schema error, any authentication/rate error, or exhausted budget. A first other failure allows only independent remaining cases.'})
    write(output / 'manifest.json', {'dataset_canonical_sha256': APPROVED_HASH, 'dataset_file_sha256': sha(output / 'dataset.json'),
        'approval_sha256': sha(output / 'approval.json'), 'provider': 'groq', 'model': 'openai/gpt-oss-20b', 'schema_mode': 'json',
        'max_completion_tokens': 4096, 'timeout_seconds': 60, 'maximum_requests': 10, 'minimum_start_interval_seconds': 90,
        'wall_budget_seconds': 1200, 'estimated_combined_token_ceiling': 63997, 'automatic_retries': 0,
        'prompt_versions': plan['prompt_versions'], 'prompt_hashes': plan['prompt_hashes'],
        'scoring': json.loads((ROOT / 'eval/live_extraction/real-pilot-v1/manifest.json').read_text())['scoring'],
        'source_hashes': {str(p.relative_to(ROOT)): sha(p) for p in (ROOT / 'src/ota_verifier').rglob('*.py')},
        'python': sys.version, 'stop_policy': 'Latest user authorization: repeated errors or exhausted budget; immediate stop on authentication/rate-limit errors',
        'quota_note': 'First-request quota unknown. Subsequent reservations checked against fresh headers and reset times. Token estimates are not tokenizer-certified bounds.'})
    (output / 'runner.py').write_bytes(Path(__file__).read_bytes())


def score_case(row: dict[str, Any], run: ExtractionRun) -> dict[str, Any]:
    """Score frozen approved meaning, supporting evidence, issue classification and gate separately."""
    gold = ExtractionDraft.model_validate_json(canonical_json(row['proposed_draft']))
    actual = run.draft
    found = actual.constraints if actual else ()
    metrics = compare_constraints(tuple(e.constraint for e in gold.constraints), tuple(e.constraint for e in found))
    def bindings(entries: Any) -> Counter:
        return Counter((constraint_signature(e.constraint), e.evidence.document_id, e.evidence.start_char,
                        e.evidence.end_char, e.constraint.source_text) for e in entries)
    def issues(entries: Any) -> Counter:
        return Counter((i.kind, i.evidence.document_id, i.evidence.start_char, i.evidence.end_char, i.source_text) for i in entries)
    matching = sum((bindings(gold.constraints) & bindings(found)).values())
    same_issues = actual is not None and issues(gold.issues) == issues(actual.issues)
    exact_draft = actual is not None and bindings(gold.constraints) == bindings(found) and same_issues
    expected_blocked = row['expected_gate'] == 'blocked'
    gate_correct = (run.status == 'blocked') == expected_blocked
    gold_signatures = Counter(constraint_signature(e.constraint) for e in gold.constraints)
    found_signatures = Counter(constraint_signature(e.constraint) for e in found)
    return {'case_id': row['id'], 'semantic': metrics.model_dump(mode='json'),
            'semantic_exact': actual is not None and gold_signatures == found_signatures,
            'false_positive_signatures': list((found_signatures - gold_signatures).elements()),
            'false_negative_signatures': list((gold_signatures - found_signatures).elements()),
            'gold_constraints': len(gold.constraints), 'emitted_constraints': len(found), 'correct_bindings': matching,
            'literal_valid_citations': sum(evidence_error(run.request, e.evidence, e.constraint.source_text) is None for e in found),
            'exact_issue_set': same_issues, 'exact_draft': exact_draft, 'gate_correct': gate_correct,
            'complete_expected_outcome': exact_draft and gate_correct,
            'expected_gate': 'blocked' if expected_blocked else 'ready', 'actual_gate': run.status,
            'verifier_called': run.verification is not None,
            'verifier_correct': run.verification.faithful == exact_draft if run.verification is not None else None,
            'verifier_reference_valid': not any(i.code in ('verification_reference', 'verification_coverage') for i in run.issues) if run.verification else None,
            'expected_issue_kinds': [issue.kind for issue in gold.issues],
            'actual_issue_kinds': [issue.kind for issue in actual.issues] if actual else None}


def execute(output: Path) -> None:
    """Run five cases serially with real transport, at most ten HTTP requests and the approved profile, no retries."""
    assert not (output / 'started.json').exists(), 'Refusing to restart a started evaluation'
    manifest = json.loads((output / 'manifest.json').read_text())
    assert sha(output / 'dataset.json') == manifest['dataset_file_sha256']
    assert sha(output / 'approval.json') == manifest['approval_sha256']
    assert manifest['prompt_hashes'] == {'extraction': content_hash(EXTRACT), 'verification': content_hash(VERIFY)}
    from portable_source_hashes import verify_portable_sources
    assert verify_portable_sources(
        ROOT,
        ROOT / 'eval/live_extraction/real-retest-v2/portable_source_hashes.json'
    )
    data = json.loads((output / 'dataset.json').read_text(encoding='utf-8'))
    assert content_hash(canonical_json(data)) == APPROVED_HASH
    settings = configuration()
    secrets = tuple(s.api_key.get_secret_value() for s in settings.values())
    write(output / 'started.json', {'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'dataset_sha256': APPROVED_HASH})
    started = monotonic()
    reserved_tokens = 0
    boundary_failures = 0
    next_allowed = started
    calls: list[dict[str, Any]] = []
    active: dict[str, Any] = {}
    case_id = ''

    class Observe(HTTPErrorProcessor):
        def http_response(self, request: Any, response: Any) -> Any:
            active['http_status'] = response.code
            headers = {k.lower(): v for k, v in response.headers.items()}
            active['response_headers'] = {k: v for k, v in headers.items() if k.startswith('x-ratelimit-') or k in ('retry-after', 'content-type', 'server')}
            if response.code >= 400:
                active['error_body'] = response.read(4096).decode('utf-8', errors='replace')
            return super().http_response(request, response)
        https_response = http_response

    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, *args: Any, **kwargs: Any) -> None:
            raise LLMError('Redirect refused; no second HTTP request permitted')

    install_opener(build_opener(Observe(), NoRedirect()))

    class ObservedClient:
        def __init__(self, purpose: Purpose) -> None:
            self.purpose = purpose

        def generate_json(self, *, purpose: Purpose, system_prompt: str, user_prompt: str,
                          schema: dict[str, Any], prompt_version: str) -> CallRecord:
            nonlocal active, next_allowed, reserved_tokens
            if purpose != self.purpose or len(calls) >= 10:
                raise LLMError('Fixed role/request budget exhausted')
            if sum(bool(call.get('error')) for call in calls) >= 2:
                raise LLMError('Repeated provider failures; no further requests allowed')
            while monotonic() < next_allowed:
                if monotonic() - started >= 1140:
                    raise LLMError('Wall budget exhausted during quota pacing')
                remaining = next_allowed - monotonic()
                write(output / 'progress.json', {'case_id': case_id, 'next_role': purpose, 'phase': 'PACING',
                                                'wait_seconds': round(remaining, 1), 'requests': len(calls)})
                sleep(min(5, remaining))
            if monotonic() - started >= 1140:
                raise LLMError('Wall budget exhausted; no additional request')
            active = {'case_id': case_id, 'purpose': purpose, 'timestamp_utc': datetime.now(timezone.utc).isoformat(),
                      'provider': 'groq', 'model': 'openai/gpt-oss-20b', 'request_sent': False, 'http_status': None, 'usage': None}
            calls.append(active)
            begin = perf_counter()

            def real_transport(request: HttpRequest) -> dict[str, Any]:
                nonlocal next_allowed, reserved_tokens
                assert not active['request_sent']
                assert request.url == 'https://api.groq.com/openai/v1/chat/completions'
                assert request.body['model'] == 'openai/gpt-oss-20b'
                assert 'proposed_draft' not in user_prompt and 'expected_gate' not in user_prompt
                # Character heuristic is conservative operational scheduling, not measured token usage.
                estimate = (sum(len(m['content']) for m in request.body['messages']) + 2) // 3 + 4096
                reservation_with_margin = estimate + 512
                if reserved_tokens + estimate > 63997:
                    raise LLMError('Combined estimated token budget exhausted before sending')
                limit = int(calls[-2].get('response_headers', {}).get('x-ratelimit-limit-tokens', '8000')) if len(calls) > 1 else 8000
                if reservation_with_margin > limit:
                    raise LLMError('Estimated single-request token reservation exceeds observed/historical TPM; stop without sending')
                if len(calls) > 1:
                    previous = calls[-2].get('response_headers', {})
                    if not all(key in previous for key in ('x-ratelimit-limit-tokens', 'x-ratelimit-remaining-tokens', 'x-ratelimit-remaining-requests')):
                        raise LLMError('Fresh rate-limit metadata missing; stop before another request')
                reserved_tokens += estimate
                active['estimated_token_reservation'] = estimate
                active['estimated_token_reservation_with_margin'] = reservation_with_margin
                active['request_sent'] = True
                active['request_sha256'] = content_hash(canonical_json(request.body))
                next_allowed = monotonic() + 90
                write(output / 'calls.json', calls, secrets)
                envelope = http_transport(request)
                active['usage'] = envelope.get('usage')
                active['response_model'] = envelope.get('model')
                return envelope

            try:
                call = LLMClient(settings[purpose], transport=real_transport).generate_json(
                    purpose=purpose, system_prompt=system_prompt, user_prompt=user_prompt, schema=schema, prompt_version=prompt_version)
                assert call.origin == 'live' and call.provider == 'groq'
                active['call'] = call.model_dump(mode='json')
                return call
            except LLMError as error:
                active['error'] = str(error)
                if error.record is not None:
                    active['call'] = error.record.model_dump(mode='json')
                raise
            finally:
                active['latency_ms'] = round((perf_counter() - begin) * 1000, 3)
                headers = active.get('response_headers', {})
                for resource, threshold in (('tokens', 8000), ('requests', 1)):
                    remaining = headers.get('x-ratelimit-remaining-' + resource)
                    if remaining is not None and int(remaining) < threshold:
                        reset = headers.get('x-ratelimit-reset-' + resource, '')
                        if not reset:
                            active['error'] = 'Insufficient quota without usable reset metadata; stop'
                        seconds = sum(float(n) * {'h': 3600, 'm': 60, 's': 1, 'ms': .001}[u]
                                      for n, u in re.findall(r'(\d+(?:\.\d+)?)(ms|h|m|s)', reset))
                        next_allowed = max(next_allowed, monotonic() + seconds + 1)
                write(output / 'calls.json', calls, secrets)
                LOG.info('%s %s HTTP=%s requests=%s', case_id, purpose, active['http_status'], len(calls))

    outcomes = []
    stop_reason = None
    for row in data['cases']:
        if stop_reason:
            outcomes.append({'case_id': row['id'], 'status': 'NOT_RUN', 'reason': stop_reason})
            continue
        case_id = row['id']
        request = DocumentRequest.model_validate_json(canonical_json(row['request_scaffold']))
        run = extract_and_verify(request, ObservedClient('extraction'), ObservedClient('verification'))
        score = score_case(row, run)
        planning = None
        if run.status == 'ready':
            planning = plan_campaign(verified_campaign(run), PlanningOptions(timeout_ms=5000, max_parallel=2)).model_dump(mode='json')
        outcome = {'case_id': row['id'], 'status': 'ATTEMPTED', 'run': run.model_dump(mode='json'), 'score': score,
                   'planning': planning, 'planning_scope': 'Synthetic inventory scaffold; real-source extraction only, not vendor update schedule'}
        outcomes.append(outcome)
        write(output / (row['id'] + '.json'), outcome, secrets)
        if any(i.code == 'llm_boundary_error' for i in run.issues):
            boundary_failures += 1
        fatal = any(c.get('http_status') in (401, 403, 429) or (c.get('error') and (not c.get('request_sent') or 'quota' in c['error'].lower() or 'budget' in c['error'].lower())) for c in calls)
        if boundary_failures >= 2 or fatal:
            stop_reason = 'Repeated provider/schema failures, authentication/rate failure, or budget exhaustion; no retries'
        write(output / 'outcomes.json', outcomes, secrets)
    scores = [o['score'] for o in outcomes if o['status'] == 'ATTEMPTED']
    tp = sum(s['semantic']['true_positives'] for s in scores)
    fp = sum(s['semantic']['false_positives'] for s in scores)
    fn = sum(s['semantic']['false_negatives'] for s in scores)
    emitted = sum(s['emitted_constraints'] for s in scores)
    gold = sum(s['gold_constraints'] for s in scores)
    bindings = sum(s['correct_bindings'] for s in scores)
    reviewed = [s for s in scores if s['verifier_called']]
    correct_reviewed = [s for s in reviewed if s['exact_draft']]
    bad_reviewed = [s for s in reviewed if not s['exact_draft']]
    summary = {'stratum': 'FINAL REAL-DOCUMENT DEVELOPMENT RETEST', 'dataset_canonical_sha256': APPROVED_HASH,
        'provider': 'groq', 'model': 'openai/gpt-oss-20b', 'requests': len(calls), 'http_requests_sent': sum(c['request_sent'] for c in calls),
        'maximum_requests': 10, 'estimated_tokens_reserved': reserved_tokens, 'estimated_token_ceiling': 63997, 'automatic_retries': 0, 'attempted_cases': len(scores), 'scheduled_cases': 5,
        'not_run_cases': 5 - len(scores), 'stop_reason': stop_reason, 'wall_elapsed_seconds': round(monotonic() - started, 3),
        'semantic_counts': {'tp': tp, 'fp': fp, 'fn': fn}, 'precision': ratio(tp, tp + fp), 'recall': ratio(tp, tp + fn),
        'f1': ratio(2 * tp, 2 * tp + fp + fn), 'semantic_case_exact_match': ratio(sum(s['semantic_exact'] for s in scores), len(scores)),
        'grounding_precision': ratio(bindings, emitted), 'grounding_recall': ratio(bindings, gold),
        'literal_citation_validity': ratio(sum(s['literal_valid_citations'] for s in scores), emitted),
        'draft_exact_match': ratio(sum(s['exact_draft'] for s in scores), len(scores)),
        'gate_correctness': ratio(sum(s['gate_correct'] for s in scores), len(scores)),
        'complete_expected_outcome': ratio(sum(s['complete_expected_outcome'] for s in scores), len(scores)),
        'hallucination_over_extraction_proxy': ratio(fp, emitted),
        'verifier_correctness': ratio(sum(s['verifier_correct'] for s in reviewed), len(reviewed)),
        'verifier_false_rejection': ratio(sum(not s['verifier_correct'] for s in correct_reviewed), len(correct_reviewed)),
        'verifier_false_acceptance': ratio(sum(not s['verifier_correct'] for s in bad_reviewed), len(bad_reviewed)),
        'http_status_counts': dict(Counter(str(c['http_status']) for c in calls)),
        'token_usage': {k: sum((c.get('usage') or {}).get(k, 0) for c in calls) for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')},
        'latency_ms_by_role': {role: [c['latency_ms'] for c in calls if c['purpose'] == role] for role in ('extraction', 'verification')},
        'production_sources_unchanged': manifest['source_hashes'] == {str(p.relative_to(ROOT)): sha(p) for p in (ROOT / 'src/ota_verifier').rglob('*.py')},
        'source_dataset_unchanged': sha(ROOT / 'eval/live_extraction/real-review-v3/candidates.json') == manifest['dataset_file_sha256'],
        'all_cases_correct': len(scores) == 5 and all(s['complete_expected_outcome'] for s in scores)}
    write(output / 'outcomes.json', outcomes, secrets)
    write(output / 'summary.json', summary, secrets)
    write(output / 'SHA256SUMS.json', {p.name: sha(p) for p in output.iterdir() if p.is_file() and p.name != 'SHA256SUMS.json'})
    LOG.info('Evaluation complete: requests=%s cases=%s stop=%s', len(calls), len(scores), stop_reason)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('freeze', 'execute'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    (freeze if args.action == 'freeze' else execute)(args.output)
