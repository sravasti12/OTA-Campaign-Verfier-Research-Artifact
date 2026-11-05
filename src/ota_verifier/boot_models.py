"""Guarded trial-boot records, separate from the unchanged baseline ECU model."""
from typing import Annotated, Literal, Self
from pydantic import Field, model_validator
from .models import Identifier, Plan, Record, Slot, VehicleState, Violation
from .simulation_models import Assessment, FaultSpec, InvariantFinding, SimulationOptions

GuardedStage = Literal['erase', 'write', 'verify', 'activate', 'boot', 'confirm']
Health = Literal['unknown', 'passed', 'failed']
GUARDED_CASES_PER_ECU = 16


class GuardedOptions(Record):
    """Explicit finite trial budget; other persistence semantics are versioned rules."""
    max_trial_attempts: Annotated[int, Field(gt=0, le=10)] = 2
    policy: Literal['guarded-trial-v1'] = 'guarded-trial-v1'


class GuardedFaultSpec(FaultSpec):
    """The shared five-stage faults plus power loss around atomic confirmation."""
    stage: GuardedStage


class BootMetadata(Record):
    """Confirmed selection, observed health, and attempt counter survive power loss.

    Candidate selection and running_slot are volatile. Effective installed
    versions live in GuardedSnapshot.state and remain known during an outage.
    """
    ecu_id: Identifier
    confirmed_slot: Slot
    candidate_slot: Slot | None
    running_slot: Slot | None
    available: bool
    health_a: Health
    health_b: Health
    attempts_used: Annotated[int, Field(ge=0)] = 0

    @model_validator(mode='after')
    def explicit_availability(self) -> Self:
        """Unavailable ECUs cannot claim a running slot."""
        if self.available != (self.running_slot is not None):
            raise ValueError('Availability and running slot disagree')
        return self


class GuardedSnapshot(Record):
    """Known effective versions plus explicit runtime availability and boot metadata."""
    state: VehicleState
    boot: tuple[BootMetadata, ...]

    @model_validator(mode='after')
    def matching_ecus(self) -> Self:
        """Require complete, unique metadata and consistent effective/running slots."""
        ids = [metadata.ecu_id for metadata in self.boot]
        if len(ids) != len(set(ids)) or set(ids) != {ecu.ecu_id for ecu in self.state.ecus}:
            raise ValueError('Boot metadata must cover exactly the runtime ECUs')
        active = {ecu.ecu_id: ecu.active_slot for ecu in self.state.ecus}
        if any(metadata.available and metadata.running_slot != active[metadata.ecu_id] for metadata in self.boot):
            raise ValueError('A running image must be the effective installed image')
        return self


class GuardedEvent(Record):
    """Every logical boot boundary, including outages and rejected transitions."""
    time_ms: Annotated[int, Field(ge=0)]
    ecu_id: str | None
    stage: Literal['initial', 'erase', 'write', 'verify', 'activate', 'boot', 'confirm',
                   'boot_attempt', 'fault', 'halt', 'power_restored', 'guard_blocked',
                   'reboot', 'recover_begin', 'recover_boot', 'recover_confirm']
    snapshot: GuardedSnapshot
    writing_ecus: tuple[str, ...] = ()
    message: str = ''


class GuardedRecoveryAction(Record):
    """An explicit boot/slot selection followed by atomic confirmation."""
    ecu_id: Identifier
    slot: Slot


class GuardedRecovery(Record):
    """Bounded recovery proof over known healthy stored images and availability."""
    status: Literal['available', 'unavailable', 'unknown']
    states: Annotated[tuple[GuardedSnapshot, ...], Field(min_length=1)]
    steps: tuple[GuardedRecoveryAction, ...] = ()
    examined_states: Annotated[int, Field(ge=0)]
    reason: str
    blockers: tuple[Violation, ...] = ()

    @model_validator(mode='after')
    def complete_path(self) -> Self:
        """Only proven paths may contain actions and successor states."""
        if len(self.states) != len(self.steps) + 1 or self.status != 'available' and self.steps:
            raise ValueError('Inconsistent guarded recovery path')
        return self


class GuardedResult(Record):
    """A single guarded execution; a failed fault run can preserve all invariants."""
    campaign_id: Identifier
    fault: GuardedFaultSpec | None
    status: Literal['completed', 'failed']
    assessment: Assessment
    trace: Annotated[tuple[GuardedEvent, ...], Field(min_length=1)]
    findings: tuple[InvariantFinding, ...] = ()
    recovery: GuardedRecovery | None = None
    guard_blockers: tuple[Violation, ...] = ()

    @model_validator(mode='after')
    def truthful_verdict(self) -> Self:
        """Retain historical violations and never treat search limits as a pass."""
        if self.status == 'failed' and (self.fault is None or self.recovery is None):
            raise ValueError('Failed guarded run requires fault and recovery evidence')
        if self.status == 'completed' and (self.fault is not None or self.recovery is not None):
            raise ValueError('Nominal completion cannot contain a fault or recovery')
        if self.recovery is not None and self.recovery.status == 'unavailable' and not any(
            finding.invariant == 'rollback_path' for finding in self.findings
        ):
            raise ValueError('Proven missing rollback needs an invariant finding')
        expected = ('violations' if self.findings else 'inconclusive'
                    if self.recovery is not None and self.recovery.status == 'unknown' else 'passed')
        if self.recovery is not None and self.recovery.status == 'available' and self.trace[-1].snapshot != self.recovery.states[-1]:
            raise ValueError('Executed final state differs from proven guarded recovery')
        if self.assessment != expected or any(f.trace_index >= len(self.trace) for f in self.findings):
            raise ValueError('Guarded assessment or finding reference disagrees with evidence')
        return self


class GuardedStressReport(Record):
    """Complete guarded coverage: 14 common plus 2 confirmation cases per update."""
    campaign_id: Identifier
    plan: Plan
    options: SimulationOptions
    guarded_options: GuardedOptions
    nominal: GuardedResult
    cases: tuple[GuardedResult, ...]
    expected_fault_cases: int
    assessment: Assessment

    @model_validator(mode='after')
    def complete_coverage(self) -> Self:
        """Reject incomplete, duplicated, cross-campaign, or misclassified sweeps."""
        if self.expected_fault_cases != GUARDED_CASES_PER_ECU * len(self.plan.steps) or len(self.cases) != self.expected_fault_cases:
            raise ValueError('Guarded fault coverage must be complete')
        if self.campaign_id != self.plan.campaign_id or self.nominal.campaign_id != self.campaign_id or self.nominal.status != 'completed':
            raise ValueError('Guarded nominal identity/completion mismatch')
        ids = {step.ecu_id for step in self.plan.steps}
        if any(case.campaign_id != self.campaign_id or case.status != 'failed' or case.fault is None or case.fault.ecu_id not in ids for case in self.cases):
            raise ValueError('Invalid guarded fault case identity')
        if len({case.fault for case in self.cases}) != len(self.cases):
            raise ValueError('Duplicate guarded fault case')
        for result in (self.nominal, *self.cases):
            if any(metadata.attempts_used > self.guarded_options.max_trial_attempts
                   for event in result.trace for metadata in event.snapshot.boot):
                raise ValueError('Recorded trial attempts exceed the declared policy budget')
        assessments = (self.nominal.assessment, *(case.assessment for case in self.cases))
        expected = 'violations' if 'violations' in assessments else 'inconclusive' if 'inconclusive' in assessments else 'passed'
        if self.assessment != expected:
            raise ValueError('Guarded stress verdict disagrees with cases')
        return self
