"""Policy-specific reviews retain comparison failures and reject cross-policy approvals."""
import json
from pathlib import Path
from typing import Any
import pytest
from ota_verifier.boot_models import GuardedOptions
from ota_verifier.graph import WorkflowService
from ota_verifier.persistence.service import PersistentWorkflowService
from ota_verifier.persistence.diff import compare_revisions
from ota_verifier.workflow_examples import example_input, fixture_dependencies
from ota_verifier.workflow_models import (AnalysisArtifacts, PolicySelection, ReviewBundle, ReviewSnapshot,
    ReviewSubmission, WorkflowInput, approval_eligible, snapshot_hash)


def create(service: Any, example: str = 'authorized_rollback', policy: str | None = 'guarded-trial-v1', **options: Any) -> ReviewBundle:
    """Analyze explicitly labeled synthetic data using the requested policy."""
    request, case = example_input(example)
    selection = None if policy is None else PolicySelection(id=policy, guarded_options=GuardedOptions() if policy == 'guarded-trial-v1' else None)
    return service.start(WorkflowInput(request=request, selected_policy=selection, **options), fixture_dependencies(case))


def approve(bundle: ReviewBundle, key: str = 'review') -> ReviewSubmission:
    """Bind the human decision to the complete policy-specific evidence."""
    return ReviewSubmission(run_id=bundle.run_id, revision=bundle.revision, snapshot_hash=bundle.snapshot_hash,
        idempotency_key=key, action='approve', reviewer='Simulation reviewer', reason='Reviewed selected policy and retained comparison evidence')


def test_guarded_selection_passes_without_erasing_baseline_violations() -> None:
    service = WorkflowService()
    bundle = create(service)
    artifacts = bundle.snapshot.artifacts
    assert artifacts.status == 'simulation_passed'
    assert artifacts.simulation.assessment == artifacts.comparison.baseline.assessment == 'violations'
    assert artifacts.comparison.guarded.assessment == 'passed'
    assert len(artifacts.simulation.cases) == 42
    assert len(artifacts.comparison.guarded.cases) == 48
    assert bundle.format_version == 'review-bundle-v2'
    assert bundle.snapshot.rules_version == 'workflow-v2'
    assert approval_eligible(bundle.snapshot)
    assert service.review(approve(bundle)).review_state == 'approved'
    assert ReviewBundle.model_validate_json(service.get(bundle.run_id).model_dump_json()).review_state == 'approved'
    facts = {fact.id: fact for fact in bundle.snapshot.facts}
    assert facts['selected-policy'].required_in_explanation
    assert 'guarded-trial-v1' in facts['selected-policy'].message
    assert facts['simulation'].outcome == 'violation'
    assert facts['guarded-simulation'].outcome == 'passed'
    assert bundle.snapshot.explanation.status == 'fixture'
    assert 'selected-policy' in {statement.evidence_id for statement in bundle.snapshot.explanation.draft.statements}


@pytest.mark.parametrize('policy', [None, 'baseline-v1'])
def test_passing_comparator_does_not_approve_baseline(policy: str | None) -> None:
    service = WorkflowService()
    bundle = create(service, policy=policy, boot_comparison=GuardedOptions())
    assert bundle.snapshot.artifacts.status == 'simulation_violations'
    assert bundle.snapshot.artifacts.comparison.guarded.assessment == 'passed'
    assert not approval_eligible(bundle.snapshot)
    with pytest.raises(ValueError):
        service.review(approve(bundle))
    assert service.get(bundle.run_id).current_decision is None


@pytest.mark.parametrize('example', ['clear', 'ambiguous', 'order_conflict'])
def test_guarded_selection_cannot_approve_violations_or_unexecuted_analysis(example: str) -> None:
    service = WorkflowService()
    bundle = create(service, example=example)
    assert not approval_eligible(bundle.snapshot)
    with pytest.raises(ValueError):
        service.review(approve(bundle))
    if example != 'clear':
        assert bundle.snapshot.artifacts.comparison is None


def test_guarded_selection_does_not_grant_permissions() -> None:
    service = WorkflowService()
    bundle = create(service, example='clear')
    assert bundle.snapshot.artifacts.input.request.campaign.downgrade_authorizations == ()
    assert bundle.snapshot.artifacts.comparison.guarded.assessment == 'violations'
    assert any(finding.violation.code == 'rollback_unavailable'
        for case in bundle.snapshot.artifacts.comparison.guarded.cases for finding in case.findings)
    assert not approval_eligible(bundle.snapshot)


