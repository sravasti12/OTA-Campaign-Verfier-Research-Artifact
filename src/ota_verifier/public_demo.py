"""Bounded fixture-only public demo; no filesystem library or provider configuration."""
import streamlit as st
from .boot_models import GuardedOptions
from .boot_review import render_boot_comparison
from .graph import WorkflowService
from .models import PlanningOptions
from .review_app import EXAMPLE_LABELS, _requirements, _plan, _faults, _review
from .review_views import ANALYSIS_LABELS, REVIEW_LABELS, inputs_current
from .workflow_examples import example_input, fixture_dependencies
from .workflow_models import PolicySelection, WorkflowInput

MAX_DEMO_ANALYSES = 8


def main() -> None:
    """Run real deterministic analysis on synthetic examples in an isolated session."""
    st.set_page_config(page_title='OTA Campaign Verifier — Public Demo', page_icon='🚗', layout='wide')
    st.title('OTA Campaign Verifier')
    st.caption('PUBLIC SIMULATION DEMO / Synthetic fixtures / No live model calls')
    st.info('This free demo uses synthetic source documents and scripted extraction responses. '
        'Plans, faults, recovery, and invariants run in deterministic code. '
        'Review records are self-reported and session-only; nothing is deployed to a vehicle.')
    if '_public_demo_initialized' not in st.session_state:
        st.session_state.workflow_service = WorkflowService()
        st.session_state.pop('active_run_id', None)
        st.session_state._public_demo_initialized = True
        st.session_state.public_analysis_count = 0
    with st.sidebar:
        st.subheader('Explore a synthetic campaign')
        label = st.selectbox('Example campaign', list(EXAMPLE_LABELS), key='public_example')
        policy = st.selectbox('Policy to review', ['Baseline policy', 'Guarded trial boot policy'], key='public_policy')
        parallel = st.slider('Concurrent write limit', min_value=1, max_value=3, value=2, key='public_parallel')
        st.caption('No uploads, editable server paths, provider credentials, or persistent workspaces are exposed.')
    name = EXAMPLE_LABELS[label]
    request, case = example_input(name)
    incoming = WorkflowInput(request=request, planning_options=PlanningOptions(max_parallel=parallel), mode='fixture',
        selected_policy=PolicySelection(id='guarded-trial-v1', guarded_options=GuardedOptions(max_trial_attempts=2))
            if policy == 'Guarded trial boot policy' else PolicySelection(id='baseline-v1'))
    with st.expander('Synthetic source documents and inventory'):
        st.json(request.model_dump(mode='json'), expanded=False)
    exhausted = st.session_state.public_analysis_count >= MAX_DEMO_ANALYSES
    if exhausted:
        st.info('This session has reached its eight-analysis demo limit. Start a new browser session to continue.')
    analyze = st.button('Analyze revision', key='public_analyze', type='primary', disabled=exhausted)
    service = st.session_state.workflow_service
    if analyze:
        try:
            with st.spinner('Planning and stress-testing the simulation…'):
                if 'active_run_id' in st.session_state:
                    bundle = service.revise(st.session_state.active_run_id, incoming, fixture_dependencies(case))
                else:
                    bundle = service.start(incoming, fixture_dependencies(case))
                    st.session_state.active_run_id = bundle.run_id
                st.session_state.public_analysis_count += 1
        except ValueError:
            st.error('The example could not complete. Start a fresh session and try again.')
    if 'active_run_id' not in st.session_state:
        st.write('Choose an example, then select **Analyze revision**. '
            'Try the intermediate-version conflict and authorized rollback comparison.')
        return
    bundle = service.get(st.session_state.active_run_id)
    current = inputs_current(bundle, incoming)
    columns = st.columns(3)
    columns[0].metric('Selected policy: ' + bundle.snapshot.artifacts.input.selected_policy.id,
        ANALYSIS_LABELS[bundle.snapshot.artifacts.status])
    columns[1].metric('Human decision', REVIEW_LABELS[bundle.review_state] if current else 'Draft changed')
    columns[2].metric('Revision', bundle.revision)
    if not current:
        st.warning('The selected example, policy, or write limit changed. Analyze a new revision before reviewing.')
    st.download_button('Download simulation evidence', bundle.model_dump_json(indent=2),
        file_name=f'ota-simulation-{bundle.run_id}-r{bundle.revision}.json', mime='application/json')
    requirements, plan, faults, review = st.tabs(['Requirements', 'Plan', 'Faults', 'Review'])
    with requirements:
        _requirements(bundle)
    with plan:
        _plan(bundle)
    with faults:
        render_boot_comparison(bundle)
        _faults(bundle)
    with review:
        _review(bundle, current)
