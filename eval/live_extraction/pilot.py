"""Approved three-case synthetic development pilot; real HTTP, bounded calls, no retries."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
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
sys.path[:0] = [str(ROOT/'src')]
from ota_verifier.benchmark.corpus import corpus_hash, load_corpus
from ota_verifier.benchmark.metrics import extraction_metrics
from ota_verifier.data.generate import SyntheticCase
from ota_verifier.evaluation import constraint_signature, evaluate_case
from ota_verifier.llm.client import ClientSettings, LLMClient, LLMError, USER_AGENT, http_transport
from ota_verifier.llm.evidence import canonical_json, content_hash, evidence_error
from ota_verifier.llm.extractor import SYSTEM_PROMPT as EXTRACTION_SYSTEM, PROMPT_VERSION as EXTRACTION_VERSION
from ota_verifier.llm.models import CallRecord, Purpose
from ota_verifier.llm.pipeline import extract_and_verify
from ota_verifier.llm.verifier import SYSTEM_PROMPT as VERIFICATION_SYSTEM, PROMPT_VERSION as VERIFICATION_VERSION
from ota_verifier.models import PlanningOptions

IDS = ('clear-42','order_conflict-44','unsupported-47')
LOG = logging.getLogger(__name__)


def sha(path: Path) -> str:
    """Hash exact bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: Any, secrets: tuple[str,...] = ()) -> None:
    """Atomically save redacted UTF-8 evidence without request headers."""
    text = json.dumps(value,indent=2,ensure_ascii=False)
    for secret in secrets:
        if secret:
            text = text.replace(secret,'[REDACTED]')
    text = re.sub(r'org_[A-Za-z0-9_-]+','[ORGANIZATION REDACTED]',text)
    temp = path.with_suffix(path.suffix+'.tmp')
    temp.write_text(text,encoding='utf-8',newline='\n')
    temp.replace(path)


def freeze(output: Path) -> None:
    """Record the user's explicit review, unchanged selected labels, settings and budget before inference."""
    output.mkdir(parents=True,exist_ok=False)
    corpus = load_corpus()
    original = json.loads((ROOT/'eval/live_extraction/readiness-v1/pilot-review-packet.json').read_text(encoding='utf-8'))
    cases = [next(case for case in corpus.development if case.id==identifier) for identifier in IDS]
    assert [row['case'] for row in original['cases']] == [case.model_dump(mode='json') for case in cases]
    dataset = {'format':'synthetic-development-pilot-v1','origin':'SYNTHETIC DEVELOPMENT PILOT',
               'source_corpus_sha256':corpus_hash(corpus),'cases':[case.model_dump(mode='json') for case in cases]}
    digest = content_hash(canonical_json(dataset))
    write(output/'dataset.json',dataset)
    write(output/'approval.json',{'status':'APPROVED_BY_PROJECT_OWNER','recorded_at_utc':datetime.now(timezone.utc).isoformat(),
        'timestamp_meaning':'Time this explicit chat approval was recorded, not an authenticated signature timestamp.',
        'reviewer':'Project owner; self-reported explicit user instruction in this conversation',
        'scope':'SYNTHETIC DEVELOPMENT PILOT ONLY','dataset_canonical_sha256':digest,
        'case_ids':list(IDS),'automotive_domain_expert_validation':False,
        'approval_basis':'User personally reviewed and approved frozen expected labels, exact source evidence and gate outcomes.',
        'specific_adjudications':{'order_conflict-44':'Preserve both contradictory ordering rules; deterministic planner decides infeasibility.',
                                 'unsupported-47':'Zero formal constraints and cited unsupported_requirement issue.'},
        'maximum_api_requests':6,'automatic_retries':0,'real_document_approval':False})
    settings = {role:ClientSettings.from_env(role).model_copy(update={'max_tokens':2048,'timeout_seconds':45.0})
                for role in ('extraction','verification')}
    assert all(s.provider=='groq' and s.model=='openai/gpt-oss-20b' for s in settings.values())
    assert all(s.schema_mode=='json' for s in settings.values()), 'Do not silently change the approved configured output mode'
    write(output/'manifest.json',{'dataset_canonical_sha256':digest,'dataset_file_sha256':sha(output/'dataset.json'),
        'approval_file_sha256':sha(output/'approval.json'),'case_ids':list(IDS),'model':'openai/gpt-oss-20b',
        'provider':'groq','schema_mode':'json','temperature':0,'max_output_tokens':2048,'call_timeout_seconds':45,
        'min_start_interval_seconds':70,'maximum_api_requests':6,'wall_budget_seconds':900,
        'explanation_calls':0,'automatic_retries':0,'source_corpus_sha256':corpus_hash(corpus),
        'stop_on':['schema failure','provider failure including first HTTP 429','wall/request budget exhausted','input/prompt/source drift'],
        'scoring':{'semantics':'Normalized constraint multiset on attempted supported cases; preserve parseable drafts even if verification blocks.',
                   'unsupported':'Separately score zero constraints plus correctly cited unsupported_requirement and blocked gate.',
                   'exact_match':'Report supported semantic exact match separately from complete case extraction/issue/gate correctness.',
                   'hallucination_proxy':'False-positive semantic constraints / emitted constraints on supported cases; not proof of fabricated quotes.',
                   'not_run':'Retain scheduled not-run cases; exclude them from attempted-only accuracy denominators.'},
        'prompt_versions':{'extraction':EXTRACTION_VERSION,'verification':VERIFICATION_VERSION},
        'system_prompt_sha256':{'extraction':content_hash(EXTRACTION_SYSTEM),'verification':content_hash(VERIFICATION_SYSTEM)},
        'source_hashes':{str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'src/ota_verifier').rglob('*.py')},
        'python':sys.version,'user_agent':USER_AGENT})
    (output/'runner.py').write_bytes(Path(__file__).read_bytes())
    LOG.info('Frozen approved dataset: %s',digest)


