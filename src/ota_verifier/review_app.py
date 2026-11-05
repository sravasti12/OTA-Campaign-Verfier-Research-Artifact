"""Local Streamlit review screen over the checkpointed simulation workflow."""
import json
from typing import Any
import altair as alt
import pandas as pd
from pydantic import ValidationError
import streamlit as st
from .graph import WorkflowService
from .shared import SharedWorkflowService
from .shared_review import shared_gate
from .persistence.operations import export_id
from .persistence.service import PersistentWorkflowService
from .persistence.store import RunNotReady, StorageError
from .persistence.locks import WorkspaceBusy
from .persistence_review import render_library, render_pending, render_history
from .boot_models import GuardedOptions
from .boot_review import render_boot_comparison
from .llm.client import LLMError
from .llm.evidence import canonical_json, content_hash
from .llm.models import DocumentRequest
from .models import PlanningOptions
from .review_views import ANALYSIS_LABELS, REVIEW_LABELS, decision_labels, inputs_current, vehicle_rows
from .simulation_models import SimulationOptions
from .workflow_examples import example_input, fixture_dependencies, live_dependencies
from .workflow_models import PolicySelection, ReviewBundle, ReviewSubmission, WorkflowInput

EXAMPLE_LABELS = {
    'Parallel update campaign': 'clear', 'Dependency-only campaign': 'dependency_only',
    'Conflicting flash order': 'order_conflict', 'Impossible intermediate versions': 'intermediate_trap',
    'Ambiguous requirement': 'ambiguous', 'Unsupported requirement': 'unsupported',
    'No updates (approval demo)': 'no_updates',
    'Authorized rollback comparison': 'authorized_rollback',
}


def _initialize() -> None:
    if 'workflow_service' not in st.session_state:
        st.session_state.workflow_service = WorkflowService()
    if ('active_run_id' not in st.session_state
            and ('compare_policies' not in st.session_state.workflow_service.graph.nodes
                 or getattr(st.session_state.workflow_service, 'policy_rules_version', None) != 'workflow-v2')):
        st.session_state.workflow_service = WorkflowService()
    if 'fixture_example' not in st.session_state:
        st.session_state.fixture_example = 'clear'
    if 'request_json' not in st.session_state:
        request, _ = example_input()
        st.session_state.request_json = request.model_dump_json(indent=2)



def _workspace_ready() -> bool:
    """Preserve an older live workspace instead of silently dropping its review data."""
    service = st.session_state.workflow_service
    if 'compare_policies' in service.graph.nodes and getattr(service, 'policy_rules_version', None) == 'workflow-v2':
        return True
    st.warning('This workspace uses an older review graph. Its analysis is retained; open a current workspace to analyze explicit policies.')
    if 'active_run_id' in st.session_state:
        previous = service.get(st.session_state.active_run_id)
        st.download_button('Download previous workspace review bundle', previous.model_dump_json(indent=2),
            file_name=f'ota-review-{previous.run_id}-r{previous.revision}.json', mime='application/json')
    if st.button('Keep previous workspace and start Phase 9', key='upgrade_workspace'):
        archives = st.session_state.get('previous_workspaces', [])
        st.session_state.previous_workspaces = [*archives, service]
        st.session_state.workflow_service = WorkflowService()
        st.session_state.pop('active_run_id', None)
        st.rerun()
    return False


def _load_selected_example() -> None:
    """Replace the draft before widgets render; retain analysis options and evidence."""
    label = st.session_state.example_campaign
    name = EXAMPLE_LABELS[label]
    request, _ = example_input(name)
    st.session_state.fixture_example = name
    st.session_state.request_json = request.model_dump_json(indent=2)
    st.session_state.example_load_notice = label


