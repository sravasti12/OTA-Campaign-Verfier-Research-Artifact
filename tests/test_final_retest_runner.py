"""Offline budget/stop controls for the final runner; never provider accuracy evidence."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
import urllib.request
import pytest
pytestmark = pytest.mark.usefixtures('offline_groq_settings')
from ota_verifier.llm.client import LLMError

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('final_retest', ROOT / 'eval/live_extraction/final_retest.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


@pytest.mark.parametrize('failure', [False, True])
def test_fixed_request_ceiling_and_no_retry_with_mock_http(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: bool) -> None:
    """Five two-stage cases cap at ten calls; repeated failures stop after two independent calls."""
    frozen = ROOT / 'eval/live_extraction/real-retest-v2'
    for name in ('dataset.json', 'manifest.json', 'approval.json'):
        (tmp_path / name).write_bytes((frozen / name).read_bytes())
    clock = [0.0]
    sent = []
    monkeypatch.setattr(runner, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(runner, 'sleep', lambda duration: clock.__setitem__(0, clock[0] + duration))
    monkeypatch.setattr(urllib.request, '_opener', None)
    cases = json.loads((tmp_path / 'dataset.json').read_text(encoding='utf-8'))['cases']
    def transport(request: Any) -> dict[str, Any]:
        sent.append(request.body)
        assert request.body['max_completion_tokens'] == 4096
        response = SimpleNamespace(code=400 if failure else 200, headers={
            'x-ratelimit-limit-tokens': '8000', 'x-ratelimit-remaining-tokens': '8000',
            'x-ratelimit-remaining-requests': '999'}, read=lambda n: b'{"error":{"code":"offline_failure"}}')
        response.msg = 'Offline response'
        response.info = lambda: response.headers
        for handler in urllib.request._opener.handlers:
            if type(handler).__name__ == 'Observe':
                if failure:
                    # Observe records the real HTTP-shaped failure; its parent raises via opener.error.
                    try:
                        handler.http_response(None, response)
                    except (AttributeError, TypeError):
                        pass
                else:
                    handler.http_response(None, response)
        if failure:
            raise LLMError('Offline HTTP400; no network')
        user = json.loads(request.body['messages'][1]['content'])
        if 'extraction' in user:
            draft = user['extraction']
            content = {'faithful': True, 'reviewed_constraint_ids': [entry['constraint']['id'] for entry in draft['constraints']],
                       'reviewed_document_ids': [doc['id'] for doc in user['documents']], 'issues': []}
        else:
            row = next(row for row in cases if row['id'] == user['documents'][0]['id'])
            # Deliberately remove issues for the worst-case ten-request path; not gold/live scoring.
            content = {'constraints': row['proposed_draft']['constraints'], 'issues': []}
        return {'model': 'openai/gpt-oss-20b', 'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2},
                'choices': [{'message': {'content': json.dumps(content)}, 'finish_reason': 'stop'}]}
    monkeypatch.setattr(runner, 'http_transport', transport)
    runner.execute(tmp_path)
    summary = json.loads((tmp_path / 'summary.json').read_text())
    assert len(sent) == (2 if failure else 10)
    assert summary['http_requests_sent'] == len(sent) and summary['automatic_retries'] == 0
    assert summary['estimated_tokens_reserved'] <= 63997
    assert summary['not_run_cases'] == (3 if failure else 0)
    with pytest.raises(AssertionError, match='restart'):
        runner.execute(tmp_path)
    assert len(sent) == (2 if failure else 10)