def ratio(numerator: int, denominator: int) -> dict[str,Any]:
    """Keep undefined empty denominators null."""
    return {'numerator':numerator,'denominator':denominator,'value':numerator/denominator if denominator else None}


def score(evaluations: list[Any], cases: list[SyntheticCase]) -> dict[str,Any]:
    """Aggregate existing production metrics without allowing case errors to cancel."""
    by_id = {case.id:case for case in cases}
    pairs = tuple((by_id[row.case_id],row.run) for row in evaluations)
    supported = [row for row in evaluations if not row.expected_blocked]
    tp = sum(row.metrics.true_positives for row in supported)
    fp = sum(row.metrics.false_positives for row in supported)
    fn = sum(row.metrics.false_negatives for row in supported)
    exact = sum(not row.metrics.false_positives and not row.metrics.false_negatives for row in supported)
    return {'semantic_counts':{'true_positives':tp,'false_positives':fp,'false_negatives':fn},
        'precision':ratio(tp,tp+fp),'recall':ratio(tp,tp+fn),'f1':ratio(2*tp,2*tp+fp+fn),
        'supported_semantic_exact_match':ratio(exact,len(supported)),
        'over_extraction_hallucination_proxy':ratio(fp,tp+fp),
        'existing_extraction_metrics':extraction_metrics(pairs).model_dump(mode='json'),
        'real_document_metrics':None,'stratum':'SYNTHETIC DEVELOPMENT PILOT',
        'attempted_cases':len(evaluations),'scheduled_cases':len(cases),'accuracy_scope':'Attempted cases only; NOT_RUN cases remain in results.'}


