"""Deterministic evaluation of extraction semantics and downstream decisions."""
import argparse
from collections import Counter
from pathlib import Path
import sys
from typing import Literal
from .data.generate import SyntheticCase, generate_cases
from .models import Campaign, Constraint, FeasibleResult, Mutex, Order, Plan, PlanningOptions, PlanStep, Record, Requires, Violation
from .planner import plan_campaign
from .scheduling import constraint_ecus, validate_plan
from .simulator import stress_test
from .simulation_models import SimulationResult
from .llm.client import ClientSettings, FixtureClient, JsonClient, LLMClient, LLMError
from .llm.evidence import canonical_json
from .llm.models import ExtractedConstraint, ExtractionDraft, ExtractionRun, FaithfulnessVerdict, VerificationIssue
from .llm.pipeline import extract_and_verify, verified_campaign
from .llm.verifier import validate_draft
from .versions import parse_spec

Profile = Literal['reference', 'omission', 'reversed', 'false_approval', 'malformed']


class ConstraintMetrics(Record):
    """Multiset semantic comparison, excluding IDs and source wording."""
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float | None
    recall: float | None


class CaseEvaluation(Record):
    """Separate extraction quality, gate decisions, and ground-truth consequences."""
    case_id: str
    truth_campaign: Campaign
    run: ExtractionRun
    expected_blocked: bool
    metrics: ConstraintMetrics | None
    deterministic_checks_passed: bool
    accepted_semantic_error: bool
    planning_status: Literal['not_run', 'feasible', 'infeasible', 'unknown']
    truth_planning_status: Literal['not_run', 'feasible', 'infeasible', 'unknown']
    truth_plan_violations: tuple[Violation, ...]
    false_acceptance: bool
    false_infeasibility: bool
    downstream_inconclusive: bool
    fault_outcome_differences: int | None
    missed_fault_violations: int | None


class EvaluationReport(Record):
    """Fixture diagnostics are explicitly separate from actual model measurements."""
    dataset_version: str = 'synthetic-v1'
    mode: Literal['fixtures', 'live']
    profile: str
    cases: tuple[CaseEvaluation, ...]
    micro_metrics: ConstraintMetrics
    semantically_evaluable_cases: int
    ready_count: int
    blocked_count: int
    accepted_semantic_errors: int
    false_acceptances: int
    false_acceptance_denominator: int
    false_acceptance_rate: float | None
    false_infeasibilities: int
    inconclusive_decisions: int


def constraint_signature(constraint: Constraint) -> str:
    """Canonicalize domain meaning, including numeric version normalization."""
    if isinstance(constraint, Requires):
        payload = ('requires', constraint.ecu, parse_spec(constraint.version_spec), constraint.needs, parse_spec(constraint.needs_version_spec))
    elif isinstance(constraint, Mutex):
        payload = ('mutex', tuple(sorted(constraint.ecus)))
    elif isinstance(constraint, Order):
        payload = ('order', constraint.before, constraint.after)
    else:
        payload = ('precondition', constraint.ecu, constraint.ignition, constraint.minimum_battery_percent)
    return canonical_json(payload)


def compare_constraints(expected: tuple[Constraint, ...], actual: tuple[Constraint, ...]) -> ConstraintMetrics:
    """Compute exact normalized semantic precision/recall, penalizing duplicates."""
    gold = Counter(constraint_signature(constraint) for constraint in expected)
    found = Counter(constraint_signature(constraint) for constraint in actual)
    true = sum((gold & found).values())
    false_positive, false_negative = sum((found - gold).values()), sum((gold - found).values())
    return ConstraintMetrics(true_positives=true, false_positives=false_positive, false_negatives=false_negative,
        precision=true / (true + false_positive) if true + false_positive else None,
        recall=true / (true + false_negative) if true + false_negative else None)


