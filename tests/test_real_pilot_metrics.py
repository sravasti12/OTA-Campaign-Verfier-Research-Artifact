"""Offline scoring contracts; these fixtures never establish model accuracy."""
import importlib.util
import json
from pathlib import Path
import pytest
from ota_verifier.llm.client import FixtureClient
from ota_verifier.llm.models import DocumentRequest, ExtractionDraft, FaithfulnessVerdict
from ota_verifier.llm.pipeline import extract_and_verify

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('real_pilot_metrics', ROOT / 'eval/live_extraction/real_pilot.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize('index', range(5))
def test_frozen_gold_fixture_scores_meaning_evidence_issues_and_gate_separately(index: int) -> None:
    """Supported, unsupported and descriptive controls retain distinct expected behavior."""
    row = json.loads((ROOT / 'eval/live_extraction/real-review-v3/candidates.json').read_text(encoding='utf-8'))['cases'][index]
    request = DocumentRequest.model_validate_json(json.dumps(row['request_scaffold']))
    draft = ExtractionDraft.model_validate_json(json.dumps(row['proposed_draft']))
    verdict = FaithfulnessVerdict(faithful=True, reviewed_constraint_ids=tuple(e.constraint.id for e in draft.constraints),
                                  reviewed_document_ids=tuple(d.id for d in request.documents), issues=())
    responses = (draft.model_dump_json(),) if draft.issues else (draft.model_dump_json(), verdict.model_dump_json())
    run = extract_and_verify(request, FixtureClient(responses))
    result = module.score_case(row, run)
    assert result['complete_expected_outcome'] and result['exact_draft'] and result['gate_correct']
    assert result['correct_bindings'] == len(draft.constraints)
    assert result['verifier_called'] == (not bool(draft.issues))


def test_empty_descriptive_draft_is_not_correct_unsupported_abstention() -> None:
    """A blocked versus ready expectation cannot be satisfied by merely emitting zero rules."""
    row = json.loads((ROOT / 'eval/live_extraction/real-review-v3/candidates.json').read_text(encoding='utf-8'))['cases'][2]
    request = DocumentRequest.model_validate_json(json.dumps(row['request_scaffold']))
    verdict = FaithfulnessVerdict(faithful=True, reviewed_constraint_ids=(), reviewed_document_ids=(row['id'],), issues=())
    run = extract_and_verify(request, FixtureClient(('{"constraints":[],"issues":[]}', verdict.model_dump_json())))
    result = module.score_case(row, run)
    assert result['semantic_exact'] and not result['exact_issue_set']
    assert not result['gate_correct'] and not result['verifier_correct']


def test_saved_provider_failure_is_not_scored_as_successful_unsupported_abstention() -> None:
    """Recover actual saved measurements without allowing fail-closed HTTP errors to become passes."""
    recovery_spec = importlib.util.spec_from_file_location('analyze_real_pilot', ROOT / 'eval/live_extraction/analyze_real_pilot.py')
    recovery = importlib.util.module_from_spec(recovery_spec)
    recovery_spec.loader.exec_module(recovery)
    result = recovery.analyze()
    assert result['new_api_requests'] == 0
    assert result['mechanical_gate_agreement_on_attempted_cases']['numerator'] == 1
    assert result['gate_agreement_on_usable_extractions']['numerator'] == 0
    assert result['correct_unsupported_abstention_on_usable_expected_unsupported_cases']['value'] is None
    assert result['failed_request_tokens'] is None
