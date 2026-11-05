"""Bounded guarded recovery over healthy existing slots and explicit availability."""
from collections import deque
from .ab import original_images_active
from .boot import boot_metadata, check_guarded_state, guarded_boot
from .boot_models import GuardedRecovery, GuardedRecoveryAction, GuardedSnapshot
from .invariants import check_transition
from .models import Campaign, Violation
from .simulation_models import SimulationOptions


def recovery_goal(campaign: Campaign, snapshot: GuardedSnapshot) -> bool:
    """Restore original effective images, running availability, and durable selection."""
    initial = {ecu.ecu_id: ecu.active_slot for ecu in campaign.initial_state.ecus}
    return (original_images_active(campaign, snapshot.state)
            and all(metadata.available and metadata.confirmed_slot == initial[metadata.ecu_id]
                    and metadata.candidate_slot is None for metadata in snapshot.boot)
            and not check_guarded_state(campaign, snapshot))


def _key(snapshot: GuardedSnapshot) -> tuple[tuple[object, ...], ...]:
    active = {ecu.ecu_id: ecu.active_slot for ecu in snapshot.state.ecus}
    return tuple((metadata.ecu_id, active[metadata.ecu_id], metadata.available,
                  metadata.confirmed_slot, metadata.candidate_slot)
                 for metadata in sorted(snapshot.boot, key=lambda item: item.ecu_id))


def check_guarded_recovery(campaign: Campaign, start: GuardedSnapshot,
                           result: GuardedRecovery) -> tuple[Violation, ...]:
    """Replay a claimed recovery; unknown remains inconclusive, not a violation proof."""
    if result.states[0] != start:
        return (Violation(code='rollback_path_invalid', ecu_ids=(), message='Guarded recovery starts from a different state'),)
    if result.status == 'unknown':
        return ()
    if result.status == 'unavailable':
        return (Violation(code='rollback_unavailable', ecu_ids=(), message=result.reason),)
    current = start
    findings: list[Violation] = []
    for index, action in enumerate(result.steps, 1):
        candidate, blockers = guarded_boot(campaign, current, action.ecu_id, action.slot, confirm=True)
        if candidate is None:
            return tuple(findings) + blockers + (Violation(code='rollback_path_invalid', ecu_ids=(action.ecu_id,),
                                                          message='Recovery action is not permitted'),)
        if candidate != result.states[index]:
            findings.append(Violation(code='rollback_path_invalid', ecu_ids=(action.ecu_id,), message='Recovery snapshot differs from replay'))
        findings.extend(check_guarded_state(campaign, candidate))
        findings.extend(check_transition(campaign, current.state, candidate.state))
        current = candidate
    if not recovery_goal(campaign, current):
        findings.append(Violation(code='rollback_goal_missing', ecu_ids=(), message='Original confirmed, running images were not restored'))
    return tuple(findings)


def find_guarded_recovery(campaign: Campaign, start: GuardedSnapshot,
                          options: SimulationOptions | None = None) -> GuardedRecovery:
    """Find a shortest authorized boot/confirm path using known healthy stored images.

    No image is fabricated or retried as healthy after a failed health result.
    Every successor preserves compatibility and authorization. Availability can
    return ECU by ECU, but a new dependent cannot boot before its required peer.
    """
    options = options or SimulationOptions()
    check_guarded_state(campaign, start)  # Also validates complete ECU coverage.
    queue = deque([(start, (), (start,))])
    visited = {_key(start)}
    examined = 0
    truncated = False
    blockers: dict[str, Violation] = {}
    while queue:
        current, actions, states = queue.popleft()
        examined += 1
        if recovery_goal(campaign, current):
            result = GuardedRecovery(status='available', states=states, steps=actions,
                examined_states=examined, reason='Original healthy confirmed images are running')
            if check_guarded_recovery(campaign, start, result):
                raise RuntimeError('Guarded recovery returned an invalid path')
            return result
        for metadata in sorted(current.boot, key=lambda item: item.ecu_id):
            slots = (metadata.confirmed_slot, 'B' if metadata.confirmed_slot == 'A' else 'A')
            for slot in slots:
                candidate, rejected = guarded_boot(campaign, current, metadata.ecu_id, slot, confirm=True)
                if candidate is None:
                    for blocker in rejected:
                        blockers.setdefault(blocker.model_dump_json(), blocker)
                    continue
                key = _key(candidate)
                if key in visited:
                    continue
                if len(visited) >= options.max_recovery_states:
                    truncated = True
                    continue
                visited.add(key)
                action = GuardedRecoveryAction(ecu_id=metadata.ecu_id, slot=slot)
                queue.append((candidate, actions + (action,), states + (candidate,)))
    return GuardedRecovery(status='unknown' if truncated else 'unavailable', states=(start,),
        examined_states=examined, blockers=tuple(blockers.values()),
        reason='Guarded recovery state limit reached' if truncated else
               'No healthy, compatible, authorized boot path restores original confirmed images')
