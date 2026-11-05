"""Offline workflow examples and explicit provider dependencies for the local UI."""
from typing import Literal
from .data.generate import SCENARIOS, SyntheticCase, generate_case
from .evaluation import fixture_client
from .graph import WorkflowClients
from .llm.client import ClientSettings, LLMClient
from .llm.explainer import FixtureExplanationClient
from .llm.models import DocumentRequest
from .models import Campaign, DowngradeAuthorization, ECU

Example = Literal['clear', 'dependency_only', 'order_conflict', 'intermediate_trap', 'ambiguous', 'unsupported', 'no_updates', 'authorized_rollback']
EXAMPLES: tuple[Example, ...] = (*SCENARIOS, 'no_updates', 'authorized_rollback')


def example_input(name: Example = 'clear') -> tuple[DocumentRequest, SyntheticCase]:
    """Return source-only input and a separate canned-response case.

    The no-updates example demonstrates a passing review without claiming fault
    tolerance for a nonempty campaign; it has zero fault cases explicitly.
    """
    if name not in EXAMPLES:
        raise ValueError('Unknown workflow example')
    case = generate_case('clear' if name in ('no_updates', 'authorized_rollback') else name)
    request = case.request
    if name == 'no_updates':
        inventory = request.campaign
        ecus = tuple(ECU(**ecu.model_dump(exclude={'target_version'}), target_version=ecu.current_version)
                     for ecu in inventory.ecus)
        request = DocumentRequest(campaign=Campaign(id=inventory.id, ecus=ecus,
            initial_state=inventory.initial_state, downgrade_authorizations=inventory.downgrade_authorizations),
            documents=request.documents)
    if name == 'authorized_rollback':
        inventory = request.campaign
        permissions = tuple(DowngradeAuthorization(ecu_id=ecu.id, version=ecu.current_version,
            authorized_by='synthetic-reviewer', reason='Explicit original-image rollback permission for this simulation example')
            for ecu in inventory.ecus)
        request = DocumentRequest(campaign=Campaign(id=inventory.id, ecus=inventory.ecus,
            initial_state=inventory.initial_state, downgrade_authorizations=permissions), documents=request.documents)
    return request, case


def fixture_dependencies(case: SyntheticCase) -> WorkflowClients:
    """Create fresh per-run fixture clients, never reusing consumed response queues."""
    return WorkflowClients(extractor=fixture_client(case), explainer=FixtureExplanationClient())


def live_dependencies() -> WorkflowClients:
    """Read configured provider settings only when a live run is explicitly submitted."""
    return WorkflowClients(extractor=LLMClient(ClientSettings.from_env()),
        verifier=LLMClient(ClientSettings.from_env('verification')),
        explainer=LLMClient(ClientSettings.from_env('explanation')))
