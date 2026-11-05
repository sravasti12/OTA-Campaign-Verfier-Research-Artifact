"""Offline UI checks for the optional durable workspace."""
from pathlib import Path
from streamlit.testing.v1 import AppTest
from ota_verifier.persistence.service import PersistentWorkflowService
from ota_verifier.workflow_examples import example_input, fixture_dependencies
from ota_verifier.workflow_models import WorkflowInput

APP = Path(__file__).parents[1] / 'app' / 'streamlit_app.py'


def test_open_existing_sqlite_run_without_reanalysis(tmp_path: Path) -> None:
    path = tmp_path / 'reviews.sqlite'
    request, case = example_input('no_updates')
    with PersistentWorkflowService(path) as service:
        original = service.start(WorkflowInput(request=request), fixture_dependencies(case), run_id='saved')
    app = AppTest.from_file(str(APP), default_timeout=45).run()
    app.text_input(key='database_path').set_value(str(path))
    app.button(key='open_database').click().run()
    assert not app.exception
    assert 'active_run_id' not in app.session_state
    app.button(key='open_saved_run').click().run()
    try:
        assert not app.exception
        assert app.metric[0].value == 'Simulation passed'
        assert app.session_state['workflow_service'].get('saved').snapshot_hash == original.snapshot_hash
        app.text_input(key='reviewer_1').set_value('Durable reviewer')
        app.text_area(key='reason_1').set_value('Reviewed no-update simulation')
        next(button for button in app.button if button.label == 'Record decision').click().run()
        assert not app.exception
        assert app.metric[1].value == 'Proposal approved'
    finally:
        app.session_state['workflow_service'].close()
    with PersistentWorkflowService(path) as service:
        assert service.get('saved').review_state == 'approved'


def test_pending_saved_run_can_resume_from_screen(tmp_path: Path) -> None:
    path = tmp_path / 'reviews.sqlite'
    request, case = example_input('no_updates')
    with PersistentWorkflowService(path) as service:
        service.begin(WorkflowInput(request=request), fixture_dependencies(case), run_id='pending')
    app = AppTest.from_file(str(APP), default_timeout=45).run()
    app.text_input(key='database_path').set_value(str(path))
    app.button(key='open_database').click().run()
    app.button(key='open_saved_run').click().run()
    try:
        assert not app.exception
        assert app.button(key='resume_analysis').disabled is False
        app.button(key='resume_analysis').click().run()
        assert not app.exception
        assert app.metric[0].value == 'Simulation passed'
    finally:
        app.session_state['workflow_service'].close()
