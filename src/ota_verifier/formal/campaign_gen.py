"""Seeded generator of synthetic N-ECU campaigns with random acyclic dependencies.

The graphs are synthetic. They are not drawn from any real vehicle architecture.
"""
import random
from ..models import Campaign, ECU, ECUState, Image, Requires, VehicleState

# Each ECU depends on 0, 1 or 2 earlier ECUs, so every graph is acyclic.
DEPENDENCY_COUNTS = (0, 1, 2)
DEPENDENCY_WEIGHTS = (0.4, 0.4, 0.2)


def ecu_names(size: int) -> tuple[str, ...]:
    """Name ECUs in order."""
    return tuple(f'ecu{index:02d}' for index in range(size))


def random_edges(size: int, seed: int) -> tuple[tuple[str, str], ...]:
    """Return (dependent, dependency) pairs of a random DAG, fixed by size and seed."""
    rng = random.Random(f'{size}:{seed}')
    names = ecu_names(size)
    edges = []
    for index, name in enumerate(names):
        count = rng.choices(DEPENDENCY_COUNTS, DEPENDENCY_WEIGHTS)[0]
        for target in sorted(rng.sample(range(index), min(count, index))):
            edges.append((name, names[target]))
    return tuple(edges)


def generate(size: int, seed: int) -> Campaign:
    """Build a schema-valid campaign, so it is also usable by the planner and simulator."""
    if size < 2:
        raise ValueError('A campaign needs at least two ECUs')
    names = ecu_names(size)
    ecus = tuple(ECU(id=name, current_version='1', target_version='2', flash_minutes=1.0) for name in names)
    states = tuple(ECUState(ecu_id=name, slot_a=Image(version='1'), slot_b=None, active_slot='A') for name in names)
    constraints = tuple(
        Requires(id=f'{dependent}-needs-{dependency}', source_document_id='synthetic',
                 source_text='Generated synthetic dependency.', ecu=dependent, version_spec='>=2',
                 needs=dependency, needs_version_spec='>=2')
        for dependent, dependency in random_edges(size, seed))
    return Campaign(id=f'generated-n{size}-s{seed}', ecus=ecus,
                    initial_state=VehicleState(ecus=states, battery_percent=80, ignition='off'),
                    constraints=constraints)


def edges_of(campaign: Campaign) -> tuple[tuple[str, str], ...]:
    """Read dependency edges back from a campaign."""
    return tuple((rule.ecu, rule.needs) for rule in campaign.constraints if isinstance(rule, Requires))


def is_acyclic(names: tuple[str, ...], edges: tuple[tuple[str, str], ...]) -> bool:
    """Check acyclicity independently of how the generator builds its graphs."""
    remaining = set(names)
    while remaining:
        free = {name for name in remaining
                if not any(dependent == name and dependency in remaining for dependent, dependency in edges)}
        if not free:
            return False
        remaining -= free
    return True


def tla_set(values: tuple[str, ...]) -> str:
    """Render ECU names as a TLA+ set."""
    return '{' + ', '.join(f'"{value}"' for value in values) + '}'


def tla_edges(edges: tuple[tuple[str, str], ...]) -> str:
    """Render dependency edges as a TLA+ set of tuples."""
    return '{' + ', '.join(f'<<"{a}", "{b}">>' for a, b in edges) + '}'
