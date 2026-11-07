"""Mocked provider contract tests: no real provider, model download, or API key."""
from io import BytesIO
import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
import pytest
from pydantic import SecretStr
from ota_verifier.llm.client import (ClientSettings, HttpRequest, LLMClient, LLMError,
                                    USER_AGENT, http_transport, provider_schema)
from ota_verifier.llm.evidence import content_hash
from ota_verifier.llm.models import ExtractionDraft


def _envelope(provider: str, raw: str = '{}') -> dict[str, Any]:
    if provider == 'ollama':
        return {'message': {'content': raw}, 'done': True, 'done_reason': 'stop'}
    if provider == 'gemini':
        return {'candidates': [{'content': {'parts': [{'text': raw}]}, 'finishReason': 'STOP'}]}
    return {'choices': [{'message': {'content': raw}, 'finish_reason': 'stop'}]}


def _generate(client: LLMClient) -> Any:
    return client.generate_json(purpose='extraction', system_prompt='Extract only.', user_prompt='Synthetic notes.',
        schema=ExtractionDraft.model_json_schema(), prompt_version='test-v1')


@pytest.mark.parametrize('provider', ['ollama', 'gemini', 'groq'])
def test_provider_request_and_credential_free_audit(provider: str) -> None:
    requests: list[HttpRequest] = []
    secret = 'test-only-not-a-real-credential'

    def transport(request: HttpRequest) -> dict[str, Any]:
        requests.append(request)
        return _envelope(provider)

    settings = ClientSettings(provider=provider, model='test-model', api_key=SecretStr(secret))
    record = _generate(LLMClient(settings, transport))
    request = requests[0]
    assert secret not in record.model_dump_json()
    assert secret not in settings.model_dump_json()
    assert secret not in repr(settings)
    assert secret not in repr(request)
    assert record.request_hash == content_hash(record.request_json)
    assert record.origin == 'live'  # Transport is mocked; adapter's actual path is exercised.
    assert request.timeout_seconds == 60
    assert request.headers['User-Agent'] == USER_AGENT
    if provider == 'ollama':
        assert request.headers['Authorization'] == 'Bearer ' + secret
        assert request.url == 'http://localhost:11434/api/chat'
        assert request.body['stream'] is False
        assert isinstance(request.body['format'], dict)
    elif provider == 'gemini':
        assert request.headers['x-goog-api-key'] == secret
        assert secret not in request.url
        assert request.body['generationConfig']['responseMimeType'] == 'application/json'
        assert 'responseJsonSchema' in request.body['generationConfig']
    else:
        assert request.headers['Authorization'] == 'Bearer ' + secret
        assert request.body['response_format']['json_schema']['strict'] is True


