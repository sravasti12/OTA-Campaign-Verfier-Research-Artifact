"""Checkpoint routing, isolated runs, stale decisions, and idempotent human review."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import json
from typing import Any
import pytest
from ota_verifier.graph import WorkflowClients, WorkflowService
from ota_verifier.llm.client import JsonClient
from ota_verifier.models import PlanningOptions, UnknownResult
from ota_verifier.workflow_examples import example_input, fixture_dependencies
from ota_verifier.workflow_models import ReviewBundle, ReviewSubmission, WorkflowInput, approval_eligible


@dataclass
class CountingClient:
    inner: JsonClient
    purposes: list[str]

    def generate_json(self, **kwargs: Any) -> Any:
        self.purposes.append(kwargs['purpose'])
        return self.inner.generate_json(**kwargs)


def _start(name: str = 'clear', service: WorkflowService | None = None, run_id: str | None = None) -> tuple[WorkflowService, ReviewBundle, list[str]]:
    request, case = example_input(name)
    dependencies = fixture_dependencies(case)
    calls: list[str] = []
    clients = WorkflowClients(CountingClient(dependencies.extractor, calls),
                              explainer=CountingClient(dependencies.explainer, calls))
    service = service or WorkflowService()
    bundle = service.start(WorkflowInput(request=request), clients, run_id)
    return service, bundle, calls


def _decision(bundle: ReviewBundle, action: str = 'review_with_findings', key: str = 'review-1') -> ReviewSubmission:
    return ReviewSubmission(idempotency_key=key, run_id=bundle.run_id, revision=bundle.revision,
        snapshot_hash=bundle.snapshot_hash, action=action, reviewer='simulation-reviewer', reason='Reviewed the recorded evidence')


@pytest.mark.parametrize(('name', 'expected', 'nodes'), [
    ('clear', 'simulation_violations', ('extract', 'plan', 'simulate', 'explain', 'prepare_review')),
    ('ambiguous', 'extraction_blocked', ('extract', 'explain', 'prepare_review')),
    ('unsupported', 'extraction_blocked', ('extract', 'explain', 'prepare_review')),
    ('order_conflict', 'planning_infeasible', ('extract', 'plan', 'explain', 'prepare_review')),
    ('intermediate_trap', 'planning_infeasible', ('extract', 'plan', 'explain', 'prepare_review')),
    ('no_updates', 'simulation_passed', ('extract', 'plan', 'simulate', 'explain', 'prepare_review')),
])
def test_conditional_workflow_pauses_before_review(name: str, expected: str, nodes: tuple[str, ...]) -> None:
    service, bundle, calls = _start(name)
    assert bundle.snapshot.artifacts.status == expected
    assert bundle.review_state == 'awaiting_review'
    assert bundle.current_decision is None
    assert bundle.completed_nodes == nodes
    config = service._config(bundle.run_id)
    assert service.graph.get_state(config).next == ('human_review',)
    assert ReviewBundle.model_validate_json(bundle.model_dump_json()) == bundle


def test_pause_resume_and_duplicate_review_do_not_repeat_calls() -> None:
    service, bundle, calls = _start()
    expected_calls = ['extraction', 'verification', 'explanation']
    assert calls == expected_calls
    assert service.resume(bundle.run_id) == bundle
    submission = _decision(bundle)
    result = service.review(submission)
    assert result.review_state == 'reviewed_with_findings'
    assert service.review(submission) == result
    assert service.resume(bundle.run_id) == result
    assert len(result.decisions) == 1
    assert result.completed_nodes.count('human_review') == 1
    assert calls == expected_calls
    assert result.snapshot.artifacts.simulation.assessment == 'violations'


def test_violations_cannot_be_approved_and_checkpoint_cannot_be_resumed_blindly() -> None:
    service, bundle, calls = _start()
    with pytest.raises(ValueError, match='cannot be approved'):
        service.review(_decision(bundle, 'approve'))
    with pytest.raises(ValueError, match='explicit human decision'):
        service.graph.invoke(None, service._config(bundle.run_id))
    assert service.get(bundle.run_id).current_decision is None
    assert calls == ['extraction', 'verification', 'explanation']


def test_passing_no_update_proposal_can_be_approved() -> None:
    service, bundle, calls = _start('no_updates')
    assert approval_eligible(bundle.snapshot)
    assert bundle.snapshot.artifacts.simulation.expected_fault_cases == 0
    result = service.review(_decision(bundle, 'approve'))
    assert result.review_state == 'approved'
    assert result.current_decision.submission.snapshot_hash == bundle.snapshot_hash


def test_reject_and_idempotency_conflict() -> None:
    service, bundle, calls = _start()
    result = service.review(_decision(bundle, 'reject'))
    assert result.review_state == 'rejected'
    with pytest.raises(ValueError, match='Idempotency key'):
        service.review(_decision(bundle, 'review_with_findings'))
    with pytest.raises(ValueError, match='already has a final decision'):
        service.review(_decision(bundle, 'reject', 'other-key'))


def test_new_revision_invalidates_old_approval_and_preserves_history() -> None:
    service, bundle, calls = _start('no_updates')
    reviewed = service.review(_decision(bundle, 'approve'))
    request, case = example_input('clear')
    revised = service.revise(bundle.run_id, WorkflowInput(request=request), fixture_dependencies(case))
    assert revised.revision == 2
    assert revised.snapshot_hash != reviewed.snapshot_hash
    assert revised.review_state == 'invalidated'
    assert revised.current_decision is None
    assert len(revised.decisions) == 1
    assert revised.decisions[0] == reviewed.current_decision
    with pytest.raises(ValueError, match='stale'):
        service.review(_decision(bundle, 'approve', key='new-stale-key'))
    decision = service.review(_decision(revised, key='new-review'))
    assert decision.review_state == 'reviewed_with_findings'
    assert len(decision.decisions) == 2


def test_cross_run_decision_and_duplicate_run_ids_are_rejected() -> None:
    service, first, calls = _start('no_updates', run_id='first')
    _, second, _ = _start('no_updates', service, 'second')
    assert first.snapshot_hash != second.snapshot_hash
    wrong = ReviewSubmission(**_decision(first, 'approve').model_dump(exclude={'run_id'}), run_id=second.run_id)
    with pytest.raises(ValueError, match='stale'):
        service.review(wrong)
    request, case = example_input()
    with pytest.raises(ValueError, match='already exists'):
        service.start(WorkflowInput(request=request), fixture_dependencies(case), 'first')
    assert service.get('first').current_decision is None
    assert service.get('second').current_decision is None


def test_concurrent_duplicate_submissions_record_one_decision() -> None:
    service, bundle, calls = _start()
    submission = _decision(bundle)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(service.review, (submission, submission)))
    assert results[0] == results[1]
    assert len(results[0].decisions) == 1
    assert calls == ['extraction', 'verification', 'explanation']


def test_solver_unknown_never_reaches_simulation_or_approval(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('ota_verifier.graph.plan_campaign', lambda *args, **kwargs: UnknownResult(reason='Simulated solver timeout'))
    service, bundle, calls = _start()
    assert bundle.snapshot.artifacts.status == 'planning_unknown'
    assert bundle.snapshot.artifacts.simulation is None
    assert 'simulate' not in bundle.completed_nodes
    with pytest.raises(ValueError):
        service.review(_decision(bundle, 'approve'))


def test_exported_hash_detects_changed_advisory_text() -> None:
    service, bundle, calls = _start()
    raw = json.loads(bundle.model_dump_json())
    raw['snapshot']['explanation']['deterministic_summary'][0] += ' changed'
    with pytest.raises(ValueError, match='hash mismatch'):
        ReviewBundle.model_validate_json(json.dumps(raw))


def test_memory_scope_does_not_claim_restart_persistence() -> None:
    service, bundle, calls = _start()
    with pytest.raises(ValueError, match='Unknown run'):
        WorkflowService().get(bundle.run_id)


@pytest.mark.parametrize('change', ['source', 'battery', 'authorization', 'parallel', 'deadline', 'recovery_limit'])
def test_hash_binds_inputs_and_options_even_with_same_run_and_revision(change: str) -> None:
    from ota_verifier.workflow_models import snapshot_hash
    request, case = example_input('no_updates')
    original = WorkflowService().start(WorkflowInput(request=request), fixture_dependencies(case))
    raw = json.loads(WorkflowInput(request=request).model_dump_json())
    if change == 'source':
        raw['request']['documents'][0]['text'] += ' Additional context only.'
    elif change == 'battery':
        raw['request']['campaign']['initial_state']['battery_percent'] = 79
    elif change == 'authorization':
        raw['request']['campaign']['downgrade_authorizations'] = [dict(ecu_id='gateway', version='1',
            authorized_by='reviewer', reason='Explicit test permission')]
    elif change == 'parallel':
        raw['planning_options']['max_parallel'] = 2
    elif change == 'deadline':
        raw['planning_options']['deadline_ms'] = 0
    else:
        raw['simulation_options']['max_recovery_states'] = 7
    changed = WorkflowInput.model_validate_json(json.dumps(raw))
    newer = WorkflowService().start(changed, fixture_dependencies(case))
    assert snapshot_hash('same-run', 1, original.snapshot) != snapshot_hash('same-run', 1, newer.snapshot)


def test_prior_identical_approval_retry_is_stale_after_revision() -> None:
    service, bundle, calls = _start('no_updates')
    submission = _decision(bundle, 'approve')
    service.review(submission)
    request, case = example_input('no_updates')
    service.revise(bundle.run_id, WorkflowInput(request=request), fixture_dependencies(case))
    with pytest.raises(ValueError, match='stale'):
        service.review(submission)


def test_fault_search_uncertainty_remains_visible_and_cannot_be_approved() -> None:
    from ota_verifier.llm.models import DocumentRequest
    from ota_verifier.simulation_models import SimulationOptions
    request, case = example_input()
    raw = json.loads(request.model_dump_json())
    raw['campaign']['downgrade_authorizations'] = [dict(ecu_id=ecu['id'], version='1',
        authorized_by='reviewer', reason='Explicit fault test rollback permission') for ecu in raw['campaign']['ecus']]
    request = DocumentRequest.model_validate_json(json.dumps(raw))
    service = WorkflowService()
    bundle = service.start(WorkflowInput(request=request, simulation_options=SimulationOptions(max_recovery_states=1)),
                           fixture_dependencies(case))
    report = bundle.snapshot.artifacts.simulation
    assert any(case.assessment == 'inconclusive' for case in report.cases)
    assert report.assessment == 'violations'  # Historical boot failures still dominate the overall verdict.
    assert not approval_eligible(bundle.snapshot)
    with pytest.raises(ValueError):
        service.review(_decision(bundle, 'approve'))


def test_local_workflow_disables_ambient_external_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    from langsmith import get_tracing_context
    monkeypatch.setenv('LANGSMITH_TRACING', 'true')
    request, case = example_input('no_updates')
    dependencies = fixture_dependencies(case)
    purposes: list[str] = []

    @dataclass
    class CheckTracing:
        inner: JsonClient

        def generate_json(self, **kwargs: Any) -> Any:
            assert get_tracing_context().get('enabled') is False
            purposes.append(kwargs['purpose'])
            return self.inner.generate_json(**kwargs)

    service = WorkflowService()
    bundle = service.start(WorkflowInput(request=request), WorkflowClients(CheckTracing(dependencies.extractor),
        explainer=CheckTracing(dependencies.explainer)))
    service.review(_decision(bundle, 'approve'))
    assert purposes == ['extraction', 'verification', 'explanation']
