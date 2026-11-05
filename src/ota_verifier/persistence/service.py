"""Restartable SQLite workflow service with transactional review authority."""
from collections.abc import Callable
import json
from pathlib import Path
import re
import sqlite3
from typing import Any
from uuid import uuid4
from langgraph.checkpoint.sqlite import SqliteSaver
from langsmith import tracing_context
from ..graph import WorkflowClients, build_graph
from ..llm.client import FixtureClient, JsonClient, LLMError
from ..llm.evidence import canonical_json, content_hash
from ..llm.models import Purpose
from ..workflow_models import ReviewBundle, ReviewDecision, ReviewSnapshot, ReviewSubmission, WorkflowInput, snapshot_hash
from .locks import execution_lock
from .models import PersistentBundle, RunSummary, VersionManifest, ReviewAuthentication
from .recipes import ClientRecipe, capture_recipe, materialize_role
from .receipts import ReceiptClient
from .store import RunNotReady, RunStore, StorageError, StorageVersionError, UncertainModelCall
from .versions import current_manifest

ClientFactory = Callable[[ClientRecipe], WorkflowClients]


class PersistentWorkflowService:
    """Optional local durable workspace; MemorySaver's service remains unchanged.

    SQL decisions are authoritative. A graph checkpoint can lag a committed
    decision after a crash, but must never replace or duplicate that decision.
    Graph mutation is serialized across processes without a long SQL transaction.
    """

    def __init__(self, path: Path, client_factory: ClientFactory | None = None,
                 lock_timeout: float = 10) -> None:
        self.policy_rules_version = 'workflow-v2'
        self.store = RunStore(path)
        self.path = self.store.path
        self.lock_path = self.path.with_name(self.path.name + '.execution.lock')
        self.lock_timeout = lock_timeout
        self.client_factory = client_factory
        self._provided: dict[str, WorkflowClients] = {}
        self._materialized: dict[tuple[str, str], JsonClient] = {}
        self._connection = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        self._connection.execute('PRAGMA synchronous=FULL')
        self.graph = build_graph(self._clients_for_thread, SqliteSaver(self._connection), self.store.record_decision)

    def __enter__(self) -> 'PersistentWorkflowService':
        """Own the checkpoint connection for a bounded service lifetime."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Release SQLite resources after use."""
        self.close()

    def close(self) -> None:
        """Close this instance without removing persistent runs or decisions."""
        self._connection.close()

    def _row_for_thread(self, thread_id: str) -> dict[str, Any]:
        run_id, revision = thread_id.rsplit(':', 1)
        return self.store.revision(run_id, int(revision))

    def _actual_client(self, thread_id: str, purpose: Purpose, recipe: ClientRecipe) -> JsonClient:
        key = (thread_id, purpose)
        if key in self._materialized:
            return self._materialized[key]
        dependencies = self._provided.get(thread_id)
        if dependencies is None and self.client_factory is not None:
            dependencies = self.client_factory(recipe)
            self._provided[thread_id] = dependencies
        role = recipe.role(purpose)
        provided = None
        if dependencies:
            provided = {'extraction': dependencies.extractor,
                'verification': dependencies.verifier or dependencies.extractor,
                'explanation': dependencies.explainer}[purpose]
        # Split ordinary shared fixture queues by purpose so replaying extraction
        # never shifts the verifier's canned response position after a restart.
        try:
            result = materialize_role(role, purpose) if provided is None or isinstance(provided, FixtureClient) else provided
        except LLMError as error:
            raise StorageError(str(error)) from None
        self._materialized[key] = result
        return result

    def _clients_for_thread(self, thread_id: str) -> WorkflowClients:
        row = self._row_for_thread(thread_id)
        recipe = ClientRecipe.model_validate_json(row['recipe_json'])
        def wrapper(purpose: Purpose) -> ReceiptClient:
            return ReceiptClient(self.store, thread_id, purpose, recipe.role(purpose),
                                 lambda: self._actual_client(thread_id, purpose, recipe))
        return WorkflowClients(extractor=wrapper('extraction'), verifier=wrapper('verification'),
            explainer=None if recipe.explanation.kind == 'disabled' else wrapper('explanation'))

    def _config(self, run_id: str, revision: int | None = None) -> dict[str, Any]:
        return {'configurable': {'thread_id': self.store.revision(run_id, revision)['thread_id']}}

    def _manifest(self, incoming: WorkflowInput) -> VersionManifest:
        """Record the actual evidence schema while retaining runtime fingerprints."""
        manifest = current_manifest().model_copy(update={'storage_schema': self.store.schema_version})
        if incoming.selected_policy is None:
            return manifest.model_copy(update={'bundle_schema': 'review-bundle-v1', 'workflow_rules': 'workflow-v1'})
        return manifest

    def _start(self, incoming: WorkflowInput, clients: WorkflowClients | None, run_id: str | None,
               recipe: ClientRecipe | None, revise: bool, pause_after: str | None) -> str:
        run_id = run_id or uuid4().hex
        if not re.fullmatch(r'[A-Za-z0-9_-]+', run_id):
            raise StorageError('Run ID must contain only letters, numbers, underscores, or hyphens')
        if recipe is None:
            if clients is None:
                raise StorageError('Starting analysis requires clients or an explicit public ClientRecipe')
            recipe = capture_recipe(clients)
        with execution_lock(self.lock_path, self.lock_timeout):
            revision = self.store.allocate(run_id, incoming, recipe, self._manifest(incoming), revise=revise)
            if clients is not None:
                self._provided[f'{run_id}:{revision}'] = clients
            self._drive(run_id, revision, initialize=True, pause_after=pause_after)
        return run_id

    def start(self, incoming: WorkflowInput, clients: WorkflowClients | None = None, run_id: str | None = None,
              *, recipe: ClientRecipe | None = None) -> ReviewBundle:
        """Analyze a new durable run and pause at human review."""
        return self.get(self._start(incoming, clients, run_id, recipe, False, None))

    def begin(self, incoming: WorkflowInput, clients: WorkflowClients | None = None, run_id: str | None = None,
              *, recipe: ClientRecipe | None = None, pause_after: str = 'extract') -> RunSummary:
        """Commit an intermediate graph checkpoint for explicit later resumption."""
        allowed = {'extract', 'plan', 'simulate', 'compare_policies', 'explain'}
        if pause_after not in allowed:
            raise StorageError('Unsupported analysis pause point')
        created = self._start(incoming, clients, run_id, recipe, False, pause_after)
        return next(item for item in self.list_runs() if item.run_id == created)

    def revise(self, run_id: str, incoming: WorkflowInput, clients: WorkflowClients | None = None,
               *, recipe: ClientRecipe | None = None) -> ReviewBundle:
        """Create a fresh versioned revision, retaining all older artifacts and decisions."""
        return self.get(self._start(incoming, clients, run_id, recipe, True, None))

    def _drive(self, run_id: str, revision: int, *, initialize: bool = False,
               pause_after: str | None = None) -> None:
        row = self.store.revision(run_id, revision)
        versions = VersionManifest.model_validate_json(row['versions_json'])
        if versions != self._manifest(WorkflowInput.model_validate_json(row['input_json'])):
            raise StorageVersionError('Runtime or implementation changed; retain this evidence and create a new revision')
        if row['status'] == 'uncertain':
            raise UncertainModelCall(row['message'] or 'A prior request is uncertain; create a new revision to retry')
        config = self._config(run_id, revision)
        incoming = json.loads(row['input_json'])
        initial = {'run_id': run_id, 'revision': revision, 'input': incoming, 'completed_nodes': []} if initialize else None
        if not initialize and not self.graph.get_state(config).values:
            with self.store.connect() as connection:
                receipts = connection.execute('SELECT 1 FROM ota_receipts WHERE thread_id=? LIMIT 1', (row['thread_id'],)).fetchone()
            if receipts or json.loads(row['completed_nodes_json']):
                raise StorageError('Interrupted analysis checkpoint is missing; retain evidence and create a new revision')
            # Allocation may commit before the very first graph checkpoint.
            initial = {'run_id': run_id, 'revision': revision, 'input': incoming, 'completed_nodes': []}
        try:
            with tracing_context(enabled=False):
                self.graph.invoke(initial, config, interrupt_after=[pause_after] if pause_after else None)
        except UncertainModelCall as error:
            self.store.mark(run_id, revision, 'uncertain', str(error))
            raise
        except Exception as error:
            message = str(error) if isinstance(error, StorageError) else f'Execution interrupted ({type(error).__name__}); no automatic retry'
            self.store.mark(run_id, revision, 'error', message)
            raise
        state = self.graph.get_state(config)
        nodes = canonical_json(state.values.get('completed_nodes', []))
        if state.values.get('snapshot') and state.next == ('human_review',):
            snapshot = ReviewSnapshot.model_validate_json(canonical_json(state.values['snapshot']))
            self.store.publish(run_id, revision, snapshot, nodes)
        else:
            self.store.mark(run_id, revision, 'paused', completed_nodes_json=nodes)

    def _bundle(self, run_id: str, revision: int | None = None) -> ReviewBundle:
        row = self.store.revision(run_id, revision)
        if row['status'] != 'ready' or row['snapshot_json'] is None:
            raise RunNotReady(f"Revision is {row['status']}; no complete review snapshot is published")
        snapshot = ReviewSnapshot.model_validate_json(row['snapshot_json'])
        if snapshot.artifacts.input != WorkflowInput.model_validate_json(row['input_json']):
            raise StorageError('Stored snapshot input differs from immutable revision input')
        digest = snapshot_hash(run_id, row['revision'], snapshot)
        if digest != row['snapshot_hash']:
            raise StorageError('Stored analysis snapshot hash mismatch')
        checkpoint = self.graph.get_state(self._config(run_id, row['revision']))
        if not checkpoint.values.get('snapshot') or ReviewSnapshot.model_validate_json(
            canonical_json(checkpoint.values['snapshot'])) != snapshot:
            raise StorageError('Analysis checkpoint is missing, corrupt, or differs from published evidence')
        decisions = self.store.decisions(run_id, row['revision'])
        decision = next((item for item in decisions if item.submission.revision == row['revision']), None)
        if decision:
            review_state = {'approve': 'approved', 'reject': 'rejected',
                            'review_with_findings': 'reviewed_with_findings'}[decision.submission.action]
        else:
            review_state = 'invalidated' if decisions else 'awaiting_review'
        nodes = tuple(json.loads(row['completed_nodes_json']))
        if decision is not None and 'human_review' not in nodes:
            nodes += ('human_review',)  # The authoritative review effect committed even if its graph cache lagged.
        return ReviewBundle(format_version='review-bundle-v2' if snapshot.rules_version == 'workflow-v2' else 'review-bundle-v1',
            run_id=run_id, revision=row['revision'], snapshot=snapshot, snapshot_hash=digest,
            review_state=review_state, current_decision=decision, decisions=decisions, completed_nodes=nodes)

    def get(self, run_id: str) -> ReviewBundle:
        """Open the latest published evidence without running a model or graph node."""
        return self._bundle(run_id)

    def get_revision(self, run_id: str, revision: int) -> ReviewBundle:
        """Read a historical immutable revision; decisions still bind only to its hash."""
        return self._bundle(run_id, revision)

    def resume(self, run_id: str) -> ReviewBundle:
        """Continue from committed analysis; ready reviews require no credentials or replay."""
        with execution_lock(self.lock_path, self.lock_timeout):
            self.store.assert_writable(run_id)
            row = self.store.revision(run_id)
            if row['status'] != 'ready':
                self._drive(run_id, row['revision'])
            return self.get(run_id)

    def review(self, submission: ReviewSubmission) -> ReviewBundle:
        """Run the review gate with a transactional, cross-process decision recorder."""
        with execution_lock(self.lock_path, self.lock_timeout):
            self.store.assert_writable(submission.run_id)
            bundle = self.get(submission.run_id)
            if submission.revision != bundle.revision or submission.snapshot_hash != bundle.snapshot_hash:
                raise StorageError('Review is stale; inspect the latest revision')
            for previous in bundle.decisions:
                if previous.submission.idempotency_key == submission.idempotency_key:
                    if previous.submission != submission:
                        raise StorageError('Idempotency key already belongs to another decision')
                    return bundle
            if bundle.current_decision is not None:
                raise StorageError('This revision already has a final decision')
            row = self.store.revision(submission.run_id)
            versions = VersionManifest.model_validate_json(row['versions_json'])
            if versions != self._manifest(WorkflowInput.model_validate_json(row['input_json'])):
                raise StorageVersionError('Runtime changed; create a new analysis revision before adding a decision')
            config = self._config(submission.run_id)
            with tracing_context(enabled=False):
                self.graph.update_state(config, {'pending_decision': submission.model_dump(mode='json')}, as_node='prepare_review')
                self.graph.invoke(None, config)
            result = self.get(submission.run_id)
            if result.current_decision is None or result.current_decision.submission != submission:
                raise StorageError('Committed review does not match this submission')
            return result

    def list_runs(self) -> tuple[RunSummary, ...]:
        """List the current revision of each local workspace run."""
        return self.store.summaries()

    def revisions(self, run_id: str) -> tuple[RunSummary, ...]:
        """List retained revisions without changing current selection or replaying work."""
        return self.store.summaries(run_id)

    def export(self, run_id: str, revision: int | None = None) -> PersistentBundle:
        """Export versions and full review evidence as a validated portable envelope."""
        row = self.store.revision(run_id, revision)
        authentication = self.review_authentication(run_id, row['revision'])
        return PersistentBundle(format_version='persistent-review-v2' if authentication else 'persistent-review-v1',
            versions=VersionManifest.model_validate_json(row['versions_json']),
            review=self._bundle(run_id, row['revision']), review_authentication=authentication)

    def partial_evidence(self, run_id: str) -> dict[str, Any]:
        """Expose committed checkpoint evidence for interrupted runs without granting review."""
        row = self.store.revision(run_id)
        values = self.graph.get_state(self._config(run_id)).values
        return {'run_id': run_id, 'revision': row['revision'], 'status': row['status'], 'message': row['message'],
                'versions': json.loads(row['versions_json']), 'checkpoint': values}


    def workflow_input(self, run_id: str) -> WorkflowInput:
        """Read immutable inputs for restoring a saved editor draft."""
        return WorkflowInput.model_validate_json(self.store.revision(run_id)['input_json'])


    def review_authentication(self, run_id: str, revision: int) -> tuple[ReviewAuthentication, ...]:
        """Read OIDC provenance separately from historical self-reported reviews."""
        if self.store.schema_version != 2:
            return ()
        with self.store.connect() as connection:
            records = connection.execute('SELECT * FROM ota_review_auth WHERE run_id=? AND revision<=? ORDER BY revision',
                (run_id, revision)).fetchall()
        return tuple(ReviewAuthentication(run_id=run_id, revision=record['revision'],
            **json.loads(record['identity_json']), roles=tuple(json.loads(record['roles_json'])),
            recorded_at_utc=record['recorded_at']) for record in records)

    def archive_info(self, run_id: str) -> dict[str, Any] | None:
        """Read a retention marker without changing or hiding its evidence."""
        if self.store.schema_version != 2:
            return None
        with self.store.connect() as connection:
            row = connection.execute('SELECT * FROM ota_retention WHERE run_id=?', (run_id,)).fetchone()
        return dict(row) if row else None
