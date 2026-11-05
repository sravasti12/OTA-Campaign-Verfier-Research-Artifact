"""Evidence-linked explanation schemas; model prose never determines verdicts."""
from typing import Annotated, Literal, Self
from pydantic import Field, model_validator
from ..models import Identifier, Record
from .models import CallRecord

AnalysisStatus = Literal['extraction_blocked', 'planning_infeasible', 'planning_unknown',
                         'simulation_passed', 'simulation_violations', 'simulation_inconclusive']
FactOutcome = Literal['passed', 'blocked', 'feasible', 'infeasible', 'unknown', 'violation', 'information']


class EvidenceFact(Record):
    """An authoritative fact with navigable source or simulation coordinates."""
    id: Identifier
    kind: Literal['extraction', 'constraint', 'plan', 'step', 'conflict', 'simulation', 'fault', 'finding']
    outcome: FactOutcome
    message: str
    detail_json: str
    constraint_id: str | None = None
    source_document_id: str | None = None
    source_text: str | None = None
    case_index: int | None = None
    trace_index: int | None = None
    required_in_explanation: bool = False


class ExplanationStatement(Record):
    """Advisory prose citing exactly one fact and preserving its typed outcome."""
    evidence_id: Identifier
    outcome: FactOutcome
    text: Annotated[str, Field(min_length=1, max_length=2000)]


class ExplanationDraft(Record):
    """A model explanation must preserve the deterministic overall status."""
    analysis_status: AnalysisStatus
    statements: Annotated[tuple[ExplanationStatement, ...], Field(min_length=1, max_length=30)]


class ExplanationResult(Record):
    """Validated advisory explanation or a deterministic fallback with evidence."""
    status: Literal['live', 'fixture', 'fallback']
    deterministic_summary: tuple[str, ...]
    draft: ExplanationDraft | None
    call: CallRecord | None
    issues: tuple[str, ...]

    @model_validator(mode='after')
    def consistent_result(self) -> Self:
        """Do not expose rejected explanation prose as a validated draft."""
        if self.status == 'fallback':
            if self.draft is not None or not self.issues:
                raise ValueError('Fallback requires issues and must not expose an accepted draft')
        elif (self.draft is None or self.call is None or self.issues
              or self.call.purpose != 'explanation' or self.call.origin != self.status):
            raise ValueError('Accepted explanation requires matching call evidence')
        return self
