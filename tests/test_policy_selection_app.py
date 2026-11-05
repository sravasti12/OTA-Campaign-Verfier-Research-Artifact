"""Policy selection is visible, draft-bound, and requires fresh human review."""
from pathlib import Path
from streamlit.testing.v1 import AppTest

APP = Path(__file__).parents[1] / 'app' / 'streamlit_app.py'


def test_select_guarded_policy_review_and_switch_back_to_baseline() -> None:
    app = AppTest.from_file(str(APP), default_timeout=45).run()
    app.selectbox(key='example_campaign').select('Authorized rollback comparison').run()
    app.button(key='load_example').click().run()
    app.selectbox(key='selected_policy').select('Guarded trial boot policy').run()
    app.button(key='analyze').click().run(timeout=45)
    assert not app.exception
    assert app.metric[0].label == 'Selected policy: guarded-trial-v1'
    assert app.metric[0].value == 'Simulation passed'
    assert 'Approve simulation proposal' in app.selectbox(key='decision_1').options
    service = app.session_state['workflow_service']
    first = service.get(app.session_state['active_run_id'])
    assert first.snapshot.artifacts.simulation.assessment == 'violations'
    assert first.snapshot.artifacts.comparison.guarded.assessment == 'passed'
    app.text_input(key='reviewer_1').set_value('Policy reviewer')
    app.text_area(key='reason_1').set_value('Guarded policy evidence reviewed, with baseline violations retained')
    next(button for button in app.button if button.label == 'Record decision').click().run(timeout=45)
    assert not app.exception
    assert app.metric[1].value == 'Proposal approved'
    app.selectbox(key='selected_policy').select('Baseline policy').run()
    assert app.metric[1].value == 'Draft changed'
    assert service.get(first.run_id).snapshot_hash == first.snapshot_hash
    app.button(key='analyze').click().run(timeout=45)
    assert not app.exception
    assert app.metric[0].label == 'Selected policy: baseline-v1'
    assert app.metric[0].value == 'Simulation violations'
    assert app.metric[1].value == 'Previous decision invalidated'
    assert 'Approve simulation proposal' not in app.selectbox(key='decision_2').options


def test_guarded_options_change_disables_pending_review() -> None:
    app = AppTest.from_file(str(APP), default_timeout=45).run()
    app.selectbox(key='example_campaign').select('Authorized rollback comparison').run()
    app.button(key='load_example').click().run()
    app.selectbox(key='selected_policy').select('Guarded trial boot policy').run()
    assert app.number_input(key='trial_attempts').disabled is False
    app.button(key='analyze').click().run(timeout=45)
    assert not app.exception
    app.number_input(key='trial_attempts').set_value(1).run()
    assert not app.exception
    assert app.metric[1].value == 'Draft changed'
    assert next(button for button in app.button if button.label == 'Record decision').disabled