def fixture_client(case: SyntheticCase, profile: Profile = 'reference') -> FixtureClient:
    """Create labeled canned responses for exercising the harness, not model scoring."""
    draft, verdict = case.reference_draft, case.reference_verdict
    dependency = next((entry for entry in draft.constraints if isinstance(entry.constraint, Requires)), None)
    if profile == 'malformed':
        return FixtureClient(('```json\n{}\n```',))
    if dependency is not None and profile in ('omission', 'reversed', 'false_approval'):
        changed = tuple(entry for entry in draft.constraints if entry is not dependency)
        if profile == 'reversed':
            rule = dependency.constraint
            reversed_rule = Requires(id=rule.id, source_document_id=rule.source_document_id,
                source_text=rule.source_text, ecu=rule.needs, version_spec=rule.needs_version_spec,
                needs=rule.ecu, needs_version_spec=rule.version_spec)
            changed += (ExtractedConstraint(constraint=reversed_rule, evidence=dependency.evidence),)
        draft = ExtractionDraft(constraints=changed, issues=draft.issues)
        review_issues = () if profile == 'false_approval' else (VerificationIssue(
            kind='incorrect_constraint' if profile == 'reversed' else 'missing_requirement',
            constraint_id=dependency.constraint.id if profile == 'reversed' else None,
            evidence=dependency.evidence, source_text=dependency.constraint.source_text,
            message='Dependency direction was reversed' if profile == 'reversed' else 'Explicit dependency was omitted'),)
        verdict = FaithfulnessVerdict(faithful=not review_issues,
            reviewed_constraint_ids=tuple(entry.constraint.id for entry in changed),
            reviewed_document_ids=tuple(document.id for document in case.request.documents), issues=review_issues)
    return FixtureClient((draft.model_dump_json(), verdict.model_dump_json()))


def _truth_view(plan: Plan, truth: Campaign) -> Plan:
    # Rebind only source-ID metadata so differing extraction IDs do not become
    # false safety failures. Timing, slots, versions, states and options are intact.
    steps = tuple(PlanStep(**step.model_dump(exclude={'constraint_ids'}),
        constraint_ids=tuple(c.id for c in truth.constraints if step.ecu_id in constraint_ecus(c))) for step in plan.steps)
    return Plan(campaign_id=plan.campaign_id, steps=steps, states=plan.states,
                makespan_ms=plan.makespan_ms, optimal=plan.optimal, options=plan.options)


def _fault_signature(result: SimulationResult) -> tuple[object, ...]:
    return (result.assessment, result.recovery.status if result.recovery else None,
            frozenset((f.invariant, f.violation.code, f.violation.ecu_ids,
                       f.violation.actual_version, f.violation.expected_version_spec) for f in result.findings))


def evaluate_case(case: SyntheticCase, run: ExtractionRun, *, run_stress: bool = True,
                  options: PlanningOptions | None = None) -> CaseEvaluation:
    """Judge an extraction against hidden gold, including falsely accepted plans.

    Ground truth never enters extraction/verification prompts. A candidate plan
    is checked against gold at every transition, not only its final state.
    """
    if run.request != case.request:
        raise ValueError('Evaluation run does not belong to this benchmark request')
    actual = tuple(entry.constraint for entry in run.draft.constraints) if run.draft else ()
    # Ambiguous/unsupported documents lack a uniquely extractable complete gold
    # constraint set. Evaluate their required abstention, not semantic recall.
    metrics = None if case.expected_blocked else compare_constraints(case.truth_campaign.constraints, actual)
    checks = run.draft is not None and not validate_draft(run.request, run.draft)
    ready = run.status == 'ready'
    planning_status = 'not_run'
    truth_status = 'not_run'
    findings: tuple[Violation, ...] = ()
    unsafe = ready and case.expected_blocked
    false_infeasibility = False
    inconclusive = False
    differences: int | None = None
    missed: int | None = None
    if ready:
        candidate = verified_campaign(run)
        result = plan_campaign(candidate, options)
        planning_status = result.status
        if not case.expected_blocked:
            truth_result = plan_campaign(case.truth_campaign, options)
            truth_status = truth_result.status
            inconclusive = result.status == 'unknown' or truth_result.status == 'unknown'
            false_infeasibility = result.status == 'infeasible' and truth_result.status == 'feasible'
            if isinstance(result, FeasibleResult):
                truth_plan = _truth_view(result.plan, case.truth_campaign)
                findings = validate_plan(case.truth_campaign, truth_plan)
                unsafe = bool(findings)
                if run_stress and not findings:
                    proposed = stress_test(candidate, result.plan)
                    gold = stress_test(case.truth_campaign, truth_plan)
                    differences = sum(_fault_signature(a) != _fault_signature(b)
                                      for a, b in zip(proposed.cases, gold.cases, strict=True))
                    missed = sum(a.assessment == 'passed' and b.assessment == 'violations'
                                 for a, b in zip(proposed.cases, gold.cases, strict=True))
                    unsafe |= missed > 0
                    inconclusive |= any(a.assessment == 'inconclusive' or b.assessment == 'inconclusive'
                                        for a, b in zip(proposed.cases, gold.cases, strict=True))
    return CaseEvaluation(case_id=case.id, truth_campaign=case.truth_campaign, run=run, expected_blocked=case.expected_blocked,
        metrics=metrics, deterministic_checks_passed=checks,
        accepted_semantic_error=ready and metrics is not None and bool(metrics.false_positives or metrics.false_negatives),
        planning_status=planning_status, truth_planning_status=truth_status, truth_plan_violations=findings,
        false_acceptance=unsafe, false_infeasibility=false_infeasibility,
        downstream_inconclusive=inconclusive, fault_outcome_differences=differences, missed_fault_violations=missed)


