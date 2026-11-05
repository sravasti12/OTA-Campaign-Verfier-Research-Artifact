"""Pure safety-invariant checks for simulation states, transitions, and recovery."""
from .ab import get_ecu, original_images_active, select_slot, slot_image
from .compat import check_compatibility
from .models import Campaign, VehicleState, Violation
from .policy import version_change_allowed
from .simulation_models import RecoveryResult
from .versions import parse_version


def check_state(campaign: Campaign, state: VehicleState) -> tuple[Violation, ...]:
    """Check active-image bootability and shared active-version compatibility."""
    compatibility = check_compatibility(campaign, state)
    boot = tuple(Violation(code='invalid_active_image', ecu_ids=(ecu.ecu_id,),
        message='Selected active image is not bootable in this simulation',
        actual_version=ecu.active_image.version)
        for ecu in state.ecus if not ecu.active_image.valid)
    return boot + compatibility


def check_transition(campaign: Campaign, before: VehicleState, after: VehicleState) -> tuple[Violation, ...]:
    """Check authorization of active downgrades and newly valid installed images.

    Preexisting older inactive images are not installations. An image becomes
    installed when marked valid after verification, or when selected for boot.
    """
    expected = {ecu.id for ecu in campaign.ecus}
    if {ecu.ecu_id for ecu in before.ecus} != expected or {ecu.ecu_id for ecu in after.ecus} != expected:
        raise ValueError('Transition must cover exactly the campaign ECUs')
    findings: list[Violation] = []
    for current in after.ecus:
        previous = get_ecu(before, current.ecu_id)
        destinations: set[str] = set()
        if (current.active_slot != previous.active_slot
                or parse_version(current.active_image.version) != parse_version(previous.active_image.version)):
            destinations.add(current.active_image.version)
        for slot in ('A', 'B'):
            old_image, new_image = slot_image(previous, slot), slot_image(current, slot)
            if new_image is not None and new_image.valid and (
                old_image is None or not old_image.valid
                or parse_version(old_image.version) != parse_version(new_image.version)
            ):
                destinations.add(new_image.version)
        for version in sorted(destinations):
            if not version_change_allowed(campaign, current.ecu_id, previous.active_image.version, version):
                findings.append(Violation(code='unauthorized_downgrade', ecu_ids=(current.ecu_id,),
                    actual_version=version, message=f'Installing or activating {version} from '
                    f'{previous.active_image.version} needs explicit ECU/version authorization'))
    return tuple(findings)


def check_recovery_path(campaign: Campaign, start: VehicleState, recovery: RecoveryResult) -> tuple[Violation, ...]:
    """Validate a reported rollback path, preserving unknown as inconclusive.

    Each executed recovery action must produce a bootable compatible state.
    The initial failed state can itself violate invariants; recovery does not
    erase those historical findings.
    """
    if recovery.states[0] != start:
        return (Violation(code='rollback_path_invalid', ecu_ids=(), message='Recovery starts from the wrong state'),)
    if recovery.status == 'unknown':
        return ()
    if recovery.status == 'unavailable':
        return (Violation(code='rollback_unavailable', ecu_ids=(), message=recovery.reason),)
    findings: list[Violation] = []
    state = start
    for index, action in enumerate(recovery.steps, start=1):
        try:
            previous = get_ecu(state, action.ecu_id)
            image = slot_image(previous, action.to_slot)
            if (action.from_slot != previous.active_slot or action.from_version != previous.active_image.version
                    or image is None or action.to_version != image.version):
                raise ValueError('Recovery metadata disagrees with current slot contents')
            projected = select_slot(state, action.ecu_id, action.to_slot)
        except ValueError as error:
            findings.append(Violation(code='rollback_path_invalid', ecu_ids=(action.ecu_id,), message=str(error)))
            return tuple(findings)
        if projected != recovery.states[index]:
            findings.append(Violation(code='rollback_path_invalid', ecu_ids=(action.ecu_id,),
                                      message='Recorded recovery state differs from slot-switch replay'))
        findings.extend(check_state(campaign, projected))
        findings.extend(check_transition(campaign, state, projected))
        state = projected
    if not original_images_active(campaign, state):
        findings.append(Violation(code='rollback_goal_missing', ecu_ids=(),
                                  message='Recovery did not restore original active slots and versions'))
    findings.extend(check_state(campaign, state))
    return tuple(findings)
