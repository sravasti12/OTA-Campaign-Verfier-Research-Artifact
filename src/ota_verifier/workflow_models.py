"""Immutable analysis snapshots and human decisions for a simulation workflow."""
from typing import Annotated, Any, Literal, Self
from pydantic import Field, SerializerFunctionWrapHandler, model_serializer, model_validator
from .boot_comparison import PolicyComparison
from .boot_models import GuardedOptions
from .models import FeasibleResult, Identifier, PlanningOptions, PlanningResult, Record
from .simulation_models import SimulationOptions, StressReport
from .llm.evidence import canonical_json, content_hash
from .llm.explanation_models import AnalysisStatus, EvidenceFact, ExplanationResult
from .llm.models import DocumentRequest, ExtractionRun


class PolicySelection(Record):
    """An explicitly selected simulation policy and its immutable options."""
    id: Literal['baseline-v1', 'guarded-trial-v1']
    guarded_options: GuardedOptions | None = None

    @model_validator(mode='after')
    def matching_options(self) -> Self:
        """Require guarded options only for the guarded policy."""
        if (self.id == 'guarded-trial-v1') != (self.guarded_options is not None):
            raise ValueError('Guarded policy requires options; baseline policy forbids guarded options')
        return self


class WorkflowInput(Record):
    """Everything that can affect analysis, including explicit operating mode."""
    request: DocumentRequest
    planning_options: PlanningOptions = PlanningOptions()
    simulation_options: SimulationOptions = SimulationOptions()
    mode: Literal['fixture', 'live'] = 'fixture'
    boot_comparison: GuardedOptions | None = None
    selected_policy: PolicySelection | None = None

    @property
    def comparison_options(self) -> GuardedOptions | None:
        """Guarded selection always requires complete baseline/guarded comparison."""
        if self.selected_policy is not None and self.selected_policy.id == 'guarded-trial-v1':
            return self.selected_policy.guarded_options
        return self.boot_comparison

    @model_validator(mode='after')
    def consistent_policy_options(self) -> Self:
        """Never analyze two different guarded assumptions in the same revision."""
        if (self.selected_policy is not None and self.selected_policy.id == 'guarded-trial-v1'
                and self.boot_comparison is not None and self.boot_comparison != self.selected_policy.guarded_options):
            raise ValueError('Selected guarded options differ from comparison options')
        return self

    @model_serializer(mode='wrap')
    def serialize_legacy_input(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        """Omit disabled new options so baseline snapshots retain their prior shape."""
        result = handler(self)
        if self.boot_comparison is None:
            result.pop('boot_comparison', None)
        if self.selected_policy is None:
            result.pop('selected_policy', None)
        return result


class AnalysisArtifacts(Record):
    """Deterministic results remain separate from human and explanation states."""
    input: WorkflowInput
    extraction: ExtractionRun
    planning: PlanningResult | None
    simulation: StressReport | None
    status: AnalysisStatus
    comparison: PolicyComparison | None = None

    @model_serializer(mode='wrap')
    def serialize_legacy_artifacts(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        """Keep disabled comparison out of legacy snapshot hashes and exports."""
        result = handler(self)
        if self.comparison is None:
            result.pop('comparison', None)
        return result

    @model_validator(mode='after')
    def consistent_pipeline(self) -> Self:
        """Validate stage linkage and derive the only permissible analysis status."""
        if self.extraction.request != self.input.request:
            raise ValueError('Extraction input differs from workflow input')
        if self.extraction.status == 'blocked':
            if self.planning is not None or self.simulation is not None:
                raise ValueError('Blocked extraction cannot reach planning or simulation')
            expected = 'extraction_blocked'
        elif self.planning is None:
            raise ValueError('Ready extraction requires a planning result')
        elif self.planning.status != 'feasible':
            if self.simulation is not None:
                raise ValueError('Nonfeasible planning cannot reach simulation')
            expected = 'planning_infeasible' if self.planning.status == 'infeasible' else 'planning_unknown'
        else:
            if self.simulation is None or self.simulation.plan != self.planning.plan:
                raise ValueError('Feasible plan needs matching complete stress evidence')
            if self.planning.plan.options != self.input.planning_options or self.simulation.options != self.input.simulation_options:
                raise ValueError('Analysis options differ from reviewed input')
            if self.extraction.campaign is None or self.simulation.campaign_id != self.extraction.campaign.id:
                raise ValueError('Simulation campaign differs from extracted campaign')
            expected = {'passed': 'simulation_passed', 'violations': 'simulation_violations',
                        'inconclusive': 'simulation_inconclusive'}[self.simulation.assessment]
        if self.comparison is not None:
            if (self.input.comparison_options is None or self.simulation is None
                    or self.comparison.baseline != self.simulation
                    or self.comparison.campaign != self.extraction.campaign
                    or self.comparison.guarded.guarded_options != self.input.comparison_options):
                raise ValueError('Boot comparison differs from reviewed input or baseline results')
        elif self.input.comparison_options is not None and self.simulation is not None:
            raise ValueError('Requested boot comparison is missing')
        if (self.input.selected_policy is not None and self.input.selected_policy.id == 'guarded-trial-v1'
                and self.simulation is not None):
            if self.comparison is None:
                raise ValueError('Selected guarded policy needs complete comparison evidence')
            expected = {'passed': 'simulation_passed', 'violations': 'simulation_violations',
                        'inconclusive': 'simulation_inconclusive'}[self.comparison.guarded.assessment]
        if self.status != expected:
            raise ValueError('Workflow status disagrees with deterministic results')
        return self


class ReviewSnapshot(Record):
    """Full immutable payload reviewed by a human, including advisory output."""
    artifacts: AnalysisArtifacts
    facts: tuple[EvidenceFact, ...]
    explanation: ExplanationResult
    rules_version: Literal['workflow-v1', 'workflow-v2'] = 'workflow-v1'

    @model_validator(mode='after')
    def policy_schema(self) -> Self:
        """Do not interpret a policy-aware snapshot under legacy approval rules."""
        expected = 'workflow-v2' if self.artifacts.input.selected_policy is not None else 'workflow-v1'
        if self.rules_version != expected:
            raise ValueError('Snapshot rules version differs from policy selection schema')
        return self


class ReviewSubmission(Record):
    """A reviewer-supplied decision bound to one exact run revision and snapshot."""
    idempotency_key: Identifier
    run_id: Identifier
    revision: Annotated[int, Field(gt=0)]
    snapshot_hash: Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]
    action: Literal['approve', 'reject', 'review_with_findings']
    reviewer: Identifier
    reason: Identifier


class ReviewDecision(Record):
    """Self-reported reviewer identity, not an authenticated signature."""
    submission: ReviewSubmission
    recorded_at_utc: Identifier


ReviewState = Literal['awaiting_review', 'approved', 'rejected', 'reviewed_with_findings', 'invalidated']


def snapshot_hash(run_id: str, revision: int, snapshot: ReviewSnapshot) -> str:
    """Bind a decision to the run, revision, options, all artifacts, and explanation."""
    return content_hash(canonical_json({'run_id': run_id, 'revision': revision,
                                       'snapshot': snapshot.model_dump(mode='json')}))


def approval_eligible(snapshot: ReviewSnapshot) -> bool:
    """Allow simulation-proposal approval only after complete passing analysis."""
    artifacts = snapshot.artifacts
    if (artifacts.extraction.status != 'ready' or not isinstance(artifacts.planning, FeasibleResult)
            or artifacts.simulation is None or artifacts.status != 'simulation_passed'):
        return False
    selected = artifacts.input.selected_policy
    if selected is not None and selected.id == 'guarded-trial-v1':
        report = artifacts.comparison.guarded if artifacts.comparison is not None else None
        return report is not None and report.assessment == 'passed' and report.nominal.assessment == 'passed'
    baseline_passed = artifacts.simulation.assessment == 'passed' and artifacts.simulation.nominal.assessment == 'passed'
    # Historical v1 comparison reviews keep their original conservative gate.
    return baseline_passed and (selected is not None or artifacts.comparison is None
                                or artifacts.comparison.guarded.assessment == 'passed')


class ReviewBundle(Record):
    """Exportable evidence and immutable decision history, with active approval explicit."""
    format_version: Literal['review-bundle-v1', 'review-bundle-v2'] = 'review-bundle-v1'
    run_id: Identifier
    revision: Annotated[int, Field(gt=0)]
    snapshot: ReviewSnapshot
    snapshot_hash: Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]
    review_state: ReviewState
    current_decision: ReviewDecision | None
    decisions: tuple[ReviewDecision, ...]
    completed_nodes: tuple[str, ...]

    @model_validator(mode='after')
    def bound_review(self) -> Self:
        """Reject stale approvals, cross-run history, and unsupported passing labels."""
        expected_format = 'review-bundle-v2' if self.snapshot.rules_version == 'workflow-v2' else 'review-bundle-v1'
        if self.format_version != expected_format:
            raise ValueError('Bundle schema differs from snapshot rules version')
        if self.snapshot_hash != snapshot_hash(self.run_id, self.revision, self.snapshot):
            raise ValueError('Review snapshot hash mismatch')
        if any(item.submission.run_id != self.run_id for item in self.decisions):
            raise ValueError('Review history contains another run')
        keys = [item.submission.idempotency_key for item in self.decisions]
        if len(keys) != len(set(keys)):
            raise ValueError('Duplicate review idempotency key')
        if self.current_decision is None:
            if self.review_state not in ('awaiting_review', 'invalidated'):
                raise ValueError('Final review state requires a current decision')
        else:
            decision = self.current_decision
            if (decision not in self.decisions or decision.submission.snapshot_hash != self.snapshot_hash
                    or decision.submission.revision != self.revision):
                raise ValueError('Current decision does not cover this exact snapshot')
            expected = {'approve': 'approved', 'reject': 'rejected',
                        'review_with_findings': 'reviewed_with_findings'}[decision.submission.action]
            if self.review_state != expected:
                raise ValueError('Review state disagrees with decision')
            if decision.submission.action == 'approve' and not approval_eligible(self.snapshot):
                raise ValueError('Violations or inconclusive analysis cannot be approved')
        return self