def summarize(cases: tuple[CaseEvaluation, ...], mode: Literal['fixtures', 'live'], profile: str) -> EvaluationReport:
    """Aggregate with explicit denominators and undefined empty precision/recall."""
    scored = tuple(case.metrics for case in cases if case.metrics is not None)
    true = sum(metric.true_positives for metric in scored)
    fp = sum(metric.false_positives for metric in scored)
    fn = sum(metric.false_negatives for metric in scored)
    ready = sum(case.run.status == 'ready' for case in cases)
    false = sum(case.false_acceptance for case in cases)
    return EvaluationReport(mode=mode, profile=profile, cases=cases, semantically_evaluable_cases=len(scored),
        micro_metrics=ConstraintMetrics(true_positives=true, false_positives=fp, false_negatives=fn,
            precision=true / (true + fp) if true + fp else None, recall=true / (true + fn) if true + fn else None),
        ready_count=ready, blocked_count=len(cases) - ready,
        accepted_semantic_errors=sum(case.accepted_semantic_error for case in cases),
        false_acceptances=false, false_acceptance_denominator=ready,
        false_acceptance_rate=false / ready if ready else None,
        false_infeasibilities=sum(case.false_infeasibility for case in cases),
        inconclusive_decisions=sum(case.downstream_inconclusive for case in cases))


def main(argv: list[str] | None = None) -> int:
    """Run explicit fixture or live evaluation and emit full reproducible JSON."""
    parser = argparse.ArgumentParser(description='Evaluate document extraction against synthetic ground truth')
    parser.add_argument('--mode', choices=('fixtures', 'live'), default='fixtures')
    parser.add_argument('--profile', choices=('reference', 'omission', 'reversed', 'false_approval', 'malformed'), default='reference')
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--count', type=int, default=6)
    parser.add_argument('--no-stress', action='store_true')
    parser.add_argument('--fail-on-false-acceptance', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    if args.count <= 0:
        parser.error('--count must be positive')
    if args.mode == 'live' and args.profile != 'reference':
        parser.error('Scripted perturbation profiles apply only to fixture mode')
    extraction_client: JsonClient | None = None
    review_client: JsonClient | None = None
    if args.mode == 'live':
        try:
            extraction_client = LLMClient(ClientSettings.from_env())
            review_client = LLMClient(ClientSettings.from_env('verification'))
        except LLMError as error:
            parser.error(str(error))
    results: list[CaseEvaluation] = []
    for case in generate_cases(args.seed, args.count):
        client = extraction_client or fixture_client(case, args.profile)
        run = extract_and_verify(case.request, client, review_client)
        results.append(evaluate_case(case, run, run_stress=not args.no_stress))
    report = summarize(tuple(results), args.mode, args.profile if args.mode == 'fixtures' else 'live-model-responses')
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(report.model_dump_json(indent=2) + '\n')
    sys.stdout.write(report.model_dump_json(indent=2) + '\n')
    return 4 if args.fail_on_false_acceptance and report.false_acceptances else 0


if __name__ == '__main__':
    raise SystemExit(main())
