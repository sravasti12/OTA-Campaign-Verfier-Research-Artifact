"""Validated immutable input and runtime records for the OTA simulation."""
from typing import Annotated, Literal, Self
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator
from .versions import parse_spec, parse_version


def _version(value: str) -> str:
    parse_version(value)
    return value


def _spec(value: str) -> str:
    parse_spec(value)
    return value

Version = Annotated[str, AfterValidator(_version)]
VersionSpec = Annotated[str, AfterValidator(_spec)]
Identifier = Annotated[str, Field(min_length=1, pattern=r'\S')]
Slot = Literal['A', 'B']
Ignition = Literal['off', 'accessory', 'on']


class Record(BaseModel):
    """Strict immutable records; nested collections are tuples."""
    model_config = ConfigDict(extra='forbid', frozen=True, strict=True)


class Image(Record):
    """Simulated image validity; this is not cryptographic verification."""
    version: Version
    valid: bool = True


class ECU(Record):
    """Static ECU configuration; slots live in ECUState."""
    id: Identifier
    current_version: Version
    target_version: Version
    flash_minutes: Annotated[float, Field(gt=0, allow_inf_nan=False)]


class ECUState(Record):
    """Runtime slots permit invalid images so faults can be represented."""
    ecu_id: Identifier
    slot_a: Image | None
    slot_b: Image | None
    active_slot: Slot

    @model_validator(mode='after')
    def check_active_slot(self) -> Self:
        """Require a populated active slot."""
        if (self.slot_a if self.active_slot == 'A' else self.slot_b) is None:
            raise ValueError('Active slot must contain an image')
        return self

    @property
    def active_image(self) -> Image:
        """Return the populated active image, including its validity flag."""
        image = self.slot_a if self.active_slot == 'A' else self.slot_b
        assert image is not None
        return image


class VehicleState(Record):
    """Complete vehicle observation."""
    ecus: tuple[ECUState, ...]
    battery_percent: Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]
    ignition: Ignition

    @model_validator(mode='after')
    def check_ids(self) -> Self:
        """Reject duplicate runtime IDs."""
        ids = [ecu.ecu_id for ecu in self.ecus]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate runtime ECU IDs')
        return self


class SourceConstraint(Record):
    """Constraint identity and document evidence."""
    id: Identifier
    source_document_id: Identifier
    source_text: Identifier


class Requires(SourceConstraint):
    """A matching active ECU version requires a matching peer version."""
    type: Literal['requires'] = 'requires'
    ecu: Identifier
    version_spec: VersionSpec
    needs: Identifier
    needs_version_spec: VersionSpec


class Mutex(SourceConstraint):
    """ECUs forbidden from flashing concurrently."""
    type: Literal['mutex'] = 'mutex'
    ecus: Annotated[tuple[Identifier, ...], Field(min_length=2)]

    @model_validator(mode='after')
    def check_members(self) -> Self:
        """Require distinct members."""
        if len(set(self.ecus)) != len(self.ecus):
            raise ValueError('Duplicate mutex member')
        return self


class Precondition(SourceConstraint):
    """Required environment before flashing an ECU."""
    type: Literal['precondition'] = 'precondition'
    ecu: Identifier
    ignition: Ignition
    minimum_battery_percent: Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]


class Order(SourceConstraint):
    """Directed flash precedence."""
    type: Literal['order'] = 'order'
    before: Identifier
    after: Identifier

    @model_validator(mode='after')
    def check_endpoints(self) -> Self:
        """Reject self ordering."""
        if self.before == self.after:
            raise ValueError('An ECU cannot precede itself')
        return self


Constraint = Annotated[Requires | Mutex | Precondition | Order, Field(discriminator='type')]


class DowngradeAuthorization(Record):
    """Permission scoped to one ECU and destination version."""
    ecu_id: Identifier
    version: Version
    authorized_by: Identifier
    reason: Identifier


