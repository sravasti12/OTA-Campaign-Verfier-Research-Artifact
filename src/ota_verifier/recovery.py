"""Bounded breadth-first search over existing A/B slot selections only."""
from collections import deque
from .ab import original_images_active, select_slot, slot_image
from .compat import check_compatibility
from .invariants import check_recovery_path, check_state, check_transition
from .models import Campaign, VehicleState, Violation
from .simulation_models import RecoveryResult, RecoveryStep, SimulationOptions


def _key(state: VehicleState) -> tuple[str, ...]:
    return tuple(ecu.active_slot for ecu in sorted(state.ecus, key=lambda ecu: ecu.ecu_id))


def find_recovery(campaign: Campaign, start: VehicleState,
                  options: SimulationOptions | None = None) -> RecoveryResult:
    """Find a shortest authorized, compatible slot path to original active images.

    No new images are downloaded, repaired, or fabricated. The starting state
    may be faulted; every successor must be fully bootable and compatible.
    Exhausting a state limit yields unknown, never a no-path proof.
    """
    options = options or SimulationOptions()
    check_compatibility(campaign, start)  # Fail closed on incomplete state coverage.
    frontier: deque[tuple[VehicleState, tuple[RecoveryStep, ...], tuple[VehicleState, ...]]] = deque()
    frontier.append((start, (), (start,)))
    visited = {_key(start)}
    blockers: dict[str, Violation] = {}
    examined = 0
    truncated = False
    while frontier:
        state, actions, states = frontier.popleft()
        examined += 1
        if original_images_active(campaign, state) and not check_state(campaign, state):
            result = RecoveryResult(status='available', states=states, steps=actions,
                examined_states=examined, reason='Original active images restored by validated slot switches')
            if check_recovery_path(campaign, start, result):
                raise RuntimeError('Internal recovery search returned an invalid path')
            return result
        for ecu in sorted(state.ecus, key=lambda ecu: ecu.ecu_id):
            destination = 'B' if ecu.active_slot == 'A' else 'A'
            image = slot_image(ecu, destination)
            if image is None or not image.valid:
                blocker = Violation(code='rollback_image_unusable', ecu_ids=(ecu.ecu_id,),
                    message=f'Fallback slot {destination} has no valid image')
                blockers.setdefault(blocker.model_dump_json(), blocker)
                continue
            candidate = select_slot(state, ecu.ecu_id, destination)
            key = _key(candidate)
            if key in visited:
                continue
            rejected = check_state(campaign, candidate) + check_transition(campaign, state, candidate)
            if rejected:
                for blocker in rejected:
                    blockers.setdefault(blocker.model_dump_json(), blocker)
                continue
            if len(visited) >= options.max_recovery_states:
                truncated = True
                continue
            visited.add(key)
            action = RecoveryStep(ecu_id=ecu.ecu_id, from_slot=ecu.active_slot, to_slot=destination,
                                  from_version=ecu.active_image.version, to_version=image.version)
            frontier.append((candidate, actions + (action,), states + (candidate,)))
    return RecoveryResult(status='unknown' if truncated else 'unavailable', states=(start,),
        examined_states=examined, blockers=tuple(blockers.values()),
        reason='Recovery state limit reached' if truncated else
               'No bootable, compatible, authorized slot-switch path restores original active images')
