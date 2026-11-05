"""Pure guarded-boot operations; version compatibility stays in compat.py."""
from typing import Any
from .ab import get_ecu, select_slot, slot_image, with_image
from .boot_models import BootMetadata, GuardedSnapshot, Health
from .compat import check_compatibility
from .invariants import check_transition
from .models import Campaign, Image, Requires, Slot, Violation
from .versions import matches


def initial_boot_state(campaign: Campaign) -> GuardedSnapshot:
    """Initialize confirmed/running originals; inactive boot health is unknown."""
    return GuardedSnapshot(state=campaign.initial_state, boot=tuple(BootMetadata(
        ecu_id=ecu.ecu_id, confirmed_slot=ecu.active_slot, candidate_slot=None,
        running_slot=ecu.active_slot, available=True,
        health_a=('passed' if ecu.slot_a and ecu.slot_a.valid else 'failed') if ecu.active_slot == 'A' else 'unknown',
        health_b=('passed' if ecu.slot_b and ecu.slot_b.valid else 'failed') if ecu.active_slot == 'B' else 'unknown',
    ) for ecu in campaign.initial_state.ecus))


def boot_metadata(snapshot: GuardedSnapshot, ecu_id: str) -> BootMetadata:
    """Return one ECU's boot state or reject unknown identities."""
    for metadata in snapshot.boot:
        if metadata.ecu_id == ecu_id:
            return metadata
    raise ValueError(f'Unknown boot ECU {ecu_id}')


def image_health(metadata: BootMetadata, slot: Slot) -> Health:
    """Read boot health independently of stored-image integrity."""
    return metadata.health_a if slot == 'A' else metadata.health_b


def change_boot(snapshot: GuardedSnapshot, ecu_id: str, **changes: Any) -> GuardedSnapshot:
    """Replace metadata through validation, never unchecked model_copy updates."""
    original = boot_metadata(snapshot, ecu_id)
    replacement = BootMetadata(**(original.model_dump() | changes))
    return GuardedSnapshot(state=snapshot.state, boot=tuple(
        replacement if metadata.ecu_id == ecu_id else metadata for metadata in snapshot.boot))


def set_image(snapshot: GuardedSnapshot, ecu_id: str, slot: Slot, image: Image,
              health: Health = 'unknown') -> GuardedSnapshot:
    """Set integrity/version contents and a separate observed boot-health state."""
    state = with_image(snapshot.state, ecu_id, slot, image)
    updated = GuardedSnapshot(state=state, boot=snapshot.boot)
    return change_boot(updated, ecu_id, **{'health_a' if slot == 'A' else 'health_b': health})


def power_loss(snapshot: GuardedSnapshot) -> GuardedSnapshot:
    """Clear volatile runtime/trial selection; preserve confirmed slots and counters."""
    result = snapshot
    for metadata in snapshot.boot:
        result = change_boot(result, metadata.ecu_id, available=False, running_slot=None, candidate_slot=None)
    return result


def check_guarded_state(campaign: Campaign, snapshot: GuardedSnapshot) -> tuple[Violation, ...]:
    """Check booted-image integrity/health and all known installed-version dependencies.

    Unavailable ECUs explicitly have no running image. Their last effective
    versions remain in compatibility checking; outages are not version changes.
    """
    findings = list(check_compatibility(campaign, snapshot.state))
    for metadata in snapshot.boot:
        if not metadata.available:
            continue
        ecu = get_ecu(snapshot.state, metadata.ecu_id)
        if not ecu.active_image.valid:
            findings.append(Violation(code='invalid_running_image', ecu_ids=(ecu.ecu_id,),
                actual_version=ecu.active_image.version, message='A running image failed integrity verification'))
        if image_health(metadata, ecu.active_slot) != 'passed':
            findings.append(Violation(code='unhealthy_running_image', ecu_ids=(ecu.ecu_id,),
                actual_version=ecu.active_image.version, message='A running image has no successful boot-health result'))
    return tuple(findings)


def guarded_boot(campaign: Campaign, snapshot: GuardedSnapshot, ecu_id: str, slot: Slot,
                 *, confirm: bool = False) -> tuple[GuardedSnapshot | None, tuple[Violation, ...]]:
    """Expose only a healthy compatible authorized image with available dependencies.

    Rejected candidates are returned as blockers, never applied transitions.
    Selecting the same retained effective version is not a downgrade.
    """
    metadata = boot_metadata(snapshot, ecu_id)
    image = slot_image(get_ecu(snapshot.state, ecu_id), slot)
    if image is None or not image.valid or image_health(metadata, slot) != 'passed':
        return None, (Violation(code='boot_image_unusable', ecu_ids=(ecu_id,),
            message='Boot selection needs an integrity-valid image with passed boot health'),)
    # Change projection and metadata together so an intermediate mismatch is
    # never constructed or accidentally emitted as an observed state.
    state = select_slot(snapshot.state, ecu_id, slot)
    replacement = BootMetadata(**(metadata.model_dump() | {
        'available': True, 'running_slot': slot, 'candidate_slot': None if confirm else slot,
        'confirmed_slot': slot if confirm else metadata.confirmed_slot}))
    candidate = GuardedSnapshot(state=state, boot=tuple(
        replacement if item.ecu_id == ecu_id else item for item in snapshot.boot))
    blockers = list(check_guarded_state(campaign, candidate))
    blockers.extend(check_transition(campaign, snapshot.state, candidate.state))
    available = {item.ecu_id: item.available for item in candidate.boot}
    for constraint in campaign.constraints:
        if (isinstance(constraint, Requires) and constraint.ecu == ecu_id
                and matches(image.version, constraint.version_spec) and not available[constraint.needs]):
            blockers.append(Violation(code='dependency_unavailable', ecu_ids=(ecu_id, constraint.needs),
                constraint_id=constraint.id, source_document_id=constraint.source_document_id,
                source_text=constraint.source_text, message='Dependent activation blocked while its required ECU is unavailable'))
    return (None, tuple(blockers)) if blockers else (candidate, ())


def confirm_current(snapshot: GuardedSnapshot, ecu_id: str) -> GuardedSnapshot:
    """Atomically persist the healthy running candidate as the confirmed slot."""
    metadata = boot_metadata(snapshot, ecu_id)
    ecu = get_ecu(snapshot.state, ecu_id)
    if (not metadata.available or not ecu.active_image.valid or image_health(metadata, ecu.active_slot) != 'passed'
            or metadata.candidate_slot not in (ecu.active_slot,) and metadata.confirmed_slot != ecu.active_slot):
        raise ValueError('Confirmation requires a successfully running healthy candidate')
    return change_boot(snapshot, ecu_id, confirmed_slot=ecu.active_slot, candidate_slot=None)
