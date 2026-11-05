"""Independent all-pairs oracle for small guarded recovery state spaces."""
import random
import pytest
from ota_verifier.boot_models import BootMetadata, GuardedSnapshot
from ota_verifier.boot_recovery import find_guarded_recovery
from ota_verifier.compat import check_compatibility
from ota_verifier.models import ECUState, Image, VehicleState
from ota_verifier.versions import matches
from test_planner import add_constraint, campaign_data, load_campaign


@pytest.mark.parametrize('seed', range(10))
def test_guarded_recovery_matches_exhaustive_availability_graph(seed: int) -> None:
    rng = random.Random(seed)
    data = campaign_data((1, 1))
    permissions = rng.randrange(4)
    data['downgrade_authorizations'] = [dict(ecu_id=name, version='1', authorized_by='reviewer', reason='Oracle case')
        for bit, name in enumerate(('a', 'b')) if permissions & (1 << bit)]
    for index in range(rng.randrange(4)):
        source, needs = rng.sample(('a', 'b'), 2)
        spec = rng.choice(('>=1', '>=2', '<=1'))
        add_constraint(data, 'requires', f'req-{index}', ecu=source, version_spec=spec, needs=needs, needs_version_spec=spec)
    campaign = load_campaign(data)
    snapshots = []
    for mask in range(64):
        ecus, metadata = [], []
        for index, name in enumerate(('a', 'b')):
            active = 'B' if mask & (1 << (3 * index)) else 'A'
            available = bool(mask & (1 << (3 * index + 1)))
            confirmed = 'B' if mask & (1 << (3 * index + 2)) else 'A'
            ecus.append(ECUState(ecu_id=name, slot_a=Image(version='1'), slot_b=Image(version='2'), active_slot=active))
            metadata.append(BootMetadata(ecu_id=name, confirmed_slot=confirmed, available=available,
                running_slot=active if available else None, candidate_slot=None, health_a='passed', health_b='passed'))
        snapshots.append(GuardedSnapshot(state=VehicleState(ecus=tuple(ecus), battery_percent=80, ignition='off'), boot=tuple(metadata)))
    infinity = 1000
    distance = [[0 if a == b else infinity for b in range(64)] for a in range(64)]
    for origin, snapshot in enumerate(snapshots):
        for index, name in enumerate(('a', 'b')):
            for slot_bit in (0, 1):
                target = (origin & ~(7 << (3 * index))) | ((slot_bit | 2 | (slot_bit << 2)) << (3 * index))
                candidate = snapshots[target]
                if check_compatibility(campaign, candidate.state):
                    continue
                before_version = 2 if origin & (1 << (3 * index)) else 1
                after_version = 2 if slot_bit else 1
                if after_version < before_version and not permissions & (1 << index):
                    continue
                available = {metadata.ecu_id: metadata.available for metadata in candidate.boot}
                if any(constraint.ecu == name and matches(str(after_version), constraint.version_spec)
                       and not available[constraint.needs] for constraint in campaign.constraints):
                    continue
                distance[origin][target] = min(distance[origin][target], 1)
    # Independent Floyd-Warshall closure, not production BFS/boot helpers.
    for middle in range(64):
        for origin in range(64):
            if distance[origin][middle] >= infinity:
                continue
            for target in range(64):
                distance[origin][target] = min(distance[origin][target], distance[origin][middle] + distance[middle][target])
    # Both effective versions are new. Confirmed selections/availability vary.
    start = 1 | 8 | rng.choice((0, 2)) | rng.choice((0, 4)) | rng.choice((0, 16)) | rng.choice((0, 32))
    goal = 2 | 16  # Original A slots, available, confirmed A.
    expected = distance[start][goal]
    result = find_guarded_recovery(campaign, snapshots[start])
    assert (result.status == 'available') == (expected < infinity)
    if result.status == 'available':
        assert len(result.steps) == expected
