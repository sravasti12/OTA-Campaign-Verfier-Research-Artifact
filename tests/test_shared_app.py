"""Mocked OIDC adapter tests over the real shared Streamlit workspace."""
import json
from pathlib import Path
from time import time
from typing import Any
import pytest
from streamlit.testing.v1 import AppTest
from ota_verifier.access import AccessPolicy, Account
from ota_verifier.persistence.operations import migrate_workspace
from ota_verifier.persistence.service import PersistentWorkflowService
from ota_verifier.workflow_examples import example_input, fixture_dependencies
from ota_verifier.workflow_models import WorkflowInput

APP = Path(__file__).parents[1] / 'app' / 'streamlit_app.py'


def configure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, roles: tuple[str, ...]) -> tuple[Path, Path]:
    """Provide a protected host policy and mocked verified Streamlit claims."""
    database = tmp_path / 'shared.sqlite'
    with PersistentWorkflowService(database):
        pass
    migrate_workspace(database, tmp_path / 'before.sqlite')
    request, case = example_input('no_updates')
    with PersistentWorkflowService(database) as service:
        service.start(WorkflowInput(request=request), fixture_dependencies(case), run_id='saved')
    rules = AccessPolicy(database_path=str(database), accounts=(Account(issuer='https://id.example', subject='reviewer-1', roles=roles),))
    config = tmp_path / 'access.json'
    config.write_text(rules.model_dump_json(), encoding='utf-8')
    monkeypatch.setenv('OTA_ACCESS_MODE', 'shared')
    monkeypatch.setenv('OTA_ACCESS_CONFIG', str(config))
    claims = {'iss': 'https://id.example', 'sub': 'reviewer-1', 'iat': int(time()) - 1, 'exp': int(time()) + 3600}
    monkeypatch.setattr('ota_verifier.shared_review._verified_claims', lambda: (claims, True))
    return database, config


def test_anonymous_shared_page_does_not_show_sources_or_library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    configure(tmp_path, monkeypatch, ('reader',))
    monkeypatch.setattr('ota_verifier.shared_review._verified_claims', lambda: ({}, False))
    app = AppTest.from_file(str(APP), default_timeout=45).run()
    assert not app.exception
    assert app.button(key='sign_in')
    assert len(app.text_area) == 0
    assert 'workflow_service' not in app.session_state


def test_reader_has_no_analysis_or_review_and_cannot_switch_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    configure(tmp_path, monkeypatch, ('reader',))
    app = AppTest.from_file(str(APP), default_timeout=45).run()
    try:
        assert not app.exception
        assert app.button(key='open_database').disabled
        assert app.text_input(key='database_path').disabled
        assert app.button(key='analyze').disabled
        app.button(key='open_saved_run').click().run()
        assert not app.exception
        assert app.metric[0].value == 'Simulation passed'
        assert next(button for button in app.button if button.label == 'Record decision').disabled
        assert not any(item.key == 'reviewer_1' for item in app.text_input)
    finally:
        app.session_state['workflow_service'].close()


def test_reviewer_can_record_verified_decision_without_analyst_role(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database, _ = configure(tmp_path, monkeypatch, ('reviewer',))
    app = AppTest.from_file(str(APP), default_timeout=45).run()
    try:
        app.button(key='open_saved_run').click().run()
        assert not app.exception
        assert app.button(key='analyze').disabled
        app.text_area(key='reason_1').set_value('Verified reviewer examined zero-update simulation')
        next(button for button in app.button if button.label == 'Record decision').click().run()
        assert not app.exception
        assert app.metric[1].value == 'Proposal approved'
    finally:
        app.session_state['workflow_service'].close()
    with PersistentWorkflowService(database) as service:
        reviewer = json.loads(service.get('saved').current_decision.submission.reviewer)
        assert reviewer == {'issuer': 'https://id.example', 'subject': 'reviewer-1'}
        with service.store.connect() as connection:
            assert connection.execute('SELECT COUNT(*) FROM ota_review_auth').fetchone()[0] == 1


def test_revoked_account_is_denied_on_next_render(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, config = configure(tmp_path, monkeypatch, ('reader',))
    app = AppTest.from_file(str(APP), default_timeout=45).run()
    service = app.session_state['workflow_service']
    try:
        app.button(key='open_saved_run').click().run()
        assert app.metric
        rules = json.loads(config.read_text())
        rules['accounts'][0]['enabled'] = False
        config.write_text(json.dumps(rules), encoding='utf-8')
        app.run()
        assert not app.exception
        assert app.error
        assert len(app.text_area) == len(app.metric) == 0
    finally:
        service.close()


def test_bad_mode_never_falls_back_to_local(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('OTA_ACCESS_MODE', 'shaerd')
    app = AppTest.from_file(str(APP), default_timeout=45).run()
    assert not app.exception
    assert app.error
    assert 'workflow_service' not in app.session_state
