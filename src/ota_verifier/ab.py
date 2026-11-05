"""Small immutable A/B image and active-slot operations."""
from .models import Campaign, ECUState, Image, Slot, VehicleState
from .versions import parse_version


def get_ecu(state: VehicleState, ecu_id: str) -> ECUState:
    """Get one runtime ECU or reject an unknown identity."""
    for ecu in state.ecus:
        if ecu.ecu_id == ecu_id:
            return ecu
    raise ValueError(f'Unknown ECU {ecu_id}')


def slot_image(ecu: ECUState, slot: Slot) -> Image | None:
    """Read the selected image, which may be empty or invalid."""
    return ecu.slot_a if slot == 'A' else ecu.slot_b


def _replace(state: VehicleState, replacement: ECUState) -> VehicleState:
    get_ecu(state, replacement.ecu_id)
    return VehicleState(ecus=tuple(replacement if ecu.ecu_id == replacement.ecu_id else ecu
                                   for ecu in state.ecus),
                        battery_percent=state.battery_percent, ignition=state.ignition)


def with_image(state: VehicleState, ecu_id: str, slot: Slot, image: Image | None) -> VehicleState:
    """Replace an image while preserving both active selection and other ECUs."""
    ecu = get_ecu(state, ecu_id)
    return _replace(state, ECUState(ecu_id=ecu_id,
        slot_a=image if slot == 'A' else ecu.slot_a,
        slot_b=image if slot == 'B' else ecu.slot_b, active_slot=ecu.active_slot))


def select_slot(state: VehicleState, ecu_id: str, slot: Slot) -> VehicleState:
    """Select a populated slot; callers must check bootability and authorization."""
    ecu = get_ecu(state, ecu_id)
    return _replace(state, ECUState(ecu_id=ecu_id, slot_a=ecu.slot_a,
                                   slot_b=ecu.slot_b, active_slot=slot))


def original_images_active(campaign: Campaign, state: VehicleState) -> bool:
    """Match original active slots/images; inactive contents need not be restored."""
    if {ecu.ecu_id for ecu in state.ecus} != {ecu.ecu_id for ecu in campaign.initial_state.ecus}:
        raise ValueError('Recovery state must cover exactly the campaign ECUs')
    for initial in campaign.initial_state.ecus:
        actual = get_ecu(state, initial.ecu_id)
        if (actual.active_slot != initial.active_slot or not actual.active_image.valid
                or parse_version(actual.active_image.version) != parse_version(initial.active_image.version)):
            return False
    return True
