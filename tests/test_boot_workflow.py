"""Optional boot comparison is checkpointed, hash-bound, and never an approval bypass."""
import json
import pytest
from ota_verifier.boot_models import GuardedOptions
from ota_verifier.graph import WorkflowService
from ota_verifier.workflow_examples import example_input, fixture_dependencies
from ota_verifier.workflow_models import ReviewBundle, ReviewSubmission, WorkflowInput, approval_eligible


def test_comparison_is_an_explicit_extra_graph_stage() -> None:
    request, case = example_input('authorized_rollback')
    service = WorkflowService()
    bundle = service.start(WorkflowInput(request=request, boot_comparison=GuardedOptions()), fixture_dependencies(case))
    comparison = bundle.snapshot.artifacts.comparison
    assert comparison.baseline == bundle.snapshot.artifacts.simulation
    assert comparison.guarded.assessment == 'passed'
    assert comparison.baseline.assessment == 'violations'
    assert len(comparison.shared_cases) == 42
    assert len(comparison.guarded.cases) == 48
    assert comparison.improved_cases == 3
    assert bundle.completed_nodes == ('extract', 'plan', 'simulate', 'compare_policies', 'explain', 'prepare_review')
    assert bundle.snapshot.explanation.status == 'fixture'
    required = {statement.evidence_id for statement in bundle.snapshot.explanation.draft.statements}
    assert {'boot-comparison', 'guarded-simulation', 'boot-policy-assumptions'} <= required
    assert not approval_eligible(bundle.snapshot)
    submission = ReviewSubmission(idempotency_key='test', run_id=bundle.run_id, revision=1,
        snapshot_hash=bundle.snapshot_hash, action='approve', reviewer='demo', reason='Guarded policy passed')
    with pytest.raises(ValueError, match='cannot be approved'):
        service.review(submission)
    assert ReviewBundle.model_validate_json(bundle.model_dump_json()) == bundle


def test_disabled_comparison_preserves_legacy_serialized_snapshot_shape() -> None:
    request, case = example_input('no_updates')
    incoming = WorkflowInput(request=request)
    assert 'boot_comparison' not in incoming.model_dump(mode='json')
    bundle = WorkflowService().start(incoming, fixture_dependencies(case))
    assert 'comparison' not in bundle.snapshot.artifacts.model_dump(mode='json')
    assert 'compare_policies' not in bundle.completed_nodes
    assert ReviewBundle.model_validate_json(bundle.model_dump_json()) == bundle


@pytest.mark.parametrize('example', ['ambiguous', 'order_conflict'])
def test_blocked_and_infeasible_analysis_never_runs_comparison(example: str) -> None:
    request, case = example_input(example)
    bundle = WorkflowService().start(WorkflowInput(request=request, boot_comparison=GuardedOptions()), fixture_dependencies(case))
    assert bundle.snapshot.artifacts.comparison is None
    assert 'compare_policies' not in bundle.completed_nodes


def test_policy_options_and_comparison_evidence_are_bound_to_review_hash() -> None:
    request, case = example_input('no_updates')
    service = WorkflowService()
    first = service.start(WorkflowInput(request=request, boot_comparison=GuardedOptions(max_trial_attempts=1)), fixture_dependencies(case))
    submission = ReviewSubmission(idempotency_key='approval', run_id=first.run_id, revision=1,
        snapshot_hash=first.snapshot_hash, action='approve', reviewer='demo', reason='Zero update steps explicitly reviewed')
    service.review(submission)
    second = service.revise(first.run_id, WorkflowInput(request=request, boot_comparison=GuardedOptions(max_trial_attempts=2)), fixture_dependencies(case))
    assert second.current_decision is None and second.review_state == 'invalidated'
    assert second.snapshot_hash != first.snapshot_hash
    with pytest.raises(ValueError, match='stale'):
        service.review(submission)
    raw = json.loads(second.model_dump_json())
    raw['snapshot']['artifacts']['comparison']['assumptions'][0] += ' changed'
    with pytest.raises(ValueError):
        ReviewBundle.model_validate_json(json.dumps(raw))
