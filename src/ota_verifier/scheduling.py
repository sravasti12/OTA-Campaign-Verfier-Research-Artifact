"""Pure nominal scheduling helpers and independent concrete plan validation."""
from decimal import Decimal, ROUND_CEILING
from itertools import combinations
from .compat import check_compatibility
from .models import (
    Campaign, Constraint, ECU, ECUState, Image, Mutex, Order, Plan, PlanStep,
    Precondition, Requires, VehicleState, Violation,
)
from .versions import parse_version
from .policy import version_change_allowed


def duration_ms(ecu: ECU) -> int:
    """Convert minutes to milliseconds, rounding upward to avoid understatement."""
    return int((Decimal(str(ecu.flash_minutes)) * 60_000).to_integral_value(rounding=ROUND_CEILING))


def constraint_ecus(constraint: Constraint) -> tuple[str, ...]:
    """Return ECU references in a domain constraint."""
    if isinstance(constraint, Requires):
        return (constraint.ecu, constraint.needs)
    if isinstance(constraint, Mutex):
        return constraint.ecus
    if isinstance(constraint, Order):
        return (constraint.before, constraint.after)
    return (constraint.ecu,)


def downgrade_allowed(campaign: Campaign, ecu: ECU) -> bool:
    """Require exact ECU and numeric destination-version permission for downgrades."""
    return version_change_allowed(campaign, ecu.id, ecu.current_version, ecu.target_version)


def activate_target(state: VehicleState, ecu: ECU) -> VehicleState:
    """Project a successful inactive-slot write and activation, without fault simulation."""
    projected: list[ECUState] = []
    for current in state.ecus:
        if current.ecu_id != ecu.id:
            projected.append(current)
            continue
        target = Image(version=ecu.target_version, valid=True)
        projected.append(ECUState(
            ecu_id=ecu.id, slot_a=target if current.active_slot == 'B' else current.slot_a,
            slot_b=target if current.active_slot == 'A' else current.slot_b,
            active_slot='B' if current.active_slot == 'A' else 'A',
        ))
    if ecu.id not in {current.ecu_id for current in state.ecus}:
        raise ValueError(f'Missing ECU {ecu.id}')
    return VehicleState(ecus=tuple(projected), battery_percent=state.battery_percent, ignition=state.ignition)


def _finding(code: str, message: str, ecus: tuple[str, ...] = ()) -> Violation:
    return Violation(code=code, message=message, ecu_ids=ecus)


def _step_findings(campaign: Campaign, step: PlanStep) -> list[Violation]:
    ecu = next(ecu for ecu in campaign.ecus if ecu.id == step.ecu_id)
    initial = next(state for state in campaign.initial_state.ecus if state.ecu_id == ecu.id)
    expected_slot = 'B' if initial.active_slot == 'A' else 'A'
    expected_constraints = tuple(c.id for c in campaign.constraints if ecu.id in constraint_ecus(c))
    findings: list[Violation] = []
    if (step.from_version != ecu.current_version or step.to_version != ecu.target_version
            or step.write_slot != expected_slot or step.constraint_ids != expected_constraints):
        findings.append(_finding('step_metadata', 'Step metadata does not match campaign', (ecu.id,)))
    if step.end_ms - step.start_ms != duration_ms(ecu):
        findings.append(_finding('flash_duration', 'Incorrect flash duration', (ecu.id,)))
    if not downgrade_allowed(campaign, ecu):
        findings.append(_finding('unauthorized_downgrade', 'Downgrade lacks scoped authorization', (ecu.id,)))
    return findings


def _constraint_findings(campaign: Campaign, steps: dict[str, PlanStep]) -> list[Violation]:
    findings: list[Violation] = []
    for constraint in campaign.constraints:
        failed = False
        if isinstance(constraint, Order) and constraint.before in steps and constraint.after in steps:
            failed = steps[constraint.before].end_ms > steps[constraint.after].start_ms
        elif isinstance(constraint, Mutex):
            members = [steps[ecu] for ecu in constraint.ecus if ecu in steps]
            failed = any(a.start_ms < b.end_ms and b.start_ms < a.end_ms
                         for a, b in combinations(members, 2))
        elif isinstance(constraint, Precondition) and constraint.ecu in steps:
            state = campaign.initial_state
            failed = (state.ignition != constraint.ignition
                      or state.battery_percent < constraint.minimum_battery_percent)
        if failed:
            findings.append(Violation(
                code='schedule_constraint', ecu_ids=constraint_ecus(constraint),
                message=f'Schedule violates {constraint.type}', constraint_id=constraint.id,
                source_document_id=constraint.source_document_id, source_text=constraint.source_text,
            ))
    return findings


def validate_plan(campaign: Campaign, plan: Plan) -> tuple[Violation, ...]:
    """Replay and validate a nominal plan without invoking Z3 or an LLM.

    This validates the schedule and its projected states, not fault tolerance.
    An invalid ECU set is reported before attempting state reconstruction.
    """
    changed = {ecu.id: ecu for ecu in campaign.ecus
               if parse_version(ecu.current_version) != parse_version(ecu.target_version)}
    steps = {step.ecu_id: step for step in plan.steps}
    if set(steps) != set(changed) or plan.campaign_id != campaign.id:
        return (_finding('plan_identity', 'Plan must cover exactly the changed campaign ECUs'),)
    findings: list[Violation] = []
    if plan.states[0] != campaign.initial_state:
        findings.append(_finding('initial_state', 'Plan initial state differs from campaign'))
    for state in campaign.initial_state.ecus:
        if not state.active_image.valid:
            findings.append(_finding('invalid_active_image', 'Initial active image is invalid', (state.ecu_id,)))
    state = campaign.initial_state
    findings.extend(check_compatibility(campaign, state))
    previous_end = 0
    for index, step in enumerate(plan.steps, start=1):
        findings.extend(_step_findings(campaign, step))
        if step.end_ms < previous_end:
            findings.append(_finding('activation_order', 'Activations must follow completion time'))
        previous_end = step.end_ms
        state = activate_target(state, changed[step.ecu_id])
        if state != plan.states[index]:
            findings.append(_finding('projected_state', 'Recorded activation state differs from replay', (step.ecu_id,)))
        findings.extend(check_compatibility(campaign, state))
    findings.extend(_constraint_findings(campaign, steps))
    options = plan.options
    if options.deadline_ms is not None and plan.makespan_ms > options.deadline_ms:
        findings.append(_finding('deadline', 'Schedule exceeds campaign deadline'))
    if options.max_parallel is not None:
        for step in plan.steps:
            active = sum(other.start_ms <= step.start_ms < other.end_ms for other in plan.steps)
            if active > options.max_parallel:
                findings.append(_finding('capacity', 'Schedule exceeds parallel flash limit'))
                break
    return tuple(findings)
