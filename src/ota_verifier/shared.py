"""Role-enforced shared review service, for trusted single-host application code."""
from collections.abc import Callable
from pathlib import Path
from typing import Any
from langgraph.checkpoint.sqlite import SqliteSaver
from .access import Account, Action, AccessDenied
from .graph import WorkflowClients, build_graph
from .llm.evidence import canonical_json
from .persistence.models import PersistentBundle, RunSummary, ReviewAuthentication
from .persistence.recipes import ClientRecipe
from .persistence.service import PersistentWorkflowService
from .workflow_models import ReviewBundle, ReviewDecision, ReviewSnapshot, ReviewSubmission, WorkflowInput


class SharedWorkflowService(PersistentWorkflowService):
    """Authorize every public operation and the final decision effect.

    This boundary is for the browser application, not a Python sandbox: host
    operators owning the database and source remain trusted. No user-supplied
    role, reviewer display name, database path, or token is accepted here.
    """

    def __init__(self, path: Path, authorize_action: Callable[[Action], Account]) -> None:
        self._authorize_action = authorize_action
        self._authorize_action('read')
        super().__init__(path)
        if self.store.schema_version != 2:
            self.close()
            raise AccessDenied('Shared review requires explicit operational schema 2 migration')
        self.graph = build_graph(self._clients_for_thread, SqliteSaver(self._connection), self._record_authenticated)

    def account(self, action: Action = 'read') -> Account:
        """Resolve fresh server grants, including revocations and session expiry."""
        return self._authorize_action(action)

    def allowed(self, action: Action) -> bool:
        """Expose UI affordances without replacing enforcement at operation time."""
        try:
            self.account(action)
            return True
        except AccessDenied:
            return False

    def _record_authenticated(self, submission: ReviewSubmission, snapshot: ReviewSnapshot) -> ReviewDecision:
        account = self.account('review')
        if submission.reviewer != account.identity:
            raise AccessDenied('Authenticated identity changed before decision commit')
        return self.store.record_decision(submission, snapshot, identity_json=account.identity,
            roles_json=canonical_json(account.roles))

    def start(self, incoming: WorkflowInput, clients: WorkflowClients | None = None, run_id: str | None = None,
              *, recipe: ClientRecipe | None = None) -> ReviewBundle:
        """Only analysts/admins can create provider work or deterministic analyses."""
        self.account('analyze')
        return super().start(incoming, clients, run_id, recipe=recipe)

    def begin(self, incoming: WorkflowInput, clients: WorkflowClients | None = None, run_id: str | None = None,
              *, recipe: ClientRecipe | None = None, pause_after: str = 'extract') -> RunSummary:
        """Enforce analysis permissions for checkpointed work too."""
        self.account('analyze')
        return super().begin(incoming, clients, run_id, recipe=recipe, pause_after=pause_after)

    def revise(self, run_id: str, incoming: WorkflowInput, clients: WorkflowClients | None = None,
               *, recipe: ClientRecipe | None = None) -> ReviewBundle:
        """Only analysts/admins can change reviewed policy/input through a new revision."""
        self.account('analyze')
        return super().revise(run_id, incoming, clients, recipe=recipe)

    def resume(self, run_id: str) -> ReviewBundle:
        """Continuing analysis requires analyst rights, even if currently complete."""
        self.account('analyze')
        return super().resume(run_id)

    def review(self, submission: ReviewSubmission) -> ReviewBundle:
        """Bind reviewer identity from verified OIDC grants, overriding form input."""
        actor = self.account('review')
        bound = submission.model_copy(update={'reviewer': actor.identity})
        return super().review(bound)

    def get(self, run_id: str) -> ReviewBundle:
        """Read evidence only after checking current account access."""
        self.account('read')
        return super().get(run_id)

    def get_revision(self, run_id: str, revision: int) -> ReviewBundle:
        """Protect historical evidence just as current evidence."""
        self.account('read')
        return super().get_revision(run_id, revision)

    def list_runs(self) -> tuple[RunSummary, ...]:
        """List authorized workspace entries."""
        self.account('read')
        return super().list_runs()

    def revisions(self, run_id: str) -> tuple[RunSummary, ...]:
        """List retained revisions after authorization."""
        self.account('read')
        return super().revisions(run_id)

    def export(self, run_id: str, revision: int | None = None) -> PersistentBundle:
        """Protect full portable exports, not just on-screen summaries."""
        self.account('read')
        return super().export(run_id, revision)

    def partial_evidence(self, run_id: str) -> dict[str, Any]:
        """Protect interrupted raw documents and call records."""
        self.account('read')
        return super().partial_evidence(run_id)

    def workflow_input(self, run_id: str) -> WorkflowInput:
        """Protect saved editor inputs."""
        self.account('read')
        return super().workflow_input(run_id)


    def review_authentication(self, run_id: str, revision: int) -> tuple[ReviewAuthentication, ...]:
        """Protect authenticated actor history."""
        self.account('read')
        return super().review_authentication(run_id, revision)

    def archive_info(self, run_id: str) -> dict[str, Any] | None:
        """Protect retention metadata."""
        self.account('read')
        return super().archive_info(run_id)
