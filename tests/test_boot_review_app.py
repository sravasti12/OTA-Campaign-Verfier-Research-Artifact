"""Real Streamlit interactions for opt-in policy comparison and honest result labels."""
import pytest
from test_review_app import _app, _analyze
from ota_verifier.boot_review import guarded_vehicle_rows


def test_comparison_ui_keeps_baseline_and_guarded_assessments_separate() -> None:
    app = _app()
    app.checkbox(key='compare_boot').check().run()
    app = _analyze(app, 'Authorized rollback comparison')
    assert not app.exception
    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics['Baseline analysis'] == 'Simulation violations'
    assert metrics['Baseline policy'] == 'violations'
    assert metrics['Guarded policy'] == 'passed'
    assert metrics['Improved'] == '3'
    assert 'Approve simulation proposal' not in app.selectbox(key='decision_1').options
    service = app.session_state['workflow_service']
    bundle = service.get(app.session_state['active_run_id'])
    assert len(bundle.snapshot.artifacts.comparison.guarded_only_indices) == 6
    # First ECU's boot failure is the 14th shared case.
    app.selectbox(key='paired_case_1').select(13).run()
    assert not app.exception
    case = bundle.snapshot.artifacts.comparison.guarded.cases[13]
    event = next(event for event in case.trace if event.stage == 'fault')
    rows = guarded_vehicle_rows(event.snapshot)
    failed_ecu = next(row for row in rows if row['ECU'] == case.fault.ecu_id)
    assert failed_ecu['Running version'] == 'unavailable'
    assert failed_ecu['Last effective version'] == '1'
    assert failed_ecu['B integrity'] is True
    assert failed_ecu['B boot health'] == 'failed'


def test_comparison_option_edits_require_explicit_reanalysis() -> None:
    app = _analyze(_app())
    service = app.session_state['workflow_service']
    old = service.get(app.session_state['active_run_id'])
    app.checkbox(key='compare_boot').check().run()
    assert app.metric[1].value == 'Draft changed'
    assert service.get(old.run_id).snapshot.artifacts.comparison is None
    assert service.get(old.run_id).completed_nodes == old.completed_nodes
    app.button(key='analyze').click().run(timeout=45)
    assert not app.exception
    current = service.get(old.run_id)
    assert current.revision == 2
    assert current.snapshot.artifacts.comparison is not None


def test_live_workspace_upgrade_preserves_previous_review_data() -> None:
    from types import SimpleNamespace
    from ota_verifier.graph import WorkflowService
    from ota_verifier.workflow_examples import example_input, fixture_dependencies
    from ota_verifier.workflow_models import ReviewBundle, WorkflowInput
    request, case = example_input('no_updates')
    previous_service = WorkflowService()
    previous_bundle = previous_service.start(WorkflowInput(request=request), fixture_dependencies(case))

    class PreviousWorkspace:
        graph = SimpleNamespace(nodes={'extract': None, 'human_review': None})

        def get(self, run_id: str) -> ReviewBundle:
            return previous_service.get(run_id)

    old = PreviousWorkspace()
    app = _app()
    app.session_state['workflow_service'] = old
    app.session_state['active_run_id'] = previous_bundle.run_id
    app.run()
    assert not app.exception
    app.button(key='upgrade_workspace').click().run()
    assert not app.exception
    assert app.session_state['previous_workspaces'][0] is old
    assert previous_service.get(previous_bundle.run_id).snapshot_hash == previous_bundle.snapshot_hash
    assert 'active_run_id' not in app.session_state
