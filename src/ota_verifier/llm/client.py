"""One provider boundary: Ollama, Gemini, or Groq; never used by the core."""
from collections.abc import Mapping
from dataclasses import dataclass, field
import json
import logging
import os
from pathlib import Path
from typing import Any, Literal, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from .evidence import canonical_json, content_hash
from .models import CallRecord, Purpose

logger = logging.getLogger(__name__)
Provider = Literal['ollama', 'gemini', 'groq']
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
USER_AGENT = 'OTA-Campaign-Verifier-Evaluation/0.1.0'


class LLMError(RuntimeError):
    """A sanitized provider/configuration failure, optionally with response evidence."""

    def __init__(self, message: str, record: CallRecord | None = None) -> None:
        super().__init__(message)
        self.record = record


class ClientSettings(BaseModel):
    """Explicit provider settings; credentials are excluded from serialization."""
    model_config = ConfigDict(extra='forbid', frozen=True)
    provider: Provider
    model: str = Field(min_length=1, pattern=r'^[a-zA-Z0-9_./:-]+$')
    api_key: SecretStr | None = Field(default=None, exclude=True, repr=False)
    ollama_base_url: str = 'http://localhost:11434'
    timeout_seconds: float = Field(default=60, gt=0, le=600, allow_inf_nan=False)
    max_tokens: int = Field(default=8192, gt=0, le=131072)
    schema_mode: Literal['schema', 'json'] = 'schema'

    @classmethod
    def from_env(cls, purpose: Purpose = 'extraction', env_file: Path | None = Path('.env'),
                 environ: Mapping[str, str] | None = None) -> 'ClientSettings':
        """Load .env without interpolation or process mutation; environment wins."""
        from dotenv import dotenv_values
        values = dict(dotenv_values(env_file, interpolate=False, encoding='utf-8-sig')) if env_file is not None and env_file.is_file() else {}
        values.update(os.environ if environ is None else environ)
        provider = values.get('LLM_PROVIDER', 'ollama')
        role_model = {'extraction': 'LLM_MODEL', 'verification': 'LLM_VERIFIER_MODEL', 'explanation': 'LLM_EXPLAINER_MODEL'}[purpose]
        model = values.get(role_model) or values.get('LLM_MODEL')
        if provider not in ('ollama', 'gemini', 'groq'):
            raise LLMError('LLM_PROVIDER must be ollama, gemini, or groq')
        if not model:
            raise LLMError('Set LLM_MODEL to an installed or provider-supported model')
        key = values.get({'ollama': 'OLLAMA_API_KEY', 'gemini': 'GEMINI_API_KEY', 'groq': 'GROQ_API_KEY'}[provider])
        if provider != 'ollama' and not key:
            raise LLMError(f'Missing {provider.upper()}_API_KEY')
        try:
            return cls(provider=provider, model=model, api_key=SecretStr(key) if key else None,
                ollama_base_url=values.get('OLLAMA_BASE_URL') or 'http://localhost:11434',
                timeout_seconds=values.get('LLM_TIMEOUT_SECONDS') or 60,
                max_tokens=values.get('LLM_MAX_TOKENS') or 8192,
                schema_mode=values.get('LLM_SCHEMA_MODE') or 'schema')
        except ValueError:
            raise LLMError('Invalid LLM configuration; check model, time limit, token limit, and schema mode') from None


@dataclass(frozen=True)
class HttpRequest:
    """Internal transport request; headers never enter the audit record."""
    url: str
    body: dict[str, Any]
    timeout_seconds: float
    headers: Mapping[str, str] = field(repr=False)


class Transport(Protocol):
    """Injectable HTTP boundary for offline tests."""

    def __call__(self, request: HttpRequest) -> dict[str, Any]:
        """Return a provider response envelope or raise a sanitized LLMError."""
        ...


