"""Reconstructible client recipes containing public settings or explicit fixtures only."""
from typing import Literal
from urllib.parse import urlparse
from pydantic import model_validator
from ..models import Record
from ..graph import WorkflowClients
from ..llm.client import ClientSettings, FixtureClient, JsonClient, LLMClient, LLMError
from ..llm.explainer import FixtureExplanationClient
from ..llm.models import Purpose


class PublicSettings(Record):
    """Explicit allowlist: API keys cannot be serialized into provider configuration."""
    provider: Literal['ollama', 'gemini', 'groq']
    model: str
    ollama_base_url: str
    timeout_seconds: float
    max_tokens: int
    schema_mode: Literal['schema', 'json']

    @model_validator(mode='after')
    def credential_free_url(self) -> 'PublicSettings':
        """Reject credentials/query secrets embedded in a saved endpoint."""
        parsed = urlparse(self.ollama_base_url)
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('Provider endpoint must not contain credentials or query parameters')
        return self

    @classmethod
    def capture(cls, settings: ClientSettings) -> 'PublicSettings':
        """Copy only the public settings already excluded from credential serialization."""
        return cls.model_validate_json(settings.model_dump_json())


class RoleRecipe(Record):
    """One restartable role; fixtures are labeled and never a provider env value."""
    kind: Literal['provider', 'fixture', 'fixture_explanation', 'disabled']
    settings: PublicSettings | None = None
    responses: tuple[str, ...] = ()

    @model_validator(mode='after')
    def consistent(self) -> 'RoleRecipe':
        """Provider settings and canned response payloads cannot be mixed."""
        if (self.kind == 'provider') != (self.settings is not None):
            raise ValueError('Recipe provider/settings mismatch')
        if self.kind != 'fixture' and self.responses:
            raise ValueError('Only fixtures may contain canned responses')
        return self


class ClientRecipe(Record):
    """Public reconstruction data for exactly the three permitted model roles."""
    format_version: Literal['client-recipe-v1'] = 'client-recipe-v1'
    extraction: RoleRecipe
    verification: RoleRecipe
    explanation: RoleRecipe

    def role(self, purpose: Purpose) -> RoleRecipe:
        """Return a saved role without accessing environment credentials."""
        return {'extraction': self.extraction, 'verification': self.verification, 'explanation': self.explanation}[purpose]


def _capture(client: JsonClient | None) -> RoleRecipe:
    if isinstance(client, LLMClient):
        return RoleRecipe(kind='provider', settings=PublicSettings.capture(client.settings))
    if isinstance(client, FixtureClient):
        if client._position:
            raise ValueError('Persistent runs require fresh fixture clients')
        return RoleRecipe(kind='fixture', responses=client.responses)
    if client is None:
        return RoleRecipe(kind='disabled')
    if isinstance(client, FixtureExplanationClient):
        return RoleRecipe(kind='fixture_explanation')
    raise ValueError('Custom clients require an explicit credential-free ClientRecipe')


def capture_recipe(clients: WorkflowClients) -> ClientRecipe:
    """Capture supported public clients, separating a shared fixture response queue."""
    if isinstance(clients.extractor, FixtureClient) and clients.verifier is None:
        responses = clients.extractor.responses
        if clients.extractor._position:
            raise ValueError('Persistent runs require fresh fixture clients')
        extraction = RoleRecipe(kind='fixture', responses=responses[:1])
        verification = RoleRecipe(kind='fixture', responses=responses[1:2])
    else:
        extraction = _capture(clients.extractor)
        verification = _capture(clients.verifier or clients.extractor)
    return ClientRecipe(extraction=extraction, verification=verification, explanation=_capture(clients.explainer))


def materialize_role(recipe: RoleRecipe, purpose: Purpose) -> JsonClient:
    """Rebuild fixtures or explicitly configured live clients; never persist credentials."""
    if recipe.kind == 'disabled':
        raise ValueError('Disabled model role cannot make a call')
    if recipe.kind == 'fixture':
        return FixtureClient(recipe.responses)
    if recipe.kind == 'fixture_explanation':
        if purpose != 'explanation':
            raise ValueError('Explanation fixture cannot serve another purpose')
        return FixtureExplanationClient()
    settings = ClientSettings.from_env(purpose)
    if PublicSettings.capture(settings) != recipe.settings:
        raise LLMError('Configured provider/model/options changed; create a new revision instead of mixing results')
    return LLMClient(settings)
