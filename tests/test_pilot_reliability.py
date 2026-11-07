"""Offline saved-response replay and bounded reliability guards; no live accuracy claims."""
from pathlib import Path
import json
import pytest
from ota_verifier.benchmark.corpus import load_corpus
from ota_verifier.llm.client import FixtureClient
from ota_verifier.llm.models import ExtractionRun
from ota_verifier.llm.pipeline import extract_and_verify, verified_campaign
from ota_verifier.llm.source_support import explicit_flash_order
from ota_verifier.llm.verifier import validate_draft, validate_verdict, verification_prompt
from ota_verifier.models import InfeasibleResult
from ota_verifier.planner import plan_campaign

BASELINE = Path(__file__).resolve().parents[1] / 'eval/live_extraction/synthetic-pilot-v1'


def saved(case_id: str) -> ExtractionRun:
    """Read a frozen historical run without using its live transport or settings."""
    return ExtractionRun.model_validate_json(json.dumps(json.loads(
        (BASELINE / (case_id + '.json')).read_text(encoding='utf-8'))['run']))


def test_saved_false_rejection_stays_blocked_with_precise_reference_reason() -> None:
    """A real but inappropriate ID must not be silently repaired or false rejection ignored."""
    original = saved('clear-42')
    replay = extract_and_verify(original.request, FixtureClient(tuple(call.response_text for call in original.calls)))
    assert replay.status == 'blocked'
    assert replay.verification == original.verification
    assert 'c1' in {entry.constraint.id for entry in replay.draft.constraints}
    errors = [issue for issue in replay.issues if issue.code == 'verification_reference']
    assert len(errors) == 1 and 'null constraint ID' in errors[0].message
    assert any(issue.code == 'missing_requirement' for issue in replay.issues)
    assert all(call.origin == 'fixture' for call in replay.calls)


@pytest.mark.parametrize('identifier', ['nonexistent', None])
def test_constraint_specific_verifier_findings_require_known_ids(identifier: str | None) -> None:
    """Unknown and missing IDs remain blockers independent of model judgments."""
    run = saved('clear-42')
    issue = run.verification.issues[0].model_copy(update={'kind': 'incorrect_constraint', 'constraint_id': identifier})
    verdict = run.verification.model_copy(update={'issues': (issue,)})
    assert 'verification_reference' in {issue.code for issue in validate_verdict(run.request, run.draft, verdict)}


def test_saved_swapped_order_citations_block_before_verifier() -> None:
    """Literal valid quotes cannot mask the observed reverse rule-to-sentence mapping."""
    original = saved('order_conflict-44')
    replay = extract_and_verify(original.request, FixtureClient((original.calls[0].response_text,)))
    assert replay.status == 'blocked' and replay.draft == original.draft
    assert len([issue for issue in replay.issues if issue.code == 'source_support']) == 2
    assert replay.verification is None and len(replay.calls) == 1
    assert 'contradictory_documents' in {issue.code for issue in replay.issues}


def test_correctly_grounded_opposite_orders_keep_conflict_evidence_and_reach_z3() -> None:
    """A separate constructed control tests routing, without changing saved predictions."""
    case = next(case for case in load_corpus().development if case.id == 'order_conflict-44')
    original = saved(case.id)
    # Deliberately use frozen gold as an explicitly offline control, not a repaired live result.
    draft = case.reference_draft.model_copy(update={'issues': original.draft.issues})
    assert validate_draft(case.request, draft) == ()
    assert 'solver_deferred_order_conflicts' in verification_prompt(case.request, draft)
    run = extract_and_verify(case.request, FixtureClient((draft.model_dump_json(), case.reference_verdict.model_dump_json())))
    assert run.status == 'ready' and run.draft.issues == original.draft.issues
    assert len(verified_campaign(run).constraints) == 2
    assert isinstance(plan_campaign(verified_campaign(run)), InfeasibleResult)


def test_unexplained_conflict_and_invalid_conflict_evidence_remain_blockers() -> None:
    """Do not whitelist arbitrary contradictions or overlook a fabricated conflict quote."""
    case = next(case for case in load_corpus().development if case.id == 'order_conflict-44')
    original = saved(case.id)
    issue = original.draft.issues[0]
    one_rule = case.reference_draft.model_copy(update={'constraints': case.reference_draft.constraints[:1], 'issues': (issue,)})
    assert 'contradictory_documents' in {finding.code for finding in validate_draft(case.request, one_rule)}
    invalid = issue.model_copy(update={'source_text': 'invented'})
    draft = case.reference_draft.model_copy(update={'issues': (invalid,)})
    assert 'source_error' in {finding.code for finding in validate_draft(case.request, draft)}


def test_saved_unsupported_requirement_still_has_no_rules_and_blocks() -> None:
    """Unmodeled Wi-Fi requirements must not turn into formal constraints."""
    original = saved('unsupported-47')
    replay = extract_and_verify(original.request, FixtureClient((original.calls[0].response_text,)))
    assert replay.status == 'blocked' and replay.draft.constraints == ()
    assert 'unsupported_requirement' in {issue.code for issue in replay.issues}
    assert len(replay.calls) == 1


def test_unsupported_issue_cannot_be_hidden_by_a_deferred_order_conflict() -> None:
    """Deferring a fully witnessed order conflict never dismisses unsupported demands."""
    case = next(case for case in load_corpus().development if case.id == 'order_conflict-44')
    conflict = saved(case.id).draft.issues[0]
    unsupported = conflict.model_copy(update={'kind': 'unsupported_requirement'})
    draft = case.reference_draft.model_copy(update={'issues': (conflict, unsupported)})
    assert [issue.code for issue in validate_draft(case.request, draft)] == ['unsupported_requirement']


def test_order_sentence_cannot_be_recast_as_version_dependency() -> None:
    """The bounded guard checks the rule type as well as direction."""
    original = saved('order_conflict-44')
    raw = json.loads(original.draft.model_dump_json())
    raw['constraints'][0]['constraint'] = {
        'type': 'requires', 'id': 'invented-dependency', 'ecu': 'gateway', 'version_spec': '>=2',
        'needs': 'brake', 'needs_version_spec': '>=2', 'source_document_id': 'release-44',
        'source_text': raw['constraints'][0]['constraint']['source_text']}
    from ota_verifier.llm.models import ExtractionDraft
    draft = ExtractionDraft.model_validate_json(json.dumps(raw))
    assert 'source_support' in {issue.code for issue in validate_draft(original.request, draft)}


@pytest.mark.parametrize('text', [
    'If parked, gateway must finish flashing and activate before brake starts flashing.',
    'gateway may finish flashing and activate before brake starts flashing.',
    'gateway must NOT finish flashing and activate before brake starts flashing.',
    'Update receiver before transmitter.',
])
def test_bounded_order_recognizer_never_guesses_unknown_or_conditional_wording(text: str) -> None:
    """The guard handles its documented grammar only; it is not general entailment."""
    assert explicit_flash_order(text) is None