def _controls() -> tuple[WorkflowInput | None, bool, str]:
    with st.sidebar:
        st.subheader('Campaign workspace')
        mode = st.radio('Response source', ['Offline fixtures', 'Configured provider'], key='response_source')
        st.selectbox('Example campaign', list(EXAMPLE_LABELS), key='example_campaign')
        st.button('Load example', key='load_example', on_click=_load_selected_example)
        st.caption('Load replaces source documents and inventory. Your selected policy and analysis limits stay unchanged.')
        st.caption('Offline fixtures use canned responses. Configured providers run only when you analyze.')
        unlimited = st.checkbox('Unlimited write channels', value=False, key='unlimited')
        parallel = st.number_input('Concurrent write limit', min_value=1, max_value=64, value=2, key='parallel', disabled=unlimited)
        deadline_on = st.checkbox('Set campaign deadline', key='deadline_on')
        deadline = st.number_input('Deadline (minutes)', min_value=0.0, value=5.0, step=0.5, key='deadline_minutes', disabled=not deadline_on)
        policy = st.selectbox('Policy to review', ['Legacy baseline review', 'Baseline policy', 'Guarded trial boot policy'], key='selected_policy')
        st.caption('Selecting a policy creates policy-specific evidence on the next analysis. Legacy reviews retain their original gate.')
        if policy == 'Guarded trial boot policy':
            st.caption('Guarded selection always runs both policies, including every confirmation fault case.')
        compare = st.checkbox('Compare guarded trial boot', key='compare_boot')
        attempts = st.number_input('Maximum trial attempts', min_value=1, max_value=10, value=2, key='trial_attempts', disabled=not compare and policy != 'Guarded trial boot policy')
        with st.expander('Analysis limits'):
            timeout = st.number_input('Planner budget (milliseconds)', min_value=1, value=10000, key='planner_timeout')
            recovery_limit = st.number_input('Recovery state limit', min_value=1, value=10000, key='recovery_limit')
        st.divider()
        if isinstance(st.session_state.workflow_service, PersistentWorkflowService):
            st.caption('Simulation only. Runs and review decisions are saved in the selected local SQLite workspace.')
        else:
            st.caption('Simulation only. Sessions live in memory. Open the persistent library to save future runs across restarts.')
    loaded = st.session_state.pop('example_load_notice', None)
    if loaded is not None:
        st.success(f'Loaded example: {loaded}. Source JSON updated; select Analyze revision to recompute results.')
    with st.expander('Edit source documents and inventory', expanded=loaded is not None or 'active_run_id' not in st.session_state):
        st.text_area('Source-only request JSON', height=270, key='request_json')
        st.caption('Edits change the draft only. Analyze explicitly to create a new reviewed revision.')
    incoming: WorkflowInput | None = None
    try:
        request = DocumentRequest.model_validate_json(st.session_state.request_json)
        incoming = WorkflowInput(request=request,
            planning_options=PlanningOptions(max_parallel=None if unlimited else int(parallel),
                deadline_ms=int(round(float(deadline) * 60000)) if deadline_on else None, timeout_ms=int(timeout)),
            simulation_options=SimulationOptions(max_recovery_states=int(recovery_limit)),
            mode='fixture' if mode == 'Offline fixtures' else 'live',
            boot_comparison=GuardedOptions(max_trial_attempts=int(attempts)) if compare else None,
            selected_policy=(PolicySelection(id='guarded-trial-v1', guarded_options=GuardedOptions(max_trial_attempts=int(attempts)))
                if policy == 'Guarded trial boot policy' else PolicySelection(id='baseline-v1') if policy == 'Baseline policy' else None))
    except (ValueError, ValidationError):
        st.error('The draft request is invalid. Correct the JSON and inventory before analyzing.')
    current_service = st.session_state.workflow_service
    archived = (isinstance(current_service, PersistentWorkflowService) and 'active_run_id' in st.session_state
                and current_service.archive_info(st.session_state.active_run_id) is not None)
    if archived:
        st.info('This reviewed run is archived. Its evidence is available for reading and export.')
    analyze = st.button('Analyze revision', type='primary', key='analyze', disabled=incoming is None or archived or isinstance(st.session_state.workflow_service, SharedWorkflowService) and not st.session_state.workflow_service.allowed('analyze'))
    return incoming, analyze, st.session_state.fixture_example


def _analyze(incoming: WorkflowInput, example_name: str) -> None:
    if incoming.mode == 'fixture':
        _, case = example_input(example_name)
        clients = fixture_dependencies(case)
    else:
        clients = live_dependencies()
    service: WorkflowService = st.session_state.workflow_service
    with st.spinner('Extracting, checking, planning, and stress-testing the simulated campaign…'):
        if 'active_run_id' in st.session_state:
            bundle = service.revise(st.session_state.active_run_id, incoming, clients)
        else:
            bundle = service.start(incoming, clients)
            st.session_state.active_run_id = bundle.run_id
    st.session_state.last_bundle_hash = bundle.snapshot_hash


