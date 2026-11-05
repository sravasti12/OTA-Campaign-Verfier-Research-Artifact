"""Optional SQLite run library for the local Streamlit review workspace."""
import json
from pathlib import Path
import streamlit as st
from .persistence.diff import compare_revisions
from .persistence.service import PersistentWorkflowService
from .persistence.store import StorageError
from .persistence.locks import WorkspaceBusy
from .workflow_examples import EXAMPLES, example_input
from .workflow_models import WorkflowInput


def _load_input(incoming: WorkflowInput) -> None:
    for name in EXAMPLES:
        if example_input(name)[0].documents == incoming.request.documents:
            st.session_state.fixture_example = name
            break
    st.session_state.request_json = incoming.request.model_dump_json(indent=2)
    st.session_state.response_source = 'Offline fixtures' if incoming.mode == 'fixture' else 'Configured provider'
    options = incoming.planning_options
    st.session_state.unlimited = options.max_parallel is None
    st.session_state.parallel = options.max_parallel or 2
    st.session_state.deadline_on = options.deadline_ms is not None
    st.session_state.deadline_minutes = (options.deadline_ms or 300000) / 60000
    st.session_state.planner_timeout = options.timeout_ms
    st.session_state.recovery_limit = incoming.simulation_options.max_recovery_states
    selection = incoming.selected_policy
    st.session_state.selected_policy = ('Legacy baseline review' if selection is None else
        'Baseline policy' if selection.id == 'baseline-v1' else 'Guarded trial boot policy')
    st.session_state.compare_boot = incoming.boot_comparison is not None
    st.session_state.trial_attempts = incoming.comparison_options.max_trial_attempts if incoming.comparison_options else 2


def render_library() -> None:
    """Open an explicit durable workspace; browsing never invokes an LLM."""
    with st.sidebar.expander('Persistent run library'):
        st.text_input('SQLite workspace path', value='.ota_state/reviews.sqlite', key='database_path')
        if st.button('Open SQLite workspace', key='open_database'):
            try:
                service = PersistentWorkflowService(Path(st.session_state.database_path))
                previous = st.session_state.workflow_service
                st.session_state.previous_workspaces = [*st.session_state.get('previous_workspaces', []), previous]
                st.session_state.workflow_service = service
                st.session_state.pop('active_run_id', None)
            except (StorageError, WorkspaceBusy, OSError) as error:
                st.error(str(error))
        service = st.session_state.workflow_service
        if not isinstance(service, PersistentWorkflowService):
            st.caption('Default storage is in memory. Open SQLite to retain future analyses and decisions across restarts. Existing memory runs remain in this session.')
            return
        st.caption(f'Local SQLite: {service.path}. Reviewer names are self-reported.')
        runs = service.list_runs()
        if not runs:
            st.info('No durable runs yet. Analyze to create one.')
            return
        selected = st.selectbox('Saved run', [run.run_id for run in runs], key='saved_run',
            format_func=lambda identifier: next(f'{run.campaign_id} / r{run.revision} / {run.status}' for run in runs if run.run_id == identifier))
        if st.button('Open saved run', key='open_saved_run'):
            try:
                row = service.store.revision(selected)
                _load_input(WorkflowInput.model_validate_json(row['input_json']))
                st.session_state.active_run_id = selected
            except (StorageError, WorkspaceBusy, ValueError) as error:
                st.error(str(error))


def render_pending(service: PersistentWorkflowService, run_id: str) -> None:
    """Display incomplete evidence and require an explicit resume or new revision."""
    partial = service.partial_evidence(run_id)
    st.warning(f"Analysis is {partial['status']}. {partial['message'] or 'No complete review snapshot is available.'}")
    st.caption('Resume continues committed work. If a provider call is uncertain, inspect the saved evidence and explicitly analyze a new revision to retry.')
    st.download_button('Download interrupted evidence', json.dumps(partial, indent=2),
        file_name=f'ota-interrupted-{run_id}.json', mime='application/json')
    if st.button('Resume saved analysis', key='resume_analysis', disabled=partial['status'] == 'uncertain'):
        try:
            service.resume(run_id)
            st.rerun()
        except (StorageError, WorkspaceBusy, ValueError) as error:
            st.error(str(error))


def render_history(service: PersistentWorkflowService, run_id: str) -> None:
    """Inspect version manifests and literal diffs without changing the review target."""
    with st.expander('Saved revisions and implementation versions'):
        revisions = service.revisions(run_id)
        st.dataframe([revision.model_dump() for revision in revisions], hide_index=True)
        ready = [revision.revision for revision in revisions if revision.status == 'ready']
        if not ready:
            return
        selected = st.selectbox('Historical revision', ready, key=f'history_{run_id}')
        envelope = service.export(run_id, selected)
        st.json(envelope.versions.model_dump(mode='json'), expanded=False)
        st.download_button('Download versioned historical evidence', envelope.model_dump_json(indent=2),
            file_name=f'ota-persistent-{run_id}-r{selected}.json', mime='application/json')
        current = service.get(run_id)
        if selected != current.revision:
            difference = compare_revisions(envelope.review, current)
            st.caption('Literal changes from the selected revision to the current revision. Historical selection does not change the approval target.')
            st.dataframe([change.model_dump() for change in difference.changes], hide_index=True)
