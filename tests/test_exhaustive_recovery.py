"""Recovery search compared with all-pairs shortest paths on tiny state graphs."""
import random
import pytest
from ota_verifier.ab import with_image, select_slot
from ota_verifier.compat import check_compatibility
from ota_verifier.models import Image
from ota_verifier.recovery import find_recovery
from test_planner import add_constraint, campaign_data, load_campaign


@pytest.mark.parametrize('seed', range(16))
def test_recovery_matches_exhaustive_slot_graph(seed: int) -> None:
    rng = random.Random(seed)
    data = campaign_data((1, 1, 1))
    names = ('a', 'b', 'c')
    permission_mask = rng.randrange(8) if seed % 2 else 7
    data['downgrade_authorizations'] = [dict(ecu_id=name, version='1', authorized_by='reviewer',
        reason='Exhaustive recovery exercise') for bit, name in enumerate(names) if permission_mask & (1 << bit)]
    for index in range(rng.randint(0, 5)):
        a, b = rng.sample(names, 2)
        spec = rng.choice(['>=2', '<=1'])
        add_constraint(data, 'requires', f'dep-{index}', ecu=a, version_spec=spec, needs=b, needs_version_spec=spec)
    campaign = load_campaign(data)
    base = campaign.initial_state
    for name in names:
        base = with_image(base, name, 'B', Image(version='2'))
    states = []
    for mask in range(8):
        state = base
        for bit, name in enumerate(names):
            if mask & (1 << bit):
                state = select_slot(state, name, 'B')
        states.append(state)
    valid = [not check_compatibility(campaign, state) for state in states]
    infinity = 100
    distance = [[0 if a == b else infinity for b in range(8)] for a in range(8)]
    for a in range(8):
        for bit in range(3):
            b = a ^ (1 << bit)
            downgrade = bool(a & (1 << bit))
            if valid[a] and valid[b] and (not downgrade or permission_mask & (1 << bit)):
                distance[a][b] = 1
    # Independent Floyd-Warshall oracle, not the production breadth-first search.
    for middle in range(8):
        for a in range(8):
            for b in range(8):
                distance[a][b] = min(distance[a][b], distance[a][middle] + distance[middle][b])
    result = find_recovery(campaign, states[7])
    expected = distance[7][0]
    assert (result.status == 'available') == (expected < infinity)
    if result.status == 'available':
        assert len(result.steps) == expected
        assert all(not check_compatibility(campaign, state) for state in result.states)
