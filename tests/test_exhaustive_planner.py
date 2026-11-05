"""Compare Z3 feasibility and optimum against exhaustive tiny schedules."""
from itertools import permutations, product
import random
import pytest
from ota_verifier.compat import check_compatibility
from ota_verifier.models import Campaign, ECUState, FeasibleResult, Image, InfeasibleResult, Mutex, Order, PlanningOptions, VehicleState
from ota_verifier.planner import plan_campaign
from test_planner import add_constraint, campaign_data, load_campaign


def _compatible_order(campaign: Campaign, order: tuple[str, ...]) -> bool:
    versions = {ecu.id: ecu.current_version for ecu in campaign.ecus}
    targets = {ecu.id: ecu.target_version for ecu in campaign.ecus}
    for ecu_id in order:
        versions[ecu_id] = targets[ecu_id]
        # Build version observations independently of planner transition helpers.
        state = VehicleState(ecus=tuple(ECUState(ecu_id=key, slot_a=Image(version=version),
            slot_b=None, active_slot='A') for key, version in versions.items()),
            battery_percent=80, ignition='off')
        if check_compatibility(campaign, state):
            return False
    return not check_compatibility(campaign, campaign.initial_state)


def _exhaustive_optimum(campaign: Campaign, options: PlanningOptions) -> int | None:
    """Enumerate all starts and activation orders on the integer-minute lattice.

    These cases have integer-minute durations and deadlines. For a fixed interval
    ordering all bounds are integer difference constraints, so this lattice
    contains an optimum. No Z3 or production schedule validator is used here.
    """
    durations = {ecu.id: int(ecu.flash_minutes) for ecu in campaign.ecus}
    names = tuple(durations)
    horizon = sum(durations.values())
    best: int | None = None
    for order in permutations(names):
        if not _compatible_order(campaign, order):
            continue
        for values in product(*(range(horizon - durations[name] + 1) for name in names)):
            starts = dict(zip(names, values))
            ends = {name: starts[name] + durations[name] for name in names}
            span = max(ends.values()) * 60_000
            if best is not None and span >= best:
                continue
            if options.deadline_ms is not None and span > options.deadline_ms:
                continue
            if any(ends[a] > ends[b] for a, b in zip(order, order[1:])):
                continue
            if options.max_parallel is not None and any(
                sum(starts[name] <= moment < ends[name] for name in names) > options.max_parallel
                for moment in starts.values()
            ):
                continue
            violated = False
            for constraint in campaign.constraints:
                if isinstance(constraint, Order):
                    violated |= ends[constraint.before] > starts[constraint.after]
                elif isinstance(constraint, Mutex):
                    violated |= any(starts[a] < ends[b] and starts[b] < ends[a]
                        for a, b in permutations(constraint.ecus, 2))
            if not violated:
                best = span
    return best


@pytest.mark.parametrize('seed', range(24))
def test_solver_agrees_with_exhaustive_schedules(seed: int) -> None:
    rng = random.Random(seed)
    data = campaign_data(tuple(rng.randint(1, 2) for _ in range(3)))
    names = ('a', 'b', 'c')
    for index in range(rng.randint(0, 3)):
        ecu, needs = rng.sample(names, 2)
        spec = rng.choice(['>=2', '<=1'])
        add_constraint(data, 'requires', f'dependency-{index}', ecu=ecu, version_spec=spec,
                       needs=needs, needs_version_spec=spec)
    if seed % 2 == 0:
        a, b = rng.sample(names, 2)
        add_constraint(data, 'mutex', 'shared-channel', ecus=[a, b])
    if seed % 3 == 0:
        a, b = rng.sample(names, 2)
        add_constraint(data, 'order', 'precedence', before=a, after=b)
    options = PlanningOptions(max_parallel=rng.choice([None, 1, 2]),
        deadline_ms=None if seed % 4 else rng.randint(1, 4) * 60_000)
    campaign = load_campaign(data)
    expected = _exhaustive_optimum(campaign, options)
    result = plan_campaign(campaign, options)
    if expected is None:
        assert isinstance(result, InfeasibleResult), (seed, result)
    else:
        assert isinstance(result, FeasibleResult), (seed, result)
        assert result.plan.optimal
        assert result.plan.makespan_ms == expected