def _requirements(bundle: ReviewBundle) -> None:
    extraction = bundle.snapshot.artifacts.extraction
    st.subheader('Requirements and source evidence')
    if extraction.issues:
        for issue in extraction.issues:
            st.error(f'{issue.code}: {issue.message}')
    if extraction.draft:
        rows = [{'Constraint': entry.constraint.id, 'Type': entry.constraint.type,
                 'Document': entry.evidence.document_id, 'Start': entry.evidence.start_char,
                 'End': entry.evidence.end_char, 'Source sentence': entry.constraint.source_text}
                for entry in extraction.draft.constraints]
        if rows:
            st.dataframe(rows, hide_index=True, width='stretch')
        else:
            st.info('No formal constraints were extracted.')
    for document in extraction.request.documents:
        with st.expander(f'Source: {document.id}'):
            st.code(document.text, language=None)
    if extraction.verification:
        st.caption(f'Second-pass faithfulness judgment: {extraction.verification.faithful}. This is model evidence, not a proof or human approval.')


def _plan(bundle: ReviewBundle) -> None:
    result = bundle.snapshot.artifacts.planning
    st.subheader('Nominal plan')
    if result is None:
        st.info('Planning did not run because extraction was blocked.')
        return
    if result.status == 'unknown':
        st.warning(f'Planning is inconclusive: {result.reason}')
        return
    if result.status == 'infeasible':
        st.error('No nominal schedule satisfies the modeled constraints.')
        st.dataframe([item.model_dump() for item in result.conflict.items], hide_index=True, width='stretch')
        st.caption(f'Subset-minimal conflict proven: {result.conflict.subset_minimal}')
        return
    plan = result.plan
    st.caption(f'{len(plan.steps)} updates • {plan.makespan_ms / 60000:g} simulated minutes • minimum duration proven: {plan.optimal}')
    if plan.steps:
        frame = pd.DataFrame([{'ECU': step.ecu_id, 'Start (min)': step.start_ms / 60000,
            'End (min)': step.end_ms / 60000, 'Activation': step.activation_index,
            'From': step.from_version, 'To': step.to_version, 'Slot': step.write_slot} for step in plan.steps])
        chart = alt.Chart(frame).mark_bar(cornerRadius=4, height=24).encode(
            x=alt.X('Start (min):Q', title='Simulated minutes'), x2='End (min):Q',
            y=alt.Y('ECU:N', sort=None, title=None), color=alt.Color('ECU:N', legend=None),
            tooltip=list(frame.columns)).properties(height=max(140, len(plan.steps) * 44))
        st.altair_chart(chart, width='stretch')
        st.dataframe(frame, hide_index=True, width='stretch')
    else:
        st.info('No updates are needed. This campaign has zero fault cases; it does not demonstrate fault tolerance for an update.')
    index = st.selectbox('Nominal state after activation', list(range(len(plan.states))),
        format_func=lambda value: 'Initial state' if value == 0 else f'Activation {value}', key=f'activation_{bundle.revision}')
    st.dataframe(vehicle_rows(plan.states[index]), hide_index=True, width='stretch')
    st.caption('These are nominal active-version states. The fault explorer shows actual simulated intermediate slot contents.')