def execute(output: Path) -> int:
    """Execute the approved frozen pilot serially, at most once, without automatic retries."""
    assert not (output/'started.json').exists(), 'Refusing to rerun a started pilot'
    manifest = json.loads((output/'manifest.json').read_text())
    assert sha(output/'dataset.json')==manifest['dataset_file_sha256']
    assert sha(output/'approval.json')==manifest['approval_file_sha256']
    raw = json.loads((output/'dataset.json').read_text())
    assert content_hash(canonical_json(raw))==manifest['dataset_canonical_sha256']
    assert corpus_hash(load_corpus())==manifest['source_corpus_sha256']
    assert manifest['source_hashes']=={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'src/ota_verifier').rglob('*.py')}
    assert content_hash(EXTRACTION_SYSTEM)==manifest['system_prompt_sha256']['extraction']
    assert content_hash(VERIFICATION_SYSTEM)==manifest['system_prompt_sha256']['verification']
    assert subprocess.run(['git','check-ignore','-q','--','.env'],cwd=ROOT).returncode==0
    assert not subprocess.run(['git','ls-files','--','.env'],cwd=ROOT,capture_output=True,text=True).stdout.strip()
    cases = [SyntheticCase.model_validate_json(canonical_json(case)) for case in raw['cases']]
    settings = {purpose:ClientSettings.from_env(purpose).model_copy(update={'max_tokens':2048,'timeout_seconds':45.0})
                for purpose in ('extraction','verification')}
    assert all(s.provider=='groq' and s.model==manifest['model'] and s.schema_mode==manifest['schema_mode'] for s in settings.values())
    secrets = tuple(s.api_key.get_secret_value() for s in settings.values())
    write(output/'started.json',{'timestamp_utc':datetime.now(timezone.utc).isoformat(),'dataset_sha256':manifest['dataset_canonical_sha256']})
    started = monotonic()
    last_start: float | None = None
    next_allowed = started
    records: list[dict[str,Any]] = []
    active: dict[str,Any] = {}
    case_id = ''
    stop_reason: str | None = None

    class Observe(HTTPErrorProcessor):
        def http_response(self, request: Any, response: Any) -> Any:
            active['http_status'] = response.code
            headers = {k.lower():v for k,v in response.headers.items()}
            active['response_headers'] = {k:v for k,v in headers.items() if k.startswith('x-ratelimit-') or k in
                ('retry-after','server','content-type','x-request-id','cf-ray')}
            if response.code>=400:
                active['error_body'] = response.read(4096).decode('utf-8',errors='replace')
            return super().http_response(request,response)
        https_response = http_response

    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, request: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
            raise LLMError('Redirect refused by fixed pilot budget')

    install_opener(build_opener(Observe(),NoRedirect()))

    class ObservedClient:
        def __init__(self, purpose: Purpose) -> None:
            self.purpose = purpose
        def generate_json(self, *, purpose: Purpose, system_prompt: str, user_prompt: str,
                          schema: dict[str,Any], prompt_version: str) -> CallRecord:
            nonlocal active,last_start,next_allowed
            if purpose!=self.purpose or len(records)>=6:
                raise LLMError('Pilot role or request budget exceeded')
            while monotonic()<next_allowed:
                if monotonic()-started>=900:
                    raise LLMError('Pilot wall budget exhausted before request')
                remaining = next_allowed-monotonic()
                write(output/'progress.json',{'case_id':case_id,'next_role':purpose,'phase':'PACING','wait_seconds':round(remaining,1),'requests':len(records)})
                sleep(min(5,remaining))
            if monotonic()-started>=855:
                raise LLMError('Insufficient experiment wall budget for another request')
            active = {'case_id':case_id,'purpose':purpose,'timestamp_utc':datetime.now(timezone.utc).isoformat(),
                      'http_status':None,'model':manifest['model'],'provider':'groq','usage':None,'request_sent':False}
            records.append(active)
            call_started = perf_counter()
            active['pacing_wait_ms'] = round((monotonic()-(last_start or started))*1000,3) if last_start else 0

            def real_transport(request: Any) -> dict[str,Any]:
                nonlocal last_start,next_allowed
                assert not active['request_sent'], 'No second HTTP request permitted for this call'
                assert 'truth_campaign' not in user_prompt and 'reference_draft' not in user_prompt
                active['request_sent'] = True
                last_start = monotonic()
                next_allowed = last_start+70
                active['request_sha256'] = content_hash(canonical_json(request.body))
                write(output/'calls.json',records,secrets)
                envelope = http_transport(request)
                active['usage'] = envelope.get('usage')
                active['response_model'] = envelope.get('model')
                return envelope

            try:
                call = LLMClient(settings[purpose],transport=real_transport).generate_json(purpose=purpose,
                    system_prompt=system_prompt,user_prompt=user_prompt,schema=schema,prompt_version=prompt_version)
                assert call.origin=='live' and call.provider=='groq'
                active['call'] = call.model_dump(mode='json')
                return call
            except LLMError as error:
                active['error'] = str(error)
                if error.record is not None:
                    active['call'] = error.record.model_dump(mode='json')
                raise
            finally:
                active['latency_ms'] = round((perf_counter()-call_started)*1000,3)
                headers = active.get('response_headers',{})
                # If fewer tokens remain than a conservative whole-request allowance,
                # honor the server's refill time before any next call.
                if int(headers.get('x-ratelimit-remaining-tokens','8000'))<6000:
                    token_reset = headers.get('x-ratelimit-reset-tokens','')
                    seconds = sum(float(n)*(60 if unit=='m' else .001 if unit=='ms' else 1)
                                  for n,unit in re.findall(r'(\d+(?:\.\d+)?)(ms|m|s)',token_reset))
                    next_allowed = max(next_allowed,monotonic()+seconds+1)
                write(output/'calls.json',records,secrets)
                LOG.info('%s %s HTTP=%s calls=%s',case_id,purpose,active['http_status'],len(records))

    evaluations = []
    outcomes = []
    for case in cases:
        if stop_reason:
            outcomes.append({'case_id':case.id,'status':'NOT_RUN','reason':stop_reason})
            continue
        case_id = case.id
        start = perf_counter()
        run = extract_and_verify(case.request,ObservedClient('extraction'),ObservedClient('verification'))
        evaluation = evaluate_case(case,run,run_stress=False,options=PlanningOptions(timeout_ms=5000,max_parallel=2))
        evaluations.append(evaluation)
        actual = tuple(entry.constraint for entry in run.draft.constraints) if run.draft else ()
        expected = Counter(constraint_signature(rule) for rule in case.truth_campaign.constraints) if not case.expected_blocked else Counter()
        found = Counter(constraint_signature(rule) for rule in actual)
        expected_issues = {(i.kind,i.evidence.document_id,i.evidence.start_char,i.evidence.end_char,i.source_text) for i in case.reference_draft.issues}
        found_issues = {(i.kind,i.evidence.document_id,i.evidence.start_char,i.evidence.end_char,i.source_text) for i in run.draft.issues} if run.draft else set()
        citation_errors = [evidence_error(case.request,entry.evidence,entry.constraint.source_text) for entry in run.draft.constraints] if run.draft else []
        outcome = {'case_id':case.id,'status':'ATTEMPTED','run':run.model_dump(mode='json'),
                   'evaluation':evaluation.model_dump(mode='json'),'pipeline_elapsed_ms':round((perf_counter()-start)*1000,3),
                   'false_positive_signatures':list((found-expected).elements()),'false_negative_signatures':list((expected-found).elements()),
                   'exact_expected_issue_set':expected_issues==found_issues,'zero_constraints':not actual,
                   'citation_errors':[e for e in citation_errors if e],
                   'complete_expected_outcome':run.draft is not None and expected==found and expected_issues==found_issues and
                       (run.status=='blocked')==case.expected_blocked}
        outcomes.append(outcome)
        write(output/(case.id+'.json'),outcome,secrets)
        if any(row.get('error') for row in records) or any(i.code=='llm_boundary_error' for i in run.issues):
            stop_reason = 'Provider/schema/budget failure; no automatic retry or continuation'
        write(output/'progress.json',{'completed_cases':len(evaluations),'requests':len(records),'stop_reason':stop_reason})
    metrics = score(evaluations,cases)
    complete = sum(bool(row.get('complete_expected_outcome')) for row in outcomes)
    unsupported = [row for row in outcomes if row['case_id']=='unsupported-47' and row['status']=='ATTEMPTED']
    metrics['complete_case_outcome_accuracy'] = ratio(complete,len(evaluations))
    metrics['correct_cited_unsupported_abstention'] = ratio(sum(row['complete_expected_outcome'] for row in unsupported),len(unsupported))
    metrics['semantic_false_acceptance'] = ratio(sum(row.accepted_semantic_error for row in evaluations),sum(row.run.status=='ready' for row in evaluations))
    metrics['latency_ms_by_role'] = {role:[row['latency_ms'] for row in records if row['purpose']==role] for role in ('extraction','verification')}
    metrics['provider_responses'] = dict(Counter(str(row['http_status']) for row in records))
    metrics['token_usage'] = {name:sum((row.get('usage') or {}).get(name,0) for row in records) for name in ('prompt_tokens','completion_tokens','total_tokens')}
    summary = {'stratum':'SYNTHETIC DEVELOPMENT PILOT','model':manifest['model'],'dataset_sha256':manifest['dataset_canonical_sha256'],
        'requests':len(records),'http_requests_sent':sum(row['request_sent'] for row in records),'maximum_requests':6,
        'scheduled_case_ids':list(IDS),'attempted_cases':len(evaluations),'not_run_cases':sum(row['status']=='NOT_RUN' for row in outcomes),
        'stop_reason':stop_reason,'completed_without_provider_or_schema_failure':stop_reason is None,
        'all_cases_correct':complete==len(cases),'wall_elapsed_seconds':round(monotonic()-started,3),
        'metrics':metrics,'production_sources_unchanged':manifest['source_hashes']=={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'src/ota_verifier').rglob('*.py')},
        'corpus_unchanged':corpus_hash(load_corpus())==manifest['source_corpus_sha256'],
        'real_document_approval':False,'real_document_requests':0,'explanation_requests':0}
    write(output/'outcomes.json',outcomes,secrets)
    write(output/'summary.json',summary,secrets)
    write(output/'SHA256SUMS.json',{p.name:sha(p) for p in output.iterdir() if p.is_file() and p.name!='SHA256SUMS.json'})
    LOG.info('Pilot finished: %s',canonical_json(summary))
    return 0


def main() -> int:
    """Freeze the approved pilot or execute its new, once-only evidence directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('freeze','execute'))
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    if args.action=='freeze':
        freeze(args.output)
        return 0
    return execute(args.output)


if __name__=='__main__':
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s')
    raise SystemExit(main())
