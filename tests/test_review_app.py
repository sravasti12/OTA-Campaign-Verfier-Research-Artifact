"""Real Streamlit AppTest interactions over the local offline workflow."""
import json
from pathlib import Path
from typing import Any
import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).parents[1] / 'app' / 'streamlit_app.py'


def _app() -> AppTest:
    app = AppTest.from_file(str(APP), default_timeout=45).run()
    assert not app.exception
    return app


def _analyze(app: AppTest, example: str | None = None) -> AppTest:
    if example:
        app.selectbox(key='example_campaign').select(example).run()
        app.button(key='load_example').click().run()
    app.button(key='analyze').click().run(timeout=45)
    assert not app.exception
    return app


def test_app_initial_render_is_offline_and_does_not_analyze(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError('Rendering attempted an LLM call')
    monkeypatch.setattr('ota_verifier.llm.client.LLMClient.generate_json', forbidden)
    app = _app()
    assert app.title[0].value == 'OTA Campaign Verifier'
    assert 'active_run_id' not in app.session_state
    assert app.button(key='analyze').disabled is False


def test_full_fixture_review_screen_has_separate_results_and_no_approval() -> None:
    app = _analyze(_app())
    assert [tab.label for tab in app.tabs] == ['Requirements', 'Plan', 'Faults', 'Review']
    assert app.metric[0].value == 'Simulation violations'
    assert app.metric[1].value == 'Awaiting review'
    decisions = app.selectbox(key='decision_1').options
    assert 'Approve simulation proposal' not in decisions
    assert 'Review with findings' in decisions
    service = app.session_state['workflow_service']
    bundle = service.get(app.session_state['active_run_id'])
    assert len(bundle.snapshot.artifacts.simulation.cases) == 42
    original_calls = bundle.snapshot.artifacts.extraction.calls
    app.run()
    assert not app.exception
    assert service.get(bundle.run_id).snapshot.artifacts.extraction.calls == original_calls
    assert service.get(bundle.run_id).completed_nodes == bundle.completed_nodes


def test_source_edits_disable_review_without_reanalysis() -> None:
    app = _analyze(_app())
    service = app.session_state['workflow_service']
    bundle = service.get(app.session_state['active_run_id'])
    request = json.loads(app.text_area(key='request_json').value)
    request['documents'][0]['text'] += ' New source evidence.'
    app.text_area(key='request_json').set_value(json.dumps(request)).run()
    assert not app.exception
    assert app.metric[1].value == 'Draft changed'
    submit = next(button for button in app.button if button.label == 'Record decision')
    assert submit.disabled
    assert service.get(bundle.run_id).snapshot_hash == bundle.snapshot_hash
    assert service.get(bundle.run_id).completed_nodes == bundle.completed_nodes


def test_review_with_findings_does_not_change_simulation_verdict() -> None:
    app = _analyze(_app())
    app.text_input(key='reviewer_1').set_value('Portfolio reviewer')
    app.text_area(key='reason_1').set_value('Reviewed boot failures and blocked rollback paths')
    submit = next(button for button in app.button if button.label == 'Record decision')
    submit.click().run(timeout=45)
    assert not app.exception
    assert app.metric[0].value == 'Simulation violations'
    assert app.metric[1].value == 'Reviewed with findings'
    service = app.session_state['workflow_service']
    bundle = service.get(app.session_state['active_run_id'])
    assert len(bundle.decisions) == 1
    assert bundle.snapshot.artifacts.simulation.assessment == 'violations'
    app.run()
    assert len(service.get(bundle.run_id).decisions) == 1


def test_ambiguous_input_never_renders_a_plan_or_simulation() -> None:
    app = _analyze(_app(), 'Ambiguous requirement')
    assert app.metric[0].value == 'Extraction blocked'
    service = app.session_state['workflow_service']
    bundle = service.get(app.session_state['active_run_id'])
    assert bundle.snapshot.artifacts.planning is None
    assert bundle.snapshot.artifacts.simulation is None
    assert 'plan' not in bundle.completed_nodes


def test_no_update_approval_and_new_revision_invalidate_decision() -> None:
    app = _analyze(_app(), 'No updates (approval demo)')
    assert app.metric[0].value == 'Simulation passed'
    assert 'Approve simulation proposal' in app.selectbox(key='decision_1').options
    app.selectbox(key='decision_1').select('Approve simulation proposal')
    app.text_input(key='reviewer_1').set_value('Demo reviewer')
    app.text_area(key='reason_1').set_value('No updates are requested; zero fault cases are explicit')
    next(button for button in app.button if button.label == 'Record decision').click().run(timeout=45)
    assert not app.exception
    assert app.metric[1].value == 'Proposal approved'
    app = _analyze(app, 'Parallel update campaign')
    assert app.metric[0].value == 'Simulation violations'
    assert app.metric[1].value == 'Previous decision invalidated'
    service = app.session_state['workflow_service']
    bundle = service.get(app.session_state['active_run_id'])
    assert bundle.revision == 2
    assert bundle.current_decision is None
    assert len(bundle.decisions) == 1
