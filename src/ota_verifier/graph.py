"""Checkpointed simulation review workflow; no vehicle execution or deployment."""
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
import re
from threading import RLock
from typing import Any, TypedDict, TypeVar
from uuid import uuid4
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langsmith import tracing_context
from pydantic import BaseModel
from .evidence import evidence_catalog
from .boot_comparison import compare_boot_policies
from .llm.client import JsonClient
from .llm.evidence import canonical_json
from .llm.explainer import explain_results
from .llm.models import ExtractionRun
from .llm.pipeline import extract_and_verify, verified_campaign
from .models import PlanningResult
from .planner import plan_campaign
from .simulator import stress_test
from .workflow_models import (AnalysisArtifacts, ReviewBundle, ReviewDecision, ReviewSnapshot,
                              ReviewSubmission, WorkflowInput, approval_eligible, snapshot_hash)

Model = TypeVar('Model', bound=BaseModel)
# Z3's default context is shared by this process; serialize workflow planning
# across Streamlit sessions without changing deterministic planner semantics.
_PLANNING_LOCK = RLock()


class WorkflowState(TypedDict, total=False):
    """Checkpoint data stays plain JSON; credentials and clients remain outside it."""
    run_id: str
    revision: int
    input: dict[str, Any]
    extraction: dict[str, Any]
    planning: dict[str, Any] | None
    simulation: dict[str, Any] | None
    comparison: dict[str, Any] | None
    snapshot: dict[str, Any]
    pending_decision: dict[str, Any] | None
    decision: dict[str, Any] | None
    completed_nodes: list[str]


@dataclass(frozen=True)
class WorkflowClients:
    """Explicit dependency injection for the three allowed model purposes."""
    extractor: JsonClient
    verifier: JsonClient | None = None
    explainer: JsonClient | None = None


def _parse(model: type[Model], value: Any) -> Model:
    return model.model_validate_json(canonical_json(value))


def _visited(state: WorkflowState, node: str) -> list[str]:
    return [*state.get('completed_nodes', []), node]


def _artifacts(state: WorkflowState) -> AnalysisArtifacts:
    extraction = _parse(ExtractionRun, state['extraction'])
    planning = state.get('planning')
    simulation = state.get('simulation')
    if extraction.status == 'blocked':
        status = 'extraction_blocked'
    elif planning is None:
        raise RuntimeError('Review requires a planning result')
    elif planning['status'] != 'feasible':
        status = 'planning_infeasible' if planning['status'] == 'infeasible' else 'planning_unknown'
    elif simulation is None:
        raise RuntimeError('Review requires stress-test evidence')
    else:
        incoming = _parse(WorkflowInput, state['input'])
        selected = incoming.selected_policy
        assessment = state['comparison']['guarded']['assessment'] if selected is not None and selected.id == 'guarded-trial-v1' and state.get('comparison') is not None else simulation['assessment']
        status = {'passed': 'simulation_passed', 'violations': 'simulation_violations',
                  'inconclusive': 'simulation_inconclusive'}[assessment]
    return _parse(AnalysisArtifacts, {'input': state['input'], 'extraction': state['extraction'],
        'planning': planning, 'simulation': simulation, 'comparison': state.get('comparison'), 'status': status})