@pytest.mark.parametrize('provider', ['ollama', 'gemini', 'groq'])
def test_application_identity_and_auth_reach_http_request(provider: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock only network I/O: the real adapter/transport must preserve identity and credentials."""
    secret = 'test-only-header-secret'
    seen: list[Any] = []

    def offline_urlopen(request: Any, *, timeout: float) -> BytesIO:
        seen.append(request)
        assert request.get_header('User-agent') == 'OTA-Campaign-Verifier-Evaluation/0.1.0'
        assert request.get_header('Content-type') == 'application/json'
        if provider == 'gemini':
            assert request.get_header('X-goog-api-key') == secret
            assert request.get_header('Authorization') is None
        else:
            assert request.get_header('Authorization') == 'Bearer ' + secret
            assert request.get_header('X-goog-api-key') is None
        return BytesIO(json.dumps(_envelope(provider)).encode('utf-8'))

    monkeypatch.setattr('ota_verifier.llm.client.urlopen', offline_urlopen)
    client = LLMClient(ClientSettings(provider=provider, model='test-model', api_key=SecretStr(secret)))
    record = _generate(client)
    assert len(seen) == 1
    assert secret not in record.model_dump_json()


@pytest.mark.parametrize('provider', ['ollama', 'gemini', 'groq'])
def test_explicit_json_mode(provider: str) -> None:
    seen: list[HttpRequest] = []

    def transport(request: HttpRequest) -> dict[str, Any]:
        seen.append(request)
        return _envelope(provider)

    _generate(LLMClient(ClientSettings(provider=provider, model='test-model', api_key=SecretStr('test-key'), schema_mode='json'), transport))
    request = seen[0]
    assert 'schema' in (request.body.get('messages', [{}])[0].get('content', '') or
                        request.body.get('systemInstruction', {}).get('parts', [{}])[0].get('text', '')).lower()
    if provider == 'ollama':
        assert request.body['format'] == 'json'
    elif provider == 'gemini':
        assert 'responseJsonSchema' not in request.body['generationConfig']
    else:
        assert request.body['response_format'] == {'type': 'json_object'}


@pytest.mark.parametrize('provider', ['ollama', 'gemini', 'groq'])
def test_truncation_retains_response_but_cannot_pass(provider: str) -> None:
    response = _envelope(provider)
    if provider == 'ollama':
        response['done_reason'] = 'length'
    elif provider == 'gemini':
        response['candidates'][0]['finishReason'] = 'MAX_TOKENS'
    else:
        response['choices'][0]['finish_reason'] = 'length'
    with pytest.raises(LLMError, match='truncated') as caught:
        _generate(LLMClient(ClientSettings(provider=provider, model='test-model', api_key=SecretStr('test-key')), lambda request: response))
    assert caught.value.record is not None
    assert caught.value.record.response_text == '{}'


@pytest.mark.parametrize('response', [{}, {'choices': []}, {'choices': [{'message': {'refusal': 'No'}, 'finish_reason': 'stop'}]}])
def test_bad_envelope_and_refusal_fail_closed(response: dict[str, Any]) -> None:
    with pytest.raises(LLMError):
        _generate(LLMClient(ClientSettings(provider='groq', model='test-model', api_key=SecretStr('test-key')), lambda request: response))


def test_env_precedence_verifier_model_no_mutation_or_interpolation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = tmp_path / '.env'
    env.write_text('LLM_PROVIDER=groq\nLLM_MODEL=file-model\nLLM_VERIFIER_MODEL=review-model\nGROQ_API_KEY=${UNEXPANDED}\n', encoding='utf-8')
    monkeypatch.delenv('LLM_MODEL', raising=False)
    settings = ClientSettings.from_env(env_file=env, environ={'LLM_MODEL': 'override-model'})
    review = ClientSettings.from_env('verification', env_file=env, environ={})
    assert settings.model == 'override-model'
    assert settings.api_key.get_secret_value() == '${UNEXPANDED}'
    assert review.model == 'review-model'
    import os
    assert 'LLM_MODEL' not in os.environ


@pytest.mark.parametrize('values', [{}, {'LLM_PROVIDER': 'fixture', 'LLM_MODEL': 'x'},
    {'LLM_PROVIDER': 'gemini', 'LLM_MODEL': 'x'}, {'LLM_MODEL': 'x', 'LLM_TIMEOUT_SECONDS': '-1'}])
def test_configuration_errors_are_explicit(values: dict[str, str]) -> None:
    with pytest.raises(LLMError):
        ClientSettings.from_env(env_file=None, environ=values)


def test_schema_lowering_preserves_local_schema_and_requires_objects() -> None:
    original = ExtractionDraft.model_json_schema()
    before = json.dumps(original, sort_keys=True)
    lowered = provider_schema(original)
    assert json.dumps(original, sort_keys=True) == before
    encoded = json.dumps(lowered)
    assert 'discriminator' not in encoded
    assert 'oneOf' not in encoded
    assert 'anyOf' in encoded
    assert lowered['additionalProperties'] is False
    assert set(lowered['required']) == set(lowered['properties'])


@pytest.mark.parametrize('url', ['file:///secret', 'http://user:secret@localhost:11434', 'http://localhost:11434?key=secret'])
def test_ollama_url_cannot_embed_credentials(url: str) -> None:
    with pytest.raises(LLMError, match='base URL'):
        _generate(LLMClient(ClientSettings(provider='ollama', model='test-model', ollama_base_url=url), lambda request: {}))


@pytest.mark.parametrize('error', [HTTPError('https://example.invalid/key-secret', 429, 'key-secret', {}, None), URLError('key-secret'), TimeoutError('key-secret')])
def test_transport_errors_do_not_leak_credentials(error: Exception, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: Any, **kwargs: Any) -> None:
        raise error
    monkeypatch.setattr('ota_verifier.llm.client.urlopen', fail)
    with pytest.raises(LLMError) as caught:
        http_transport(HttpRequest('https://example.invalid', {}, 1, {}))
    assert 'key-secret' not in str(caught.value)


def test_provider_response_size_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('ota_verifier.llm.client.MAX_RESPONSE_BYTES', 10)
    monkeypatch.setattr('ota_verifier.llm.client.urlopen', lambda *args, **kwargs: BytesIO(b' ' * 11))
    with pytest.raises(LLMError, match='size limit'):
        http_transport(HttpRequest('https://example.invalid', {}, 1, {}))
