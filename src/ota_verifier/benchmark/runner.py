"""Deterministic corpus checks and reproducible extraction benchmark execution."""
import argparse
from dataclasses import dataclass, field
from pathlib import Path
import sys
from time import perf_counter
from typing import Any, Literal
from ..evaluation import CaseEvaluation, Profile, evaluate_case, fixture_client, summarize
from ..llm.client import ClientSettings, JsonClient, LLMClient, LLMError
from ..llm.evidence import canonical_json, content_hash
from ..llm.models import CallRecord, Purpose
from ..llm.pipeline import extract_and_verify
from ..models import FeasibleResult, Record
from ..persistence.models import VersionManifest
from ..persistence.recipes import PublicSettings
from ..persistence.versions import current_manifest
from ..planner import plan_campaign
from ..scheduling import validate_plan
from ..simulator import stress_test
from .corpus import Corpus, corpus_hash, load_corpus
from .metrics import ExtractionMetrics, extraction_metrics
from .oracle import exhaustive_optimum


class CoreResult(Record):
    """Measured core outputs and independent labeled/oracle checks."""
    case_id: str
    tags: tuple[str, ...]
    planning_status: str
    makespan_ms: int | None
    oracle_makespan_ms: int | None
    baseline_assessment: str
    fault_cases: int
    expected_fault_cases: int
    rollback_unavailable_cases: int
    findings: tuple[str, ...]
    checks_passed: bool


class CallTiming(Record):
    """Wall time of an attempted model role, including failed calls."""
    case_id: str
    purpose: Purpose
    elapsed_ms: float


@dataclass
class TimedClient:
    """Instrument an existing abstraction without adding any model purposes."""
    client: JsonClient
    case_id: str
    timings: list[CallTiming] = field(default_factory=list)

    def generate_json(self, *, purpose: Purpose, system_prompt: str, user_prompt: str,
                      schema: dict[str, Any], prompt_version: str) -> CallRecord:
        """Delegate exactly once and retain elapsed time even on failure."""
        started = perf_counter()
        try:
            return self.client.generate_json(purpose=purpose, system_prompt=system_prompt,
                user_prompt=user_prompt, schema=schema, prompt_version=prompt_version)
        finally:
            self.timings.append(CallTiming(case_id=self.case_id, purpose=purpose, elapsed_ms=(perf_counter() - started) * 1000))


class BenchmarkReport(Record):
    """Fixture checks are never represented as live-model accuracy measurements."""
    format_version: Literal['benchmark-report-v1'] = 'benchmark-report-v1'
    corpus_version: str
    corpus_sha256: str
    seed: int
    split: Literal['development', 'heldout', 'all']
    mode: Literal['fixtures', 'live', 'core']
    profile: str
    runtime: VersionManifest
    benchmark_code_sha256: str
    provider_configuration: dict[str, PublicSettings]
    core: tuple[CoreResult, ...]
    extraction: tuple[CaseEvaluation, ...]
    metrics: ExtractionMetrics
    call_timings: tuple[CallTiming, ...]
    semantic_digest: str
    checks_passed: bool
    limitations: tuple[str, ...]


def evaluate_core(corpus: Corpus) -> tuple[CoreResult, ...]:
    """Evaluate ground-truth campaigns with no clients or model calls."""
    rows = []
    for case in corpus.core:
        oracle = exhaustive_optimum(case.campaign, case.options)
        result = plan_campaign(case.campaign, case.options)
        span = result.plan.makespan_ms if isinstance(result, FeasibleResult) else None
        findings: list[str] = []
        fault_count = expected_count = unavailable = 0
        assessment = 'not_run'
        if isinstance(result, FeasibleResult):
            findings.extend(violation.code for violation in validate_plan(case.campaign, result.plan))
            report = stress_test(case.campaign, result.plan)
            assessment = report.assessment
            fault_count, expected_count = len(report.cases), report.expected_fault_cases
            unavailable = sum(fault.recovery is not None and fault.recovery.status == 'unavailable' for fault in report.cases)
            findings.extend(sorted({finding.violation.code for fault in report.cases for finding in fault.findings}))
            valid_plan = not validate_plan(case.campaign, result.plan) and result.plan.optimal
        else:
            valid_plan = result.status == 'infeasible'
        passed = (valid_plan and result.status == case.expected_planning
            and span == oracle == case.expected_makespan_ms and assessment == case.expected_baseline
            and bool(unavailable) == case.expected_rollback_unavailable and fault_count == expected_count)
        rows.append(CoreResult(case_id=case.id, tags=case.tags, planning_status=result.status,
            makespan_ms=span, oracle_makespan_ms=oracle, baseline_assessment=assessment,
            fault_cases=fault_count, expected_fault_cases=expected_count, rollback_unavailable_cases=unavailable,
            findings=tuple(findings), checks_passed=passed))
    return tuple(rows)