def build_graph(clients_for_thread: Callable[[str], WorkflowClients],
                checkpointer: BaseCheckpointSaver | None = None,
                review_recorder: Callable[[ReviewSubmission, ReviewSnapshot], ReviewDecision] | None = None) -> CompiledStateGraph:
    """Build StateGraph with conditional stages and a static human-review pause."""
    def clients(config: RunnableConfig) -> WorkflowClients:
        return clients_for_thread(str(config['configurable']['thread_id']))

    def extract(state: WorkflowState, config: RunnableConfig) -> dict[str, Any]:
        incoming = _parse(WorkflowInput, state['input'])
        dependencies = clients(config)
        result = extract_and_verify(incoming.request, dependencies.extractor, dependencies.verifier)
        return {'extraction': result.model_dump(mode='json'), 'planning': None, 'simulation': None,
                'comparison': None, 'completed_nodes': _visited(state, 'extract')}

    def plan(state: WorkflowState) -> dict[str, Any]:
        incoming = _parse(WorkflowInput, state['input'])
        campaign = verified_campaign(_parse(ExtractionRun, state['extraction']))
        with _PLANNING_LOCK:
            result = plan_campaign(campaign, incoming.planning_options)
        return {'planning': result.model_dump(mode='json'), 'completed_nodes': _visited(state, 'plan')}

    def simulate(state: WorkflowState) -> dict[str, Any]:
        incoming = _parse(WorkflowInput, state['input'])
        artifacts = state['planning']
        if artifacts is None or artifacts['status'] != 'feasible':
            raise RuntimeError('Simulation cannot run without a feasible plan')
        from .models import FeasibleResult
        result = _parse(FeasibleResult, artifacts)
        campaign = verified_campaign(_parse(ExtractionRun, state['extraction']))
        report = stress_test(campaign, result.plan, incoming.simulation_options)
        return {'simulation': report.model_dump(mode='json'), 'completed_nodes': _visited(state, 'simulate')}

    def compare_policies(state: WorkflowState) -> dict[str, Any]:
        incoming = _parse(WorkflowInput, state['input'])
        if incoming.comparison_options is None:
            raise RuntimeError('Boot comparison requires explicit policy options')
        from .models import FeasibleResult
        from .simulation_models import StressReport
        planning = _parse(FeasibleResult, state['planning'])
        baseline = _parse(StressReport, state['simulation'])
        campaign = verified_campaign(_parse(ExtractionRun, state['extraction']))
        result = compare_boot_policies(campaign, planning.plan, incoming.simulation_options,
                                      incoming.comparison_options, baseline)
        return {'comparison': result.model_dump(mode='json'), 'completed_nodes': _visited(state, 'compare_policies')}

    def explain(state: WorkflowState, config: RunnableConfig) -> dict[str, Any]:
        artifacts = _artifacts(state)
        facts = evidence_catalog(artifacts)
        explanation = explain_results(artifacts.status, facts, clients(config).explainer)
        snapshot = ReviewSnapshot(artifacts=artifacts, facts=facts, explanation=explanation,
            rules_version='workflow-v2' if artifacts.input.selected_policy is not None else 'workflow-v1')
        return {'snapshot': snapshot.model_dump(mode='json'), 'completed_nodes': _visited(state, 'explain')}

    def prepare_review(state: WorkflowState) -> dict[str, Any]:
        return {'pending_decision': None, 'decision': None,
                'completed_nodes': _visited(state, 'prepare_review')}

    def human_review(state: WorkflowState) -> dict[str, Any]:
        if state.get('pending_decision') is None:
            raise ValueError('An explicit human decision is required before resuming review')
        submission = _parse(ReviewSubmission, state['pending_decision'])
        snapshot = _parse(ReviewSnapshot, state['snapshot'])
        digest = snapshot_hash(state['run_id'], state['revision'], snapshot)
        if (submission.run_id != state['run_id'] or submission.revision != state['revision']
                or submission.snapshot_hash != digest):
            raise ValueError('Review submission is stale or belongs to another run')
        if submission.action == 'approve' and not approval_eligible(snapshot):
            raise ValueError('Only complete passing simulation analysis can be approved')
        if state.get('decision') is not None:
            previous = _parse(ReviewDecision, state['decision'])
            if previous.submission != submission:
                raise ValueError('This snapshot already has a final decision')
            return {}
        decision = (review_recorder(submission, snapshot) if review_recorder is not None else
                    ReviewDecision(submission=submission, recorded_at_utc=datetime.now(UTC).isoformat()))
        if decision.submission != submission:
            raise ValueError('Review recorder returned a decision for another submission')
        return {'decision': decision.model_dump(mode='json'), 'pending_decision': None,
                'completed_nodes': _visited(state, 'human_review')}

    graph = StateGraph(WorkflowState)
    for name, node in (('extract', extract), ('plan', plan), ('simulate', simulate),
                       ('compare_policies', compare_policies), ('explain', explain), ('prepare_review', prepare_review), ('human_review', human_review)):
        graph.add_node(name, node)
    graph.add_edge(START, 'extract')
    graph.add_conditional_edges('extract', lambda state: 'plan' if state['extraction']['status'] == 'ready' else 'explain',
                                {'plan': 'plan', 'explain': 'explain'})
    graph.add_conditional_edges('plan', lambda state: 'simulate' if state['planning']['status'] == 'feasible' else 'explain',
                                {'simulate': 'simulate', 'explain': 'explain'})
    graph.add_conditional_edges('simulate', lambda state: 'compare_policies' if _parse(WorkflowInput, state['input']).comparison_options is not None else 'explain',
                                {'compare_policies': 'compare_policies', 'explain': 'explain'})
    graph.add_edge('compare_policies', 'explain')
    graph.add_edge('explain', 'prepare_review')
    graph.add_edge('prepare_review', 'human_review')
    graph.add_edge('human_review', END)
    return graph.compile(checkpointer=checkpointer or MemorySaver(), interrupt_before=['human_review'])


