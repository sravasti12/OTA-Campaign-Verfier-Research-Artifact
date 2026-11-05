"""The public deployment runs real bounded analysis without provider or disk access."""
from pathlib import Path
from typing import Any
import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).parents[1] / 'app/public_demo.py'


def test_public_demo_never_opens_host_storage_or_provider_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError('Public fixture demo attempted provider or filesystem access')
    monkeypatch.setattr('ota_verifier.llm.client.ClientSettings.from_env', forbidden)
    monkeypatch.setattr('ota_verifier.llm.client.LLMClient.generate_json', forbidden)
    monkeypatch.setattr('ota_verifier.persistence.service.PersistentWorkflowService.__init__', forbidden)
    app = AppTest.from_file(str(APP), default_timeout=45).run()
    assert not app.exception
    assert not app.text_area
    assert not app.text_input
    assert 'active_run_id' not in app.session_state
    app.button(key='public_analyze').click().run()
    assert not app.exception
    assert app.metric[0].value == 'Simulation violations'
    assert app.metric[1].value == 'Awaiting review'
    assert not any(button.label == 'Open SQLite workspace' for button in app.button)


def test_public_guarded_policy_and_switching_examples_keep_review_scope() -> None:
    app = AppTest.from_file(str(APP), default_timeout=45).run()
    app.selectbox(key='public_example').select('Authorized rollback comparison').run()
    app.selectbox(key='public_policy').select('Guarded trial boot policy').run()
    app.button(key='public_analyze').click().run()
    assert not app.exception
    assert app.metric[0].value == 'Simulation passed'
    service = app.session_state['workflow_service']
    first = service.get(app.session_state['active_run_id'])
    assert first.snapshot.artifacts.simulation.assessment == 'violations'
    assert first.snapshot.artifacts.comparison.guarded.assessment == 'passed'
    assert first.current_decision is None
    app.selectbox(key='public_example').select('Impossible intermediate versions').run()
    assert app.metric[1].value == 'Draft changed'
    assert next(button for button in app.button if button.label == 'Record decision').disabled
    app.button(key='public_analyze').click().run()
    assert not app.exception
    assert app.metric[0].value == 'Planning infeasible'
    assert service.get(first.run_id).revision == 2


def test_public_sessions_are_isolated_and_analysis_budget_is_bounded() -> None:
    first = AppTest.from_file(str(APP), default_timeout=45).run()
    second = AppTest.from_file(str(APP), default_timeout=45).run()
    assert first.session_state['workflow_service'] is not second.session_state['workflow_service']
    first.session_state['public_analysis_count'] = 8
    first.run()
    assert first.button(key='public_analyze').disabled
    assert not second.button(key='public_analyze').disabled
    assert first.slider(key='public_parallel').min == 1
    assert first.slider(key='public_parallel').max == 3