def _faults(bundle: ReviewBundle) -> None:
    report = bundle.snapshot.artifacts.simulation
    st.subheader('Baseline fault investigation' if bundle.snapshot.artifacts.input.selected_policy is not None else 'Fault investigation')
    if report is None:
        st.info('Fault simulation did not run without a feasible nominal plan.')
        return
    st.caption(f'Nominal: {report.nominal.assessment} • Fault coverage: {len(report.cases)}/{report.expected_fault_cases} • Assessment: {report.assessment}')
    if not report.cases:
        st.info('No flash steps means no injected-fault cases.')
        return
    def label(index: int) -> str:
        fault = report.cases[index].fault
        assert fault is not None
        return f'{index + 1}. {fault.ecu_id} — {fault.kind} {fault.when} {fault.stage}'
    case_index = st.selectbox('Fault scenario', list(range(len(report.cases))), format_func=label, key=f'fault_case_{bundle.revision}')
    case = report.cases[case_index]
    st.write(f'Fault-run assessment: **{case.assessment}**. Campaign execution: **{case.status}**.')
    if case.findings:
        st.dataframe([{'Invariant': finding.invariant, 'Trace event': finding.trace_index,
            'Code': finding.violation.code, 'ECUs': ', '.join(finding.violation.ecu_ids),
            'Constraint': finding.violation.constraint_id, 'Message': finding.violation.message,
            'Source': finding.violation.source_text} for finding in case.findings], hide_index=True, width='stretch')
    event_index = st.select_slider('Trace event', options=list(range(len(case.trace))), value=0,
                                   key=f'trace_{bundle.revision}_{case_index}')
    event = case.trace[event_index]
    st.caption(f'{event.time_ms} ms • {event.stage} • ECU: {event.ecu_id or "vehicle"} • Writing: {", ".join(event.writing_ecus) or "none"}')
    if event.message:
        st.text(event.message)
    st.dataframe(vehicle_rows(event.state), hide_index=True, width='stretch')
    recovery = case.recovery
    if recovery:
        st.write(f'Recovery: **{recovery.status}** • {recovery.examined_states} examined states')
        st.text(recovery.reason)
        if recovery.steps:
            st.dataframe([step.model_dump() for step in recovery.steps], hide_index=True, width='stretch')
        elif recovery.status == 'available':
            st.caption('Original active images were already selected; recovery uses an empty path.')
        if recovery.blockers:
            with st.expander('Rejected recovery candidates (not executed actions)'):
                st.dataframe([violation.model_dump() for violation in recovery.blockers], hide_index=True, width='stretch')


def _review(bundle: ReviewBundle, current: bool) -> None:
    st.subheader('Human review')
    selection = bundle.snapshot.artifacts.input.selected_policy
    if selection is not None:
        st.info(f'Review target: {selection.id}. This decision covers only this policy, its options, and this evidence hash.')
    st.caption(f'Run {bundle.run_id} • revision {bundle.revision}')
    st.code(bundle.snapshot_hash, language=None)
    explanation = bundle.snapshot.explanation
    st.write('Deterministic summary')
    for text in explanation.deterministic_summary:
        st.text(text)
    if explanation.status == 'fallback':
        st.warning('Advisory explanation unavailable or rejected. The deterministic evidence above remains available.')
        for issue in explanation.issues:
            st.text(issue)
    elif explanation.draft:
        with st.expander(f'Advisory explanation ({explanation.status})'):
            facts = {fact.id: fact for fact in bundle.snapshot.facts}
            for statement in explanation.draft.statements:
                st.text(statement.text)
                fact = facts[statement.evidence_id]
                st.caption(f'Evidence: {fact.id} • {fact.outcome}')
                if fact.source_text:
                    st.code(fact.source_text, language=None)
                if fact.case_index is not None:
                    policy = 'Guarded' if fact.id.startswith('guarded-') else 'Baseline'
                    st.caption(f'{policy} fault case {fact.case_index + 1}, trace event {fact.trace_index}')
    if not current:
        st.warning('Draft inputs changed. Any prior decision covers only the old snapshot. Analyze a new revision before reviewing.')
    if bundle.current_decision:
        decision = bundle.current_decision
        st.success(REVIEW_LABELS[bundle.review_state]) if bundle.review_state == 'approved' else st.info(REVIEW_LABELS[bundle.review_state])
        st.text(f'{decision.submission.reviewer}: {decision.submission.reason}')
        service = st.session_state.workflow_service
        verified = isinstance(service, PersistentWorkflowService) and any(
            record.revision == bundle.revision for record in service.review_authentication(bundle.run_id, bundle.revision))
        st.caption(f'Recorded at {decision.recorded_at_utc}. ' + ('Identity recorded through OIDC-authenticated review.' if verified else 'Reviewer identity was self-reported.'))
    else:
        labels = decision_labels(bundle)
        if 'Approve simulation proposal' not in labels:
            st.info('This evidence cannot receive approval. You can record review with findings or reject the proposal.')
        with st.form(f'review_form_{bundle.revision}'):
            action = st.selectbox('Decision', labels, key=f'decision_{bundle.revision}')
            shared_service = st.session_state.workflow_service
            if isinstance(shared_service, SharedWorkflowService):
                reviewer = shared_service.account().identity
                st.caption('Authenticated reviewer: ' + reviewer)
            else:
                reviewer = st.text_input('Reviewer', key=f'reviewer_{bundle.revision}')
            reason = st.text_area('Decision reason', key=f'reason_{bundle.revision}')
            submitted = st.form_submit_button('Record decision', disabled=not current or isinstance(shared_service, SharedWorkflowService) and not shared_service.allowed('review'))
        if submitted:
            values = {'Approve simulation proposal': 'approve', 'Reject proposal': 'reject',
                      'Review with findings': 'review_with_findings'}
            key = content_hash(canonical_json({'hash': bundle.snapshot_hash, 'action': values[action],
                                              'reviewer': reviewer, 'reason': reason}))
            try:
                submission = ReviewSubmission(idempotency_key=key, run_id=bundle.run_id, revision=bundle.revision,
                    snapshot_hash=bundle.snapshot_hash, action=values[action], reviewer=reviewer, reason=reason)
                st.session_state.workflow_service.review(submission)
                st.rerun()
            except (ValueError, ValidationError, StorageError, WorkspaceBusy) as error:
                st.error(str(error))
    st.caption('Approval records a simulation-proposal decision only. It cannot grant downgrade permissions or change invariant results.')
    if bundle.decisions:
        with st.expander('Decision history'):
            st.dataframe([{'Revision': decision.submission.revision, 'Action': decision.submission.action,
                'Reviewer': decision.submission.reviewer, 'Reason': decision.submission.reason,
                'Snapshot': decision.submission.snapshot_hash, 'Recorded UTC': decision.recorded_at_utc}
                for decision in bundle.decisions], hide_index=True, width='stretch')


