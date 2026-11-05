"""Example loading changes the draft atomically without changing analyzed evidence."""
import json
from typing import Any
import pytest
from ota_verifier.review_app import EXAMPLE_LABELS
from ota_verifier.workflow_examples import example_input
from test_review_app import _app, _analyze


def test_switch_examples_replaces_entire_request_and_survives_reruns() -> None:
    app = _app()
    for label, name in (*EXAMPLE_LABELS.items(), ('Parallel update campaign', 'clear')):
        app.selectbox(key='example_campaign').select(label).run()
        app.button(key='load_example').click().run()
        assert not app.exception
        expected, _ = example_input(name)
        assert json.loads(app.text_area(key='request_json').value) == expected.model_dump(mode='json')
        assert app.session_state['fixture_example'] == name
        app.run()
        assert not app.exception
        assert json.loads(app.text_area(key='request_json').value) == expected.model_dump(mode='json')


def test_load_confirms_draft_update_after_analyzed_result_exists() -> None:
    app = _analyze(_app())
    service = app.session_state['workflow_service']
    original = service.get(app.session_state['active_run_id'])
    app.selectbox(key='example_campaign').select('Impossible intermediate versions').run()
    app.button(key='load_example').click().run()
    assert not app.exception
    assert any('Loaded example: Impossible intermediate versions' in message.value for message in app.success)
    editor = next(item for item in app.expander if item.label == 'Edit source documents and inventory')
    assert editor.proto.expanded is True
    assert app.metric[1].value == 'Draft changed'
    assert service.get(original.run_id) == original
    assert next(button for button in app.button if button.label == 'Record decision').disabled
    app.button(key='analyze').click().run(timeout=45)
    assert not app.exception
    updated = service.get(original.run_id)
    assert updated.revision == original.revision + 1
    assert updated.snapshot.artifacts.status == 'planning_infeasible'


def test_load_restores_same_example_over_pending_editor_edits_without_a_model_call(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError('Loading an example must not call a model')
    monkeypatch.setattr('ota_verifier.llm.client.LLMClient.generate_json', forbidden)
    monkeypatch.setattr('ota_verifier.llm.client.FixtureClient.generate_json', forbidden)
    app = _app()
    app.text_area(key='request_json').set_value('{ pending invalid draft')
    app.button(key='load_example').click().run()
    assert not app.exception
    expected, _ = example_input('clear')
    assert json.loads(app.text_area(key='request_json').value) == expected.model_dump(mode='json')
    assert 'active_run_id' not in app.session_state
    assert not app.error


def test_selection_requires_load_and_loading_preserves_explicit_analysis_options() -> None:
    app = _app()
    original = app.text_area(key='request_json').value
    app.radio(key='response_source').set_value('Configured provider').run()
    app.number_input(key='parallel').set_value(3).run()
    app.checkbox(key='deadline_on').check().run()
    app.number_input(key='deadline_minutes').set_value(1.5).run()
    app.selectbox(key='selected_policy').select('Guarded trial boot policy').run()
    app.checkbox(key='compare_boot').check().run()
    app.number_input(key='trial_attempts').set_value(1).run()
    app.number_input(key='planner_timeout').set_value(12345).run()
    app.number_input(key='recovery_limit').set_value(17).run()
    app.selectbox(key='example_campaign').select('Authorized rollback comparison').run()
    assert app.text_area(key='request_json').value == original
    app.button(key='load_example').click().run()
    assert not app.exception
    expected, _ = example_input('authorized_rollback')
    assert json.loads(app.text_area(key='request_json').value) == expected.model_dump(mode='json')
    assert app.radio(key='response_source').value == 'Configured provider'
    assert app.number_input(key='parallel').value == 3
    assert app.checkbox(key='deadline_on').value is True
    assert app.number_input(key='deadline_minutes').value == 1.5
    assert app.selectbox(key='selected_policy').value == 'Guarded trial boot policy'
    assert app.checkbox(key='compare_boot').value is True
    assert app.number_input(key='trial_attempts').value == 1
    assert app.number_input(key='planner_timeout').value == 12345
    assert app.number_input(key='recovery_limit').value == 17
    assert 'active_run_id' not in app.session_state
