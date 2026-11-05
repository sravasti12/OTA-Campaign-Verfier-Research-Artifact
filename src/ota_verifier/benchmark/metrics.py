"""Extraction benchmark metrics with explicit, distinct denominators."""
from collections import Counter
from ..data.generate import SyntheticCase
from ..evaluation import ConstraintMetrics, compare_constraints, constraint_signature
from ..llm.client import LLMError
from ..llm.evidence import validate_json
from ..llm.models import ExtractionDraft, ExtractionRun
from ..models import Constraint, Record

KINDS = ('requires', 'mutex', 'precondition', 'order')


class Ratio(Record):
    """An undefined empty denominator is represented as null, never perfect accuracy."""
    numerator: int
    denominator: int
    value: float | None


def ratio(numerator: int, denominator: int) -> Ratio:
    """Retain counts with their derived rate."""
    return Ratio(numerator=numerator, denominator=denominator, value=numerator / denominator if denominator else None)


class ExtractionMetrics(Record):
    """Gold semantics, exact citations, and second-pass failures remain separate."""
    per_constraint_type: dict[str, ConstraintMetrics]
    evidence_span_accuracy: Ratio
    evidence_span_precision: Ratio
    evidence_span_recall: Ratio
    schema_rejection: Ratio
    missing_extraction_responses: int
    faithfulness_false_acceptance: Ratio
    unsupported_or_ambiguous_acceptance: Ratio
    valid_case_blocking: Ratio


def extraction_metrics(pairs: tuple[tuple[SyntheticCase, ExtractionRun], ...]) -> ExtractionMetrics:
    """Aggregate semantic multisets and exact gold spans, never using model IDs as labels.

    Span accuracy is correct exact spans / semantically matched constraints;
    precision/recall additionally penalize hallucinations, duplicates, and omissions.
    Faithfulness false acceptance is faithful judgments / reviewed bad drafts.
    Schema rejection counts strict draft JSON/schema failures only, not transport
    failures, citation validation, or second-pass disagreement.
    """
    expected: list[Constraint] = []
    actual: list[Constraint] = []
    semantic_matches = exact_spans = 0
    malformed = responses = missing = reviewed_bad = faithful_bad = 0
    abstention_cases = abstention_accepts = valid_cases = valid_blocked = 0
    for case, run in pairs:
        if case.request != run.request:
            raise ValueError('Metric input does not match the labeled request')
        extraction_call = next((call for call in run.calls if call.purpose == 'extraction'), None)
        if extraction_call is None:
            missing += 1
        else:
            responses += 1
            try:
                validate_json(ExtractionDraft, extraction_call.response_text)
            except (LLMError, ValueError):
                malformed += 1
        found = tuple(entry.constraint for entry in run.draft.constraints) if run.draft else ()
        bad = case.expected_blocked
        if case.expected_blocked:
            abstention_cases += 1
            abstention_accepts += run.status == 'ready'
        else:
            valid_cases += 1
            valid_blocked += run.status != 'ready'
            gold = case.truth_campaign.constraints
            expected.extend(gold)
            actual.extend(found)
            semantic = compare_constraints(gold, found)
            semantic_matches += semantic.true_positives
            bad = bool(semantic.false_positives or semantic.false_negatives)
            gold_spans = Counter((constraint_signature(entry.constraint), entry.evidence.document_id,
                entry.evidence.start_char, entry.evidence.end_char) for entry in case.reference_draft.constraints)
            found_spans = Counter((constraint_signature(entry.constraint), entry.evidence.document_id,
                entry.evidence.start_char, entry.evidence.end_char) for entry in run.draft.constraints) if run.draft else Counter()
            exact_spans += sum((gold_spans & found_spans).values())
        if run.verification is not None and bad:
            reviewed_bad += 1
            faithful_bad += run.verification.faithful
    per_type = {}
    for kind in KINDS:
        scores = [compare_constraints(
            tuple(rule for rule in case.truth_campaign.constraints if rule.type == kind),
            tuple(entry.constraint for entry in run.draft.constraints if entry.constraint.type == kind) if run.draft else ())
            for case, run in pairs if not case.expected_blocked]
        true = sum(score.true_positives for score in scores)
        fp = sum(score.false_positives for score in scores)
        fn = sum(score.false_negatives for score in scores)
        per_type[kind] = ConstraintMetrics(true_positives=true, false_positives=fp, false_negatives=fn,
            precision=true / (true + fp) if true + fp else None,
            recall=true / (true + fn) if true + fn else None)
    return ExtractionMetrics(per_constraint_type=per_type,
        evidence_span_accuracy=ratio(exact_spans, semantic_matches), evidence_span_precision=ratio(exact_spans, len(actual)),
        evidence_span_recall=ratio(exact_spans, len(expected)), schema_rejection=ratio(malformed, responses),
        missing_extraction_responses=missing, faithfulness_false_acceptance=ratio(faithful_bad, reviewed_bad),
        unsupported_or_ambiguous_acceptance=ratio(abstention_accepts, abstention_cases),
        valid_case_blocking=ratio(valid_blocked, valid_cases))
