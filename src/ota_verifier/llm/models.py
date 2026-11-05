"""Evidence, structured responses, and reproducible extraction run records."""
from typing import Annotated, Literal, Self
from pydantic import Field, model_validator
from ..models import Campaign, Constraint, Identifier, Record

Purpose = Literal['extraction', 'verification', 'explanation']


class SourceDocument(Record):
    """Exact ingested text; offsets use Python Unicode character indices."""
    id: Identifier
    text: Annotated[str, Field(min_length=1)]


class DocumentRequest(Record):
    """Authoritative inventory plus untrusted release notes and ECU documents."""
    campaign: Campaign
    documents: Annotated[tuple[SourceDocument, ...], Field(min_length=1)]

    @model_validator(mode='after')
    def inventory_and_documents(self) -> Self:
        """Keep extraction separate from prepopulated constraints and duplicate docs."""
        if self.campaign.constraints:
            raise ValueError('Document input campaign must have empty constraints')
        if len({document.id for document in self.documents}) != len(self.documents):
            raise ValueError('Duplicate source document IDs')
        return self


class EvidenceSpan(Record):
    """A half-open character interval in one immutable ingested document."""
    document_id: Identifier
    start_char: Annotated[int, Field(ge=0)]
    end_char: Annotated[int, Field(gt=0)]

    @model_validator(mode='after')
    def positive_span(self) -> Self:
        """Require an ordered, nonempty interval."""
        if self.end_char <= self.start_char:
            raise ValueError('Evidence end must follow start')
        return self


class SourceSegment(Record):
    """A code-generated source segment available for exact LLM citation."""
    evidence: EvidenceSpan
    text: Identifier


class ExtractedConstraint(Record):
    """A domain constraint and the exact segment supporting its source sentence."""
    constraint: Constraint
    evidence: EvidenceSpan


class ExtractionIssue(Record):
    """An ambiguous or unmodeled requirement that must not be guessed."""
    kind: Literal['ambiguous_requirement', 'unsupported_requirement', 'contradictory_documents']
    evidence: EvidenceSpan
    source_text: Identifier
    message: Identifier


class ExtractionDraft(Record):
    """Untrusted model output; required arrays can explicitly be empty."""
    constraints: tuple[ExtractedConstraint, ...]
    issues: tuple[ExtractionIssue, ...]


class VerificationIssue(Record):
    """Second-pass evidence of wrong, missing, ambiguous, or unsupported requirements."""
    kind: Literal['unsupported_constraint', 'incorrect_constraint', 'missing_requirement',
                  'ambiguous_requirement', 'unsupported_requirement']
    constraint_id: str | None
    evidence: EvidenceSpan
    source_text: Identifier
    message: Identifier


class FaithfulnessVerdict(Record):
    """A separate model judgment, never a deterministic proof of correctness."""
    faithful: bool
    reviewed_constraint_ids: tuple[str, ...]
    reviewed_document_ids: tuple[str, ...]
    issues: tuple[VerificationIssue, ...]

    @model_validator(mode='after')
    def consistent_judgment(self) -> Self:
        """Reject approval with outstanding findings or duplicate coverage claims."""
        if self.faithful and self.issues:
            raise ValueError('Faithful verdict cannot have unresolved issues')
        for ids in (self.reviewed_constraint_ids, self.reviewed_document_ids):
            if len(ids) != len(set(ids)):
                raise ValueError('Duplicate verification coverage ID')
        return self


class GateIssue(Record):
    """A deterministic handoff blocker, including model-reported review findings."""
    code: Identifier
    message: str
    constraint_id: str | None = None
    evidence: EvidenceSpan | None = None


class CallRecord(Record):
    """Credential-free request/response evidence, including explicitly labeled fixtures."""
    origin: Literal['live', 'fixture']
    provider: Literal['ollama', 'gemini', 'groq', 'fixture']
    model: Identifier
    purpose: Purpose
    prompt_version: Identifier
    request_hash: Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]
    endpoint: str
    request_json: str
    system_prompt: str
    user_prompt: str
    response_schema_json: str
    response_text: str
    finish_reason: str
    temperature: float
    max_tokens: Annotated[int, Field(gt=0)]

    @model_validator(mode='after')
    def honest_origin(self) -> Self:
        """Offline fixture responses must not masquerade as live provider calls."""
        if (self.origin == 'fixture') != (self.provider == 'fixture'):
            raise ValueError('Fixture origin/provider must agree')
        return self


class DocumentHash(Record):
    """Hash of the UTF-8 encoding of exact ingested text, not normalized file bytes."""
    document_id: Identifier
    sha256: Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]


class ExtractionRun(Record):
    """Reproducible handoff record; blocked runs never expose a planning campaign."""
    status: Literal['ready', 'blocked']
    request: DocumentRequest
    input_hash: Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]
    document_hashes: tuple[DocumentHash, ...]
    draft: ExtractionDraft | None
    verification: FaithfulnessVerdict | None
    issues: tuple[GateIssue, ...]
    calls: tuple[CallRecord, ...]
    campaign: Campaign | None

    @model_validator(mode='after')
    def fail_closed_shape(self) -> Self:
        """A ready run requires complete successful extraction and second-pass evidence."""
        if self.status == 'blocked':
            if self.campaign is not None or not self.issues:
                raise ValueError('Blocked run needs issues and must not expose a campaign')
        else:
            if (self.campaign is None or self.draft is None or self.verification is None
                    or self.issues or not self.verification.faithful):
                raise ValueError('Ready run requires verified evidence and no unresolved issues')
            if tuple(call.purpose for call in self.calls) != ('extraction', 'verification'):
                raise ValueError('Ready run requires separate extraction and verification calls')
        return self
