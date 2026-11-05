"""Strict records for deterministic fault simulation and recovery evidence."""
from typing import Annotated, Literal, Self
from pydantic import Field, model_validator
from .models import Identifier, Plan, Record, Slot, VehicleState, Version, Violation

FAULT_CASES_PER_ECU = 14

FlashStage = Literal['erase', 'write', 'verify', 'activate', 'boot']
FaultKind = Literal['power_loss', 'write_corruption', 'verification_failure', 'activation_failure', 'boot_failure']
Assessment = Literal['passed', 'violations', 'inconclusive']
Invariant = Literal['bootable_image', 'compatible_versions', 'authorized_downgrade', 'rollback_path']


class FaultSpec(Record):
    """Exactly one injected cause, addressed by ECU, stage, and boundary."""
    ecu_id: Identifier
    stage: FlashStage
    kind: FaultKind
    when: Literal['before', 'after'] = 'before'

    @model_validator(mode='after')
    def applicable_boundary(self) -> Self:
        """Reject fault/stage combinations with no defined simulation semantics."""
        if self.kind == 'power_loss':
            return self
        expected = {
            'write_corruption': ('write', 'after'),
            'verification_failure': ('verify', 'before'),
            'activation_failure': ('activate', 'before'),
            'boot_failure': ('boot', 'before'),
        }
        if (self.stage, self.when) != expected[self.kind]:
            raise ValueError(f'Unsupported boundary for {self.kind}')
        return self


class SimulationOptions(Record):
    """Deterministic bound on recovery states, not a wall-clock timeout."""
    max_recovery_states: Annotated[int, Field(gt=0)] = 10_000


class RecoveryStep(Record):
    """A single bootable slot switch; recovery never fabricates or reflashes images."""
    ecu_id: Identifier
    from_slot: Slot
    to_slot: Slot
    from_version: Version
    to_version: Version

    @model_validator(mode='after')
    def different_slots(self) -> Self:
        """A recovery action must switch to the other slot."""
        if self.from_slot == self.to_slot:
            raise ValueError('Recovery must switch slots')
        return self


class RecoveryResult(Record):
    """Shortest safe authorized path to original active images, or honest uncertainty."""
    status: Literal['available', 'unavailable', 'unknown']
    states: Annotated[tuple[VehicleState, ...], Field(min_length=1)]
    steps: tuple[RecoveryStep, ...] = ()
    examined_states: Annotated[int, Field(ge=0)]
    reason: str
    blockers: tuple[Violation, ...] = ()

    @model_validator(mode='after')
    def consistent_path(self) -> Self:
        """Only an available result may contain a recovery path."""
        if len(self.states) != len(self.steps) + 1:
            raise ValueError('Recovery requires a state per action plus its initial state')
        if self.status != 'available' and self.steps:
            raise ValueError('Unproved recovery cannot contain claimed actions')
        return self


class SimulationEvent(Record):
    """An observed transition, including concurrent write activity."""
    time_ms: Annotated[int, Field(ge=0)]
    ecu_id: str | None
    stage: Literal['initial', 'erase', 'write', 'verify', 'activate', 'boot', 'fault', 'halt', 'recover']
    state: VehicleState
    writing_ecus: tuple[str, ...] = ()
    message: str = ''


class InvariantFinding(Record):
    """A violation tied to its exact trace observation."""
    invariant: Invariant
    trace_index: Annotated[int, Field(ge=0)]
    violation: Violation


class SimulationResult(Record):
    """One nominal or single-fault execution with all historical findings retained."""
    campaign_id: Identifier
    fault: FaultSpec | None
    status: Literal['completed', 'failed']
    assessment: Assessment
    trace: Annotated[tuple[SimulationEvent, ...], Field(min_length=1)]
    findings: tuple[InvariantFinding, ...] = ()
    recovery: RecoveryResult | None = None

    @model_validator(mode='after')
    def consistent_outcome(self) -> Self:
        """Keep failure handling and verdicts consistent with recorded evidence."""
        if self.status == 'failed' and (self.fault is None or self.recovery is None):
            raise ValueError('Failed runs require fault and recovery evidence')
        if self.recovery is not None and self.recovery.status == 'unavailable' and not any(
            finding.invariant == 'rollback_path' for finding in self.findings
        ):
            raise ValueError('Unavailable recovery must report a rollback invariant violation')
        if self.status == 'completed' and (self.fault is not None or self.recovery is not None):
            raise ValueError('Completed nominal runs cannot claim an injected fault')
        expected = ('violations' if self.findings else 'inconclusive'
                    if self.recovery is not None and self.recovery.status == 'unknown' else 'passed')
        if self.assessment != expected:
            raise ValueError('Assessment disagrees with recorded evidence')
        if any(f.trace_index >= len(self.trace) for f in self.findings):
            raise ValueError('Finding references an absent trace event')
        return self


class StressReport(Record):
    """Nominal execution plus complete coverage of the bounded fault matrix."""
    campaign_id: Identifier
    plan: Plan
    options: SimulationOptions
    nominal: SimulationResult
    cases: tuple[SimulationResult, ...]
    expected_fault_cases: Annotated[int, Field(ge=0)]
    assessment: Assessment

    @model_validator(mode='after')
    def complete_coverage(self) -> Self:
        """Do not report an incomplete sweep as passing."""
        if self.expected_fault_cases != FAULT_CASES_PER_ECU * len(self.plan.steps):
            raise ValueError('Expected fault count must cover every planned ECU')
        if self.nominal.fault is not None or self.nominal.status != 'completed':
            raise ValueError('Nominal execution must complete without an injected fault')
        if self.campaign_id != self.plan.campaign_id or self.nominal.campaign_id != self.campaign_id:
            raise ValueError('Report campaign identities disagree')
        planned_ids = {step.ecu_id for step in self.plan.steps}
        if any(case.campaign_id != self.campaign_id or case.status != 'failed'
               or case.fault is None or case.fault.ecu_id not in planned_ids for case in self.cases):
            raise ValueError('Fault cases must fail with faults on this campaign plan')
        if len(self.cases) != self.expected_fault_cases:
            raise ValueError('Fault sweep is incomplete')
        if any(case.fault is None for case in self.cases):
            raise ValueError('Every stress case must identify its injected fault')
        if len({case.fault for case in self.cases}) != len(self.cases):
            raise ValueError('Duplicate injected fault case')
        assessments = (self.nominal.assessment, *(case.assessment for case in self.cases))
        expected = ('violations' if 'violations' in assessments else
                    'inconclusive' if 'inconclusive' in assessments else 'passed')
        if self.assessment != expected:
            raise ValueError('Stress assessment disagrees with execution results')
        return self
