"""Versioned durable records, with no provider credentials."""
from typing import Annotated, Literal
from pydantic import Field, model_serializer, model_validator, SerializerFunctionWrapHandler
from typing import Any, Self
from ..llm.evidence import canonical_json
from ..models import Identifier, Record
from ..workflow_models import ReviewBundle


class PackageVersion(Record):
    """One recorded runtime dependency version."""
    name: str
    version: str


class VersionManifest(Record):
    """Evidence interpretation and restart compatibility metadata."""
    storage_schema: Literal[1, 2] = 1
    bundle_schema: Literal['review-bundle-v1', 'review-bundle-v2'] = 'review-bundle-v2'
    workflow_rules: Literal['workflow-v1', 'workflow-v2'] = 'workflow-v2'
    baseline_policy: Literal['baseline-v1'] = 'baseline-v1'
    guarded_policy: Literal['guarded-trial-v1'] = 'guarded-trial-v1'
    extraction_prompt: str
    verification_prompt: str
    explanation_prompt: str
    code_sha256: Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]
    python_version: str
    sqlite_version: str
    packages: tuple[PackageVersion, ...]


class RunSummary(Record):
    """Library entry; pending can represent an active or interrupted analysis."""
    run_id: Identifier
    revision: int
    campaign_id: str
    status: Literal['pending', 'paused', 'ready', 'uncertain', 'error']
    analysis_status: str | None
    review_state: str
    created_at_utc: str
    snapshot_hash: str | None
    message: str | None


class RevisionChange(Record):
    """A literal change in reviewed input, options, constraints, plan, or findings."""
    section: str
    path: str
    before_json: str
    after_json: str


class RevisionDiff(Record):
    """Deterministic comparison; this is not a semantic equivalence proof."""
    run_id: str
    before_revision: int
    after_revision: int
    changes: tuple[RevisionChange, ...]


class ReviewAuthentication(Record):
    """Server-recorded OIDC provenance, never a token or signed attestation."""
    run_id: str
    revision: int
    issuer: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    roles: tuple[Literal['reader', 'analyst', 'reviewer', 'admin'], ...]
    recorded_at_utc: str


class PersistentBundle(Record):
    """Portable evidence envelope; importing it never grants execution rights."""
    format_version: Literal['persistent-review-v1', 'persistent-review-v2'] = 'persistent-review-v1'
    versions: VersionManifest
    review: ReviewBundle

    review_authentication: tuple[ReviewAuthentication, ...] = ()

    @model_serializer(mode='wrap')
    def legacy_envelope(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        """Keep existing local exports unchanged when no authenticated records exist."""
        result = handler(self)
        if not self.review_authentication:
            result.pop('review_authentication', None)
        return result

    @model_validator(mode='after')
    def bound_provenance(self) -> Self:
        """Bind authenticated provenance to matching immutable decision history."""
        if bool(self.review_authentication) != (self.format_version == 'persistent-review-v2'):
            raise ValueError('Authenticated export schema mismatch')
        revisions = set()
        for record in self.review_authentication:
            decision = next((entry for entry in self.review.decisions if entry.submission.revision == record.revision), None)
            identity = canonical_json({'issuer': record.issuer, 'subject': record.subject})
            if (record.run_id != self.review.run_id or record.revision in revisions or decision is None
                    or decision.submission.reviewer != identity or decision.recorded_at_utc != record.recorded_at_utc
                    or not set(record.roles) & {'reviewer', 'admin'}):
                raise ValueError('Authenticated provenance differs from retained decision')
            revisions.add(record.revision)
        return self