def main() -> None:
    """Render a local review workspace; all expensive work requires explicit submission."""
    st.set_page_config(page_title='OTA Campaign Verifier', page_icon='🚗', layout='wide')
    if not shared_gate():
        return
    _initialize()
    st.title('OTA Campaign Verifier')
    st.caption('SIMULATION  /  Source evidence → deterministic analysis → human review')
    if not _workspace_ready():
        return
    render_library()
    incoming, analyze, example_name = _controls()
    if analyze and incoming is not None:
        try:
            _analyze(incoming, example_name)
        except (ValueError, LLMError, StorageError, WorkspaceBusy) as error:
            st.error(f'Analysis could not complete: {error}')
    if 'active_run_id' not in st.session_state:
        st.info('Load an example or supply source-only request JSON, then analyze to begin.')
        return
    service: WorkflowService = st.session_state.workflow_service
    try:
        bundle = service.get(st.session_state.active_run_id)
    except RunNotReady:
        if isinstance(service, PersistentWorkflowService):
            render_pending(service, st.session_state.active_run_id)
        return
    except (StorageError, ValueError) as error:
        st.error(f'Saved evidence could not be opened: {error}')
        return
    current = inputs_current(bundle, incoming)
    archived = isinstance(service, PersistentWorkflowService) and service.archive_info(bundle.run_id) is not None
    columns = st.columns(3)
    columns[0].metric(('Selected policy: ' + bundle.snapshot.artifacts.input.selected_policy.id) if bundle.snapshot.artifacts.input.selected_policy is not None else 'Baseline analysis' if bundle.snapshot.artifacts.comparison else 'Analysis', ANALYSIS_LABELS[bundle.snapshot.artifacts.status])
    columns[1].metric('Human decision', REVIEW_LABELS[bundle.review_state] if current else 'Draft changed')
    columns[2].metric('Revision', bundle.revision)
    if not current:
        st.warning('Unanalyzed changes are not covered by the displayed results or any prior approval.')
    if isinstance(service, SharedWorkflowService):
        st.code(export_id(service.export(bundle.run_id)), language=None)
    st.download_button('Download analyzed review bundle', data=(service.export(bundle.run_id).model_dump_json(indent=2) if isinstance(service, PersistentWorkflowService) else bundle.model_dump_json(indent=2)),
        file_name=f'ota-review-{bundle.run_id}-r{bundle.revision}.json', mime='application/json', key='download_bundle')
    if isinstance(service, PersistentWorkflowService):
        render_history(service, bundle.run_id)
    requirements, plan, faults, review = st.tabs(['Requirements', 'Plan', 'Faults', 'Review'])
    with requirements:
        _requirements(bundle)
    with plan:
        _plan(bundle)
    with faults:
        render_boot_comparison(bundle)
        _faults(bundle)
    with review:
        _review(bundle, current and not archived)