@pytest.mark.parametrize('payload', [
    {'id': 'guarded-trial-v1'},
    {'id': 'baseline-v1', 'guarded_options': {'max_trial_attempts': 2}},
    {'id': 'automatic-best'},
])
def test_invalid_policy_selection_fails_closed(payload: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        PolicySelection.model_validate_json(json.dumps(payload))


def test_conflicting_guarded_options_are_rejected() -> None:
    request, _ = example_input('clear')
    with pytest.raises(ValueError, match='differ'):
        WorkflowInput(request=request, selected_policy=PolicySelection(id='guarded-trial-v1',
            guarded_options=GuardedOptions(max_trial_attempts=1)), boot_comparison=GuardedOptions(max_trial_attempts=2))


def test_selected_policy_change_creates_new_hash_and_invalidates_review() -> None:
    service = WorkflowService()
    first = create(service)
    service.review(approve(first))
    request, case = example_input('authorized_rollback')
    second = service.revise(first.run_id, WorkflowInput(request=request,
        selected_policy=PolicySelection(id='baseline-v1'), boot_comparison=GuardedOptions()), fixture_dependencies(case))
    assert second.snapshot_hash != first.snapshot_hash
    assert second.review_state == 'invalidated' and second.current_decision is None
    assert len(second.decisions) == 1
    assert second.snapshot.artifacts.status == 'simulation_violations'
    with pytest.raises(ValueError, match='stale'):
        service.review(approve(first, 'stale'))
    changes = compare_revisions(first, second)
    assert any('selected_policy' in change.path for change in changes.changes)


def test_legacy_shape_and_rules_are_preserved() -> None:
    bundle = create(WorkflowService(), example='no_updates', policy=None)
    assert bundle.format_version == 'review-bundle-v1'
    assert bundle.snapshot.rules_version == 'workflow-v1'
    assert 'selected_policy' not in bundle.snapshot.artifacts.input.model_dump(mode='json')
    assert ReviewBundle.model_validate_json(bundle.model_dump_json()) == bundle


@pytest.mark.parametrize('field,wrong', [('format_version', 'review-bundle-v1'), ('rules_version', 'workflow-v1')])
def test_policy_evidence_cannot_be_downgraded_to_legacy_schema(field: str, wrong: str) -> None:
    bundle = create(WorkflowService())
    raw = bundle.model_dump(mode='json')
    if field == 'format_version':
        raw[field] = wrong
    else:
        raw['snapshot'][field] = wrong
    with pytest.raises(ValueError):
        ReviewBundle.model_validate_json(json.dumps(raw))


@pytest.mark.parametrize('mutation', ['missing_comparison', 'truncated_coverage', 'changed_options', 'wrong_status'])
def test_incomplete_or_mismatched_selected_evidence_is_rejected(mutation: str) -> None:
    bundle = create(WorkflowService())
    raw = bundle.snapshot.artifacts.model_dump(mode='json')
    if mutation == 'missing_comparison':
        raw['comparison'] = None
    elif mutation == 'truncated_coverage':
        raw['comparison']['guarded']['cases'].pop()
    elif mutation == 'changed_options':
        raw['input']['selected_policy']['guarded_options']['max_trial_attempts'] = 1
    else:
        raw['status'] = 'simulation_violations'
    with pytest.raises(ValueError):
        AnalysisArtifacts.model_validate_json(json.dumps(raw))


def test_guarded_approval_survives_restart_and_history_keeps_policy(tmp_path: Path) -> None:
    path = tmp_path / 'reviews.sqlite'
    with PersistentWorkflowService(path) as service:
        first = create(service)
        service.review(approve(first))
    with PersistentWorkflowService(path) as service:
        assert service.get(first.run_id).review_state == 'approved'
        assert service.export(first.run_id).review.format_version == 'review-bundle-v2'
        request, case = example_input('authorized_rollback')
        second = service.revise(first.run_id, WorkflowInput(request=request,
            selected_policy=PolicySelection(id='baseline-v1')), fixture_dependencies(case))
        assert second.review_state == 'invalidated'
        assert service.get_revision(first.run_id, 1).review_state == 'approved'
        with pytest.raises(ValueError):
            service.review(approve(second, 'cannot-approve-baseline'))


def test_guarded_pending_analysis_resumes_with_selected_policy(tmp_path: Path) -> None:
    path = tmp_path / 'reviews.sqlite'
    request, case = example_input('authorized_rollback')
    with PersistentWorkflowService(path) as service:
        service.begin(WorkflowInput(request=request, selected_policy=PolicySelection(id='guarded-trial-v1',
            guarded_options=GuardedOptions())), fixture_dependencies(case), run_id='guarded', pause_after='simulate')
    with PersistentWorkflowService(path) as service:
        bundle = service.resume('guarded')
        assert bundle.snapshot.artifacts.status == 'simulation_passed'
        assert approval_eligible(bundle.snapshot)


def test_selected_guarded_policy_with_exhausted_search_is_not_approvable() -> None:
    from ota_verifier.simulation_models import SimulationOptions
    bundle = create(WorkflowService(), simulation_options=SimulationOptions(max_recovery_states=1))
    assert any(case.recovery is not None and case.recovery.status == 'unknown'
        for case in bundle.snapshot.artifacts.comparison.guarded.cases)
    assert bundle.snapshot.artifacts.status != 'simulation_passed'
    assert not approval_eligible(bundle.snapshot)


def test_selected_guarded_policy_retains_availability_regressions() -> None:
    from ota_verifier.llm.client import FixtureClient
    from ota_verifier.llm.explainer import FixtureExplanationClient
    from ota_verifier.llm.models import DocumentRequest, ExtractedConstraint, ExtractionDraft, FaithfulnessVerdict, SourceDocument
    from ota_verifier.llm.evidence import source_segments
    from ota_verifier.models import Requires
    from ota_verifier.graph import WorkflowClients
    request, _ = example_input('authorized_rollback')
    sentences = ('gateway at versions >=1 requires brake at versions >=1.',
                 'brake at versions >=1 requires gateway at versions >=1.')
    document = SourceDocument(id='stable-cycle', text='\n'.join(sentences))
    segments = source_segments(document)
    entries = tuple(ExtractedConstraint(constraint=Requires(id=f'cycle-{index}', ecu=ecu, version_spec='>=1',
        needs=needs, needs_version_spec='>=1', source_document_id=document.id, source_text=segment.text), evidence=segment.evidence)
        for index, (ecu, needs, segment) in enumerate(zip(('gateway', 'brake'), ('brake', 'gateway'), segments, strict=True)))
    source = DocumentRequest(campaign=request.campaign, documents=(document,))
    draft = ExtractionDraft(constraints=entries, issues=())
    verdict = FaithfulnessVerdict(faithful=True, reviewed_constraint_ids=tuple(entry.constraint.id for entry in entries),
        reviewed_document_ids=(document.id,), issues=())
    clients = WorkflowClients(extractor=FixtureClient((draft.model_dump_json(), verdict.model_dump_json())), explainer=FixtureExplanationClient())
    service = WorkflowService()
    bundle = service.start(WorkflowInput(request=source, selected_policy=PolicySelection(id='guarded-trial-v1',
        guarded_options=GuardedOptions())), clients)
    assert bundle.snapshot.artifacts.comparison.regressed_cases > 0
    assert bundle.snapshot.artifacts.comparison.guarded.assessment == 'violations'
    assert not approval_eligible(bundle.snapshot)
    with pytest.raises(ValueError):
        service.review(approve(bundle))


def test_persistent_manifest_matches_actual_evidence_schema(tmp_path: Path) -> None:
    with PersistentWorkflowService(tmp_path / 'reviews.sqlite') as service:
        legacy = create(service, example='no_updates', policy=None)
        explicit = create(service, example='no_updates', policy='baseline-v1')
        assert service.export(legacy.run_id).versions.bundle_schema == legacy.format_version == 'review-bundle-v1'
        assert service.export(explicit.run_id).versions.bundle_schema == explicit.format_version == 'review-bundle-v2'


def test_selected_baseline_does_not_need_guarded_comparison() -> None:
    service = WorkflowService()
    bundle = create(service, example='no_updates', policy='baseline-v1')
    assert bundle.snapshot.artifacts.comparison is None
    assert approval_eligible(bundle.snapshot)
    assert service.review(approve(bundle)).review_state == 'approved'


def test_old_approval_cannot_cover_a_policy_changed_snapshot_even_with_new_hash() -> None:
    service = WorkflowService()
    bundle = service.review(approve(create(service)))
    raw = bundle.model_dump(mode='json')
    raw['snapshot']['artifacts']['input']['selected_policy'] = {'id': 'baseline-v1', 'guarded_options': None}
    raw['snapshot']['artifacts']['status'] = 'simulation_violations'
    raw['snapshot']['artifacts']['input']['boot_comparison'] = GuardedOptions().model_dump(mode='json')
    # Recompute the public hash, as an accidental/manual re-export might do.
    changed = ReviewSnapshot.model_validate_json(json.dumps(raw['snapshot']))
    digest = snapshot_hash(bundle.run_id, bundle.revision, changed)
    raw['snapshot_hash'] = digest
    raw['current_decision']['submission']['snapshot_hash'] = digest
    raw['decisions'][0]['submission']['snapshot_hash'] = digest
    with pytest.raises(ValueError, match='cannot be approved'):
        ReviewBundle.model_validate_json(json.dumps(raw))
