"""Grounded explanation rejects invented references and preserves deterministic truth."""
import json
from typing import Any
import pytest
from ota_verifier.graph import WorkflowService, WorkflowClients
from ota_verifier.llm.client import FixtureClient, LLMError
from ota_verifier.llm.explainer import FixtureExplanationClient, explain_results
from ota_verifier.llm.explanation_models import ExplanationResult
from ota_verifier.workflow_examples import example_input, fixture_dependencies
from ota_verifier.workflow_models import WorkflowInput


def _snapshot() -> Any:
    request, case = example_input()
    return WorkflowService().start(WorkflowInput(request=request), fixture_dependencies(case)).snapshot


def test_fixture_explanation_has_grounded_outcomes_and_source_links() -> None:
    snapshot = _snapshot()
    result = snapshot.explanation
    assert result.status == 'fixture'
    assert result.call.purpose == 'explanation'
    assert result.draft.analysis_status == 'simulation_violations'
    catalog = {fact.id: fact for fact in snapshot.facts}
    assert all(catalog[statement.evidence_id].outcome == statement.outcome for statement in result.draft.statements)
    assert any(fact.kind == 'constraint' and fact.source_text for fact in snapshot.facts)
    assert any(fact.kind == 'finding' and fact.trace_index is not None for fact in snapshot.facts)
    assert ExplanationResult.model_validate_json(result.model_dump_json()) == result


@pytest.mark.parametrize('mutation', ['unknown_id', 'changed_status', 'changed_outcome', 'missing_summary', 'unsupported_claim'])
def test_invalid_explanation_falls_back(mutation: str) -> None:
    snapshot = _snapshot()
    raw = json.loads(snapshot.explanation.draft.model_dump_json())
    if mutation == 'unknown_id':
        raw['statements'][0]['evidence_id'] = 'invented'
    elif mutation == 'changed_status':
        raw['analysis_status'] = 'simulation_passed'
    elif mutation == 'changed_outcome':
        raw['statements'][0]['outcome'] = 'unknown'
    elif mutation == 'missing_summary':
        raw['statements'] = raw['statements'][1:]
    else:
        raw['statements'][0]['text'] = 'This is safe to deploy.'
    result = explain_results(snapshot.artifacts.status, snapshot.facts, FixtureClient((json.dumps(raw),)))
    assert result.status == 'fallback'
    assert result.draft is None
    assert result.call is not None
    assert result.issues
    assert result.deterministic_summary == snapshot.explanation.deterministic_summary


@pytest.mark.parametrize('client', [None, FixtureClient(('not JSON',))])
def test_absent_or_malformed_explanation_never_loses_results(client: Any) -> None:
    snapshot = _snapshot()
    result = explain_results(snapshot.artifacts.status, snapshot.facts, client)
    assert result.status == 'fallback'
    assert result.deterministic_summary
    assert any('violations' in text for text in result.deterministic_summary)


def test_provider_failure_keeps_deterministic_evidence() -> None:
    class Unavailable:
        def generate_json(self, **kwargs: Any) -> Any:
            raise LLMError('Provider unavailable')
    request, case = example_input()
    clients = fixture_dependencies(case)
    bundle = WorkflowService().start(WorkflowInput(request=request), WorkflowClients(clients.extractor, explainer=Unavailable()))
    assert bundle.snapshot.artifacts.status == 'simulation_violations'
    assert bundle.snapshot.artifacts.simulation is not None
    assert bundle.snapshot.explanation.status == 'fallback'
    assert bundle.review_state == 'awaiting_review'
