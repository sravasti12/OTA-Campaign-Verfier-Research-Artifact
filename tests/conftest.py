"""Opt-in private-configuration isolation for offline evaluation profile tests."""
from typing import Any
import pytest
from pydantic import SecretStr
from ota_verifier.llm.client import ClientSettings


@pytest.fixture
def offline_groq_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Supply explicit dummy settings and prohibit real HTTP for opted-in tests.

    This patches the settings boundary only within the requesting test; production
    environment loading and the dedicated configuration tests remain unchanged.
    """
    def settings(cls: type[ClientSettings], purpose: str = 'extraction', **kwargs: Any) -> ClientSettings:
        return cls(provider='groq', model='openai/gpt-oss-20b', api_key=SecretStr('offline-test-key'),
                   schema_mode='json', max_tokens=8192, timeout_seconds=60)

    def forbidden_http(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError('Real HTTP is prohibited in offline evaluation-profile tests')

    monkeypatch.setattr(ClientSettings, 'from_env', classmethod(settings))
    monkeypatch.setattr('ota_verifier.llm.client.urlopen', forbidden_http)