def run_benchmark(*, mode: Literal['fixtures', 'live', 'core'] = 'fixtures',
                  split: Literal['development', 'heldout', 'all'] = 'heldout', profile: Profile = 'reference',
                  clients: tuple[JsonClient, JsonClient] | None = None,
                  provider_configuration: dict[str, PublicSettings] | None = None) -> BenchmarkReport:
    """Run frozen core checks plus explicitly fixture or injected live extraction.

    This API never reads credentials or creates providers. The CLI creates live
    clients only following an explicit --mode live request. Gold is passed only
    to scoring functions, never to extract_and_verify.
    """
    if mode not in ('fixtures', 'live', 'core') or split not in ('development', 'heldout', 'all'):
        raise ValueError('Unknown benchmark mode or split')
    if mode == 'live' and (clients is None or profile != 'reference' or not provider_configuration
                           or set(provider_configuration) != {'extraction', 'verification'}):
        raise ValueError('Live measurement requires explicit clients, public configuration, and no fixture profile')
    if mode == 'core' and profile != 'reference':
        raise ValueError('Fixture profiles apply only to extraction benchmark modes')
    if mode != 'live' and (clients is not None or provider_configuration):
        raise ValueError('Offline evaluation cannot accept live clients or configuration')
    corpus = load_corpus()
    cases = corpus.development if split == 'development' else corpus.heldout if split == 'heldout' else (*corpus.development, *corpus.heldout)
    core = evaluate_core(corpus)
    pairs = []
    evaluations = []
    timings = []
    if mode != 'core':
        for case in cases:
            extraction = TimedClient(clients[0] if clients else fixture_client(case, profile), case.id)
            verifier = TimedClient(clients[1], case.id) if clients else extraction
            run = extract_and_verify(case.request, extraction, verifier)
            if mode == 'live':
                for call in run.calls:
                    if call.origin != 'live':
                        raise ValueError('Fixture responses cannot be reported as live-model measurements')
                    configured = (provider_configuration or {})[call.purpose]
                    if call.provider != configured.provider or call.model != configured.model:
                        raise ValueError('Recorded provider/model differs from declared measurement configuration')
            pairs.append((case, run))
            evaluations.append(evaluate_case(case, run))
            timings.extend(extraction.timings)
            if verifier is not extraction:
                timings.extend(verifier.timings)
    metrics = extraction_metrics(tuple(pairs))
    summary = summarize(tuple(evaluations), 'live' if mode == 'live' else 'fixtures', profile)
    passed = all(row.checks_passed for row in core) and not (
        summary.accepted_semantic_errors or summary.false_acceptances or summary.false_infeasibilities or summary.inconclusive_decisions
        or metrics.valid_case_blocking.numerator or metrics.faithfulness_false_acceptance.numerator
        or metrics.evidence_span_precision.numerator != metrics.evidence_span_precision.denominator
        or metrics.evidence_span_recall.numerator != metrics.evidence_span_recall.denominator)
    # Timings and runtime metadata are intentionally outside the reproducible
    # result digest. Prompts, raw responses, plans and counts remain inside it.
    semantic = {'corpus': corpus_hash(corpus), 'mode': mode, 'split': split, 'profile': profile,
                'core': [row.model_dump(mode='json') for row in core],
                'extraction': [row.model_dump(mode='json') for row in evaluations], 'metrics': metrics.model_dump(mode='json')}
    root = Path(__file__).parent
    code = {name: content_hash((root / name).read_text(encoding='utf-8-sig')) for name in ('corpus.py', 'oracle.py', 'metrics.py', 'runner.py', '../evaluation.py', '../data/generate.py')}
    return BenchmarkReport(corpus_version=corpus.version, corpus_sha256=corpus_hash(corpus), seed=corpus.seed,
        split=split, mode=mode, profile=profile if mode == 'fixtures' else 'live-model-responses' if mode == 'live' else 'not_applicable',
        runtime=current_manifest(), benchmark_code_sha256=content_hash(canonical_json(code)),
        provider_configuration=provider_configuration or {}, core=core, extraction=tuple(evaluations), metrics=metrics,
        call_timings=tuple(timings), semantic_digest=content_hash(canonical_json(semantic)), checks_passed=passed,
        limitations=('Simulation results apply only to the stated model and bounded corpus.',
            'Fixture outputs are scripted regression checks, not model accuracy measurements.',
            'Held-out wording is separate from development templates, not a claim about model training data.',
            'Oracle covers at most three one/two-minute monotonic 1-to-2 updates; compatibility shares compat.py.',
            'Latency is observed wall time; no performance threshold or cross-machine equivalence is asserted.',
            'Faithfulness rates condition on reviewed bad drafts; schema/transport failures are separate.'))


def main(argv: list[str] | None = None) -> int:
    """Emit a versioned benchmark report; never overwrite an existing report."""
    parser = argparse.ArgumentParser(description='Run the frozen OTA simulation benchmark')
    parser.add_argument('--mode', choices=('fixtures', 'live', 'core'), default='fixtures')
    parser.add_argument('--split', choices=('development', 'heldout', 'all'), default='heldout')
    parser.add_argument('--profile', choices=('reference', 'omission', 'reversed', 'false_approval', 'malformed'), default='reference')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--fail-on-findings', action='store_true')
    args = parser.parse_args(argv)
    if args.output and args.output.exists():
        parser.error('Output already exists; choose a new report path')
    if args.mode == 'core' and args.profile != 'reference':
        parser.error('Core-only mode has no fixture extraction profile')
    clients = None
    configuration: dict[str, PublicSettings] = {}
    if args.mode == 'live':
        if args.profile != 'reference':
            parser.error('Fixture perturbation profiles cannot be used with live providers')
        try:
            settings = (ClientSettings.from_env('extraction'), ClientSettings.from_env('verification'))
            clients = (LLMClient(settings[0]), LLMClient(settings[1]))
            configuration = {role: PublicSettings.capture(value) for role, value in zip(('extraction', 'verification'), settings, strict=True)}
        except (LLMError, ValueError) as error:
            parser.error(str(error))
    report = run_benchmark(mode=args.mode, split=args.split, profile=args.profile, clients=clients, provider_configuration=configuration)
    raw = report.model_dump_json(indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(raw)
    sys.stdout.write(raw)
    return 4 if args.fail_on_findings and not report.checks_passed else 0


if __name__ == '__main__':
    raise SystemExit(main())
