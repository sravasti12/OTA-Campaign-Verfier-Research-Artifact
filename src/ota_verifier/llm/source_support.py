"""Bounded source checks; not a general natural-language entailment engine."""
import re
from .models import ExtractedConstraint, ExtractionDraft, ExtractionIssue


def explicit_flash_order(text: str) -> tuple[str, str] | None:
    """Recognize only bounded unqualified ordering sentences.

    Unknown wording returns None and remains subject to LLM faithfulness review.
    Never infer a new rule, repair a direction, or interpret a conditional clause.
    """
    match = re.fullmatch(
        r'([A-Za-z0-9_-]+) must finish flashing and activate before '
        r'([A-Za-z0-9_-]+) starts flashing\.', text)
    if match:
        return match[1], match[2]
    match = re.fullmatch(
        r'(?:Note: )?You must update the ([A-Za-z0-9_-]+) firmware before '
        r'updating the ([A-Za-z0-9_-]+) firmware\.', text)
    return (match[1], match[2]) if match else None


def order_support_error(entry: ExtractedConstraint) -> str | None:
    """Reject a rule contradicting the explicit ordering grammar when recognized."""
    direction = explicit_flash_order(entry.constraint.source_text)
    if direction is None:
        return None
    rule = entry.constraint
    if rule.type != 'order' or (rule.before, rule.after) != direction:
        return 'Constraint disagrees with the explicit source update order'
    return None


def deferred_order_conflicts(draft: ExtractionDraft) -> tuple[ExtractionIssue, ...]:
    """Identify redundant conflict findings fully witnessed by opposite order rules.

    Exact citation validation still runs separately. Only this bounded grammar
    qualifies; arbitrary contradiction findings remain fail-closed blockers.
    Findings remain in the draft, with an explicit audit annotation in review.
    """
    supported = [entry for entry in draft.constraints
                 if explicit_flash_order(entry.constraint.source_text) is not None
                 and order_support_error(entry) is None]
    deferred = []
    for issue in draft.issues:
        if issue.kind != 'contradictory_documents':
            continue
        for entry in supported:
            if entry.evidence != issue.evidence or entry.constraint.source_text != issue.source_text:
                continue
            rule = entry.constraint
            if any((other.constraint.before, other.constraint.after) == (rule.after, rule.before)
                   and other.evidence != entry.evidence for other in supported):
                deferred.append(issue)
                break
    return tuple(deferred)
