"""Versioned durable records, with no provider credentials."""
from typing import Annotated, Literal
from pydantic import Field
from ..models import Identifier, Record
from ..workflow_models import ReviewBundle


class PackageVersion(Record):
    """One recorded runtime dependency version."""
    name: str
    version: str


class VersionManifest(Record):
    """Evidence interpretation and restart compatibility metadata."""
    storage_schema: Literal[1] = 1
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


class PersistentBundle(Record):
    """Portable evidence envelope; importing it never grants execution rights."""
    format_version: Literal['persistent-review-v1'] = 'persistent-review-v1'
    versions: VersionManifest
    review: ReviewBundle