class WorkflowService:
    """Process-local run isolation, revision management, and idempotent review.

    In-memory checkpointing supports pause/resume while this service lives. JSON
    exports are read-only evidence; they do not restore executable checkpoints.
    The public service boundary, not the breakpoint alone, enforces decisions.
    """

    def __init__(self) -> None:
        self.policy_rules_version = 'workflow-v2'
        self._registry_lock = RLock()
        self._locks: dict[str, RLock] = {}
        self._revisions: dict[str, int] = {}
        self._clients: dict[str, WorkflowClients] = {}
        self._history: dict[str, list[ReviewDecision]] = {}
        self.graph = build_graph(lambda thread_id: self._clients[thread_id])

    def _config(self, run_id: str) -> RunnableConfig:
        return {'configurable': {'thread_id': f'{run_id}:{self._revisions[run_id]}'}}

    def _lock(self, run_id: str) -> RLock:
        with self._registry_lock:
            if run_id not in self._locks:
                raise ValueError('Unknown run ID in this process/session')
            return self._locks[run_id]

    def _execute(self, run_id: str, incoming: WorkflowInput, clients: WorkflowClients) -> ReviewBundle:
        revision = self._revisions[run_id]
        self._clients[f'{run_id}:{revision}'] = clients
        with tracing_context(enabled=False):
            self.graph.invoke({'run_id': run_id, 'revision': revision, 'input': incoming.model_dump(mode='json'),
                               'completed_nodes': []}, self._config(run_id))
        return self.get(run_id)

    def start(self, incoming: WorkflowInput, clients: WorkflowClients, run_id: str | None = None) -> ReviewBundle:
        """Analyze a new isolated run and pause before its human-review node."""
        run_id = run_id or uuid4().hex
        if not re.fullmatch(r'[A-Za-z0-9_-]+', run_id):
            raise ValueError('Run ID must contain only letters, numbers, underscores, or hyphens')
        with self._registry_lock:
            if run_id in self._revisions:
                raise ValueError('Run ID already exists; use revise for changed inputs')
            self._locks[run_id] = RLock()
            self._revisions[run_id] = 1
            self._history[run_id] = []
        with self._lock(run_id):
            return self._execute(run_id, incoming, clients)

    def revise(self, run_id: str, incoming: WorkflowInput, clients: WorkflowClients) -> ReviewBundle:
        """Create a fresh checkpoint revision; previous decisions become historical only."""
        with self._lock(run_id):
            self.get(run_id)  # Reconcile an existing node decision before changing revisions.
            self._revisions[run_id] += 1
            return self._execute(run_id, incoming, clients)

    def get(self, run_id: str) -> ReviewBundle:
        """Return current evidence without executing a node or making a model call."""
        with self._lock(run_id):
            state = self.graph.get_state(self._config(run_id)).values
            if not state.get('snapshot'):
                raise ValueError('Run has no complete analysis snapshot')
            snapshot = _parse(ReviewSnapshot, state['snapshot'])
            revision = self._revisions[run_id]
            digest = snapshot_hash(run_id, revision, snapshot)
            decision = _parse(ReviewDecision, state['decision']) if state.get('decision') else None
            history = self._history[run_id]
            if decision is not None and decision not in history:
                if any(item.submission.idempotency_key == decision.submission.idempotency_key for item in history):
                    raise ValueError('Checkpoint conflicts with recorded review history')
                history.append(decision)
            current = decision if decision is not None and decision.submission.snapshot_hash == digest and decision.submission.revision == revision else None
            if current:
                review_state = {'approve': 'approved', 'reject': 'rejected',
                                'review_with_findings': 'reviewed_with_findings'}[current.submission.action]
            else:
                review_state = 'invalidated' if history else 'awaiting_review'
            return ReviewBundle(format_version='review-bundle-v2' if snapshot.rules_version == 'workflow-v2' else 'review-bundle-v1',
                run_id=run_id, revision=revision, snapshot=snapshot, snapshot_hash=digest,
                review_state=review_state, current_decision=current, decisions=tuple(history),
                completed_nodes=tuple(state.get('completed_nodes', [])))

    def resume(self, run_id: str) -> ReviewBundle:
        """Read a paused/completed run; no implicit human decision or repeated analysis."""
        return self.get(run_id)

    def review(self, submission: ReviewSubmission) -> ReviewBundle:
        """Apply one explicit hash-bound decision, idempotently under a per-run lock."""
        with self._lock(submission.run_id):
            bundle = self.get(submission.run_id)
            if submission.snapshot_hash != bundle.snapshot_hash or submission.revision != bundle.revision:
                raise ValueError('Review is stale; inspect the current revision before submitting')
            for previous in bundle.decisions:
                if previous.submission.idempotency_key == submission.idempotency_key:
                    if previous.submission != submission:
                        raise ValueError('Idempotency key was already used for a different decision')
                    return bundle
            if bundle.current_decision is not None:
                raise ValueError('This snapshot already has a final decision')
            if submission.action == 'approve' and not approval_eligible(bundle.snapshot):
                raise ValueError('Violations or inconclusive analysis cannot be approved')
            with tracing_context(enabled=False):
                self.graph.update_state(self._config(submission.run_id),
                    {'pending_decision': submission.model_dump(mode='json')}, as_node='prepare_review')
                self.graph.invoke(None, self._config(submission.run_id))
            result = self.get(submission.run_id)
            if result.current_decision is None:
                raise RuntimeError('Review node did not record the explicit decision')
            return result