class Campaign(Record):
    """Validated input; compatibility is evaluated separately."""
    id: Identifier
    ecus: Annotated[tuple[ECU, ...], Field(min_length=1)]
    initial_state: VehicleState
    constraints: tuple[Constraint, ...] = ()
    downgrade_authorizations: tuple[DowngradeAuthorization, ...] = ()

    @model_validator(mode='after')
    def check_references(self) -> Self:
        """Validate IDs, complete state coverage, versions, and ECU references."""
        ids = {ecu.id for ecu in self.ecus}
        if len(ids) != len(self.ecus):
            raise ValueError('Duplicate ECU IDs')
        if {ecu.ecu_id for ecu in self.initial_state.ecus} != ids:
            raise ValueError('Initial state must cover exactly the campaign ECUs')
        configured = {ecu.id: ecu for ecu in self.ecus}
        for state in self.initial_state.ecus:
            if parse_version(state.active_image.version) != parse_version(configured[state.ecu_id].current_version):
                raise ValueError('Current version disagrees with active image')
        if len({c.id for c in self.constraints}) != len(self.constraints):
            raise ValueError('Duplicate constraint IDs')
        for constraint in self.constraints:
            if isinstance(constraint, Requires):
                references = {constraint.ecu, constraint.needs}
            elif isinstance(constraint, Mutex):
                references = set(constraint.ecus)
            elif isinstance(constraint, Precondition):
                references = {constraint.ecu}
            else:
                references = {constraint.before, constraint.after}
            if not references <= ids:
                raise ValueError(f'Unknown ECU reference in {constraint.id}')
        if any(a.ecu_id not in ids for a in self.downgrade_authorizations):
            raise ValueError('Unknown ECU in downgrade authorization')
        return self


class Violation(Record):
    """Machine readable finding with source evidence."""
    code: Identifier
    ecu_ids: tuple[str, ...]
    message: str
    constraint_id: str | None = None
    source_document_id: str | None = None
    source_text: str | None = None
    actual_version: str | None = None
    expected_version_spec: str | None = None


class PlanningOptions(Record):
    """Resource assumptions and a total solver-work budget in milliseconds."""
    max_parallel: Annotated[int, Field(gt=0)] | None = None
    deadline_ms: Annotated[int, Field(ge=0)] | None = None
    timeout_ms: Annotated[int, Field(gt=0)] = 10_000


class PlanStep(Record):
    """One inactive-slot write followed by an instantaneous activation."""
    ecu_id: Identifier
    from_version: Version
    to_version: Version
    write_slot: Slot
    start_ms: Annotated[int, Field(ge=0)]
    end_ms: Annotated[int, Field(gt=0)]
    activation_index: Annotated[int, Field(gt=0)]
    constraint_ids: tuple[str, ...] = ()

    @model_validator(mode='after')
    def positive_interval(self) -> Self:
        """Require a positive write interval."""
        if self.end_ms <= self.start_ms:
            raise ValueError('Flash end must follow start')
        return self


class Plan(Record):
    """Nominal schedule with concrete states after each ordered activation."""
    campaign_id: Identifier
    steps: tuple[PlanStep, ...]
    states: tuple[VehicleState, ...]
    makespan_ms: Annotated[int, Field(ge=0)]
    optimal: bool
    options: PlanningOptions

    @model_validator(mode='after')
    def consistent_shape(self) -> Self:
        """Require ordered unique steps, one initial state, and exact makespan."""
        if len(self.states) != len(self.steps) + 1:
            raise ValueError('Plan needs initial state and one state per activation')
        if tuple(s.activation_index for s in self.steps) != tuple(range(1, len(self.steps) + 1)):
            raise ValueError('Steps must be in contiguous activation order')
        if len({s.ecu_id for s in self.steps}) != len(self.steps):
            raise ValueError('Duplicate planned ECU')
        if self.makespan_ms != max((s.end_ms for s in self.steps), default=0):
            raise ValueError('Incorrect makespan')
        return self


class ConflictItem(Record):
    """One source requirement or explicit planning policy in an unsat core."""
    kind: Literal['constraint', 'policy', 'resource']
    id: Identifier
    message: str
    ecu_ids: tuple[str, ...] = ()
    source_document_id: str | None = None
    source_text: str | None = None


class ConflictReport(Record):
    """Conflict relative to fixed transition semantics, not a suggested waiver."""
    items: Annotated[tuple[ConflictItem, ...], Field(min_length=1)]
    subset_minimal: bool


class FeasibleResult(Record):
    """A replay-validated nominal plan; optimality is reported separately."""
    status: Literal['feasible'] = 'feasible'
    plan: Plan
    note: str | None = None


class InfeasibleResult(Record):
    """A proven contradiction with traceable conflict evidence."""
    status: Literal['infeasible'] = 'infeasible'
    conflict: ConflictReport
    note: str | None = None


class UnknownResult(Record):
    """No feasibility verdict was established within the solver budget."""
    status: Literal['unknown'] = 'unknown'
    reason: str


PlanningResult = Annotated[FeasibleResult | InfeasibleResult | UnknownResult,
                           Field(discriminator='status')]