class JsonClient(Protocol):
    """Shared extraction/verification/explanation interface, also usable by fixtures."""

    def generate_json(self, *, purpose: Purpose, system_prompt: str, user_prompt: str,
                      schema: dict[str, Any], prompt_version: str) -> CallRecord:
        """Return response evidence; local schema validation remains mandatory."""
        ...


def http_transport(request: HttpRequest) -> dict[str, Any]:
    """POST JSON with a bounded response and sanitized errors, without retries."""
    outgoing = Request(request.url, data=canonical_json(request.body).encode('utf-8'),
                       headers=dict(request.headers), method='POST')
    try:
        with urlopen(outgoing, timeout=request.timeout_seconds) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise LLMError('Provider response exceeds the response size limit')
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise LLMError('Provider response envelope must be an object')
        return parsed
    except HTTPError as error:
        raise LLMError(f'Provider request failed (HTTP {error.code}); check credentials, limits, model, and schema support') from None
    except (URLError, TimeoutError, OSError):
        raise LLMError('Provider connection failed or timed out') from None
    except (ValueError, UnicodeError):
        raise LLMError('Provider returned an invalid JSON envelope') from None


def provider_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Lower discriminated unions to anyOf and require all object fields.

    Domain validation stays strict locally. The wire form omits Pydantic-only
    discriminator metadata and defaults; model/schema incompatibility is an
    explicit provider error, never a silent fallback to another provider.
    """
    def lower(value: Any) -> Any:
        if isinstance(value, list):
            return [lower(item) for item in value]
        if not isinstance(value, dict):
            return value
        result = {('anyOf' if key == 'oneOf' else key): lower(item)
                  for key, item in value.items() if key not in ('discriminator', 'default', 'title')}
        if 'const' in result:
            result['enum'] = [result.pop('const')]
        if result.get('type') == 'object':
            result['additionalProperties'] = False
            result['required'] = list(result.get('properties', {}))
        return result
    return lower(schema)


def _request(settings: ClientSettings, system: str, user: str, schema: dict[str, Any]) -> HttpRequest:
    headers = {'Content-Type': 'application/json', 'User-Agent': USER_AGENT}
    messages = [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]
    wire_schema = provider_schema(schema)
    if settings.provider == 'ollama':
        base = urlparse(settings.ollama_base_url)
        if (base.scheme not in ('http', 'https') or not base.netloc or base.username
                or base.password or base.query or base.fragment):
            raise LLMError('OLLAMA_BASE_URL must be an HTTP(S) base URL without credentials or query parameters')
        if settings.api_key:
            headers['Authorization'] = 'Bearer ' + settings.api_key.get_secret_value()
        return HttpRequest(settings.ollama_base_url.rstrip('/') + '/api/chat',
            {'model': settings.model, 'messages': messages, 'stream': False,
             'format': wire_schema if settings.schema_mode == 'schema' else 'json',
             'options': {'temperature': 0, 'num_predict': settings.max_tokens}}, settings.timeout_seconds, headers)
    if not settings.api_key:
        raise LLMError('This provider requires an API key')
    if settings.provider == 'gemini':
        headers['x-goog-api-key'] = settings.api_key.get_secret_value()
        config: dict[str, Any] = {'temperature': 0, 'maxOutputTokens': settings.max_tokens,
                                  'responseMimeType': 'application/json'}
        if settings.schema_mode == 'schema':
            config['responseJsonSchema'] = wire_schema
        model = quote(settings.model.removeprefix('models/'), safe='')
        return HttpRequest(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
            {'systemInstruction': {'parts': [{'text': system}]},
             'contents': [{'role': 'user', 'parts': [{'text': user}]}], 'generationConfig': config},
            settings.timeout_seconds, headers)
    headers['Authorization'] = 'Bearer ' + settings.api_key.get_secret_value()
    response_format: dict[str, Any] = {'type': 'json_object'}
    if settings.schema_mode == 'schema':
        response_format = {'type': 'json_schema', 'json_schema': {
            'name': 'ota_response', 'strict': True, 'schema': wire_schema}}
    return HttpRequest('https://api.groq.com/openai/v1/chat/completions',
        {'model': settings.model, 'messages': messages, 'temperature': 0,
         'max_completion_tokens': settings.max_tokens, 'response_format': response_format},
        settings.timeout_seconds, headers)


def _content(provider: Provider, response: dict[str, Any]) -> tuple[str, str, bool]:
    try:
        if provider == 'ollama':
            text = response['message']['content']
            reason = response.get('done_reason', 'stop')
            complete = response.get('done') is True and reason == 'stop'
        elif provider == 'gemini':
            candidate = response['candidates'][0]
            text = ''.join(part['text'] for part in candidate['content']['parts']
                           if isinstance(part.get('text'), str) and not part.get('thought', False))
            reason = candidate.get('finishReason', '')
            complete = reason == 'STOP'
        else:
            candidate = response['choices'][0]
            text = candidate['message'].get('content')
            reason = candidate.get('finish_reason', '')
            complete = reason == 'stop' and not candidate['message'].get('refusal')
        if not isinstance(text, str) or not text.strip() or not isinstance(reason, str):
            raise LLMError('Provider returned no usable text or an invalid finish reason')
        return text, reason, complete
    except (KeyError, IndexError, TypeError, AttributeError):
        raise LLMError('Provider returned an unexpected response envelope or refusal') from None


@dataclass
class LLMClient:
    """Provider adapter with a single schema-request interface and no shared state."""
    settings: ClientSettings
    transport: Transport = http_transport

    def generate_json(self, *, purpose: Purpose, system_prompt: str, user_prompt: str,
                      schema: dict[str, Any], prompt_version: str) -> CallRecord:
        """Request structured output and preserve auditable, credential-free evidence."""
        if purpose not in ('extraction', 'verification', 'explanation'):
            raise LLMError('LLMs are limited to extraction, verification, and explanation')
        # Embed the schema in JSON-only mode too; no silent syntax repair is done.
        system = system_prompt + '\nReturn only JSON matching this schema:\n' + canonical_json(schema)
        request = _request(self.settings, system, user_prompt, schema)
        response = self.transport(request)
        text, reason, complete = _content(self.settings.provider, response)
        payload = canonical_json(request.body)
        record = CallRecord(origin='live', provider=self.settings.provider, model=self.settings.model,
            purpose=purpose, prompt_version=prompt_version, request_hash=content_hash(payload),
            endpoint=request.url, request_json=payload, system_prompt=system, user_prompt=user_prompt,
            response_schema_json=canonical_json(schema), response_text=text, finish_reason=reason,
            temperature=0, max_tokens=self.settings.max_tokens)
        logger.info('Completed LLM boundary call: provider=%s purpose=%s', self.settings.provider, purpose)
        if not complete:
            raise LLMError('Provider output was truncated, refused, or not normally completed', record)
        return record


@dataclass
class FixtureClient:
    """Explicit scripted-response fixture for offline examples/evaluation, not an LLM."""
    responses: tuple[str, ...]
    _position: int = field(default=0, init=False, repr=False)

    def generate_json(self, *, purpose: Purpose, system_prompt: str, user_prompt: str,
                      schema: dict[str, Any], prompt_version: str) -> CallRecord:
        """Consume one canned response and label its origin unambiguously."""
        if self._position >= len(self.responses):
            raise LLMError('Fixture has no response for the requested call')
        raw = self.responses[self._position]
        self._position += 1
        payload = canonical_json({'system': system_prompt, 'user': user_prompt, 'schema': schema})
        return CallRecord(origin='fixture', provider='fixture', model='scripted-response',
            purpose=purpose, prompt_version=prompt_version, request_hash=content_hash(payload),
            endpoint='fixture', request_json=payload, system_prompt=system_prompt, user_prompt=user_prompt,
            response_schema_json=canonical_json(schema), response_text=raw, finish_reason='fixture', temperature=0, max_tokens=8192)
