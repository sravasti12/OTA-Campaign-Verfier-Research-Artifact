"""Independent bounded schedule enumeration, sharing only the domain compatibility rule."""
from itertools import combinations, permutations, product
from ..compat import check_compatibility
from ..models import Campaign, ECUState, Image, Mutex, Order, PlanningOptions, Precondition, VehicleState


def exhaustive_optimum(campaign: Campaign, options: PlanningOptions) -> int | None:
    """Return the exact optimum for at most three monotonic integer-minute updates.

    Enumerates interval starts and activation permutations without Z3, production
    scheduling helpers, or the production plan validator. Compatibility remains
    defined once in compat.py. Unsupported inputs fail rather than approximating.
    Integer durations/bounds give integer difference constraints for each fixed
    ordering, so an optimum exists on this finite minute lattice.
    """
    if len(campaign.ecus) > 3 or any(ecu.current_version != '1' or ecu.target_version not in ('1', '2')
        or not ecu.flash_minutes.is_integer() or not 1 <= ecu.flash_minutes <= 2 for ecu in campaign.ecus):
        raise ValueError('Oracle supports at most three 1-to-2/no-op ECUs with one/two-minute durations')
    if options.deadline_ms is not None and options.deadline_ms % 60000:
        raise ValueError('Oracle deadlines must be integral minutes')
    if any(not ecu.active_image.valid for ecu in campaign.initial_state.ecus):
        raise ValueError('Oracle requires initially valid images')
    if check_compatibility(campaign, campaign.initial_state):
        return None
    durations = {ecu.id: int(ecu.flash_minutes) for ecu in campaign.ecus if ecu.target_version != ecu.current_version}
    if any(isinstance(rule, Precondition) and rule.ecu in durations and (
        campaign.initial_state.ignition != rule.ignition or campaign.initial_state.battery_percent < rule.minimum_battery_percent)
        for rule in campaign.constraints):
        return None
    if not durations:
        return 0
    names = tuple(durations)
    horizon = sum(durations.values())
    best: int | None = None
    for order in permutations(names):
        versions = {ecu.id: '1' for ecu in campaign.ecus}
        compatible = True
        for name in order:
            versions[name] = '2'
            observation = VehicleState(ecus=tuple(ECUState(ecu_id=key, slot_a=Image(version=value), slot_b=None, active_slot='A')
                for key, value in versions.items()), battery_percent=campaign.initial_state.battery_percent, ignition=campaign.initial_state.ignition)
            if check_compatibility(campaign, observation):
                compatible = False
                break
        if not compatible:
            continue
        for starts_tuple in product(*(range(horizon - durations[name] + 1) for name in names)):
            starts = dict(zip(names, starts_tuple, strict=True))
            ends = {name: starts[name] + durations[name] for name in names}
            span = max(ends.values()) * 60000
            if (best is not None and span >= best) or (options.deadline_ms is not None and span > options.deadline_ms):
                continue
            if any(ends[a] > ends[b] for a, b in zip(order, order[1:])):
                continue
            if options.max_parallel is not None and any(sum(starts[name] <= moment < ends[name] for name in names) > options.max_parallel for moment in starts.values()):
                continue
            invalid = False
            for rule in campaign.constraints:
                if isinstance(rule, Order) and rule.before in names and rule.after in names:
                    invalid |= ends[rule.before] > starts[rule.after]
                elif isinstance(rule, Mutex):
                    invalid |= any(starts[a] < ends[b] and starts[b] < ends[a]
                        for a, b in combinations((name for name in rule.ecus if name in names), 2))
            if not invalid:
                best = span
    return best
