"""TLC output parsing and the independent replay of counterexamples."""
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any
import pytest
from ota_verifier.formal.tlc_trace import changed_ecus, parse_trace, parse_value

ROOT = Path(__file__).resolve().parent.parent


def load() -> ModuleType:
    path = ROOT / 'experiments' / 'e0_small_campaign.py'
    spec = importlib.util.spec_from_file_location('e0_small_campaign', path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


e0 = load()
INITIAL = {'active': {'gateway': 1, 'brake': 1, 'infotainment': 1},
           'inactive': {'gateway': 0, 'brake': 0, 'infotainment': 0},
           'stage': {'gateway': 'idle', 'brake': 'idle', 'infotainment': 'idle'},
           'corrupt': {'gateway': False, 'brake': False, 'infotainment': False},
           'campaign': 'run', 'culprit': [], 'faults': 0}


def state(**changes: Any) -> dict[str, Any]:
    result = {key: dict(value) if isinstance(value, dict) else value for key, value in INITIAL.items()}
    for key, value in changes.items():
        result[key] = {**result[key], **value} if isinstance(value, dict) else value
    return result


def trace(*states: dict[str, Any], ending: str = 'finite') -> dict[str, Any]:
    return {'states': [{'action': 'X', 'vars': item} for item in states], 'ending': ending, 'loop_to': None}


SAMPLE = '\n'.join((
    'Error: Invariant CompatAlways is violated.',
    'Error: The behavior up to this point is:',
    'State 1: <Initial predicate>',
    '/\\ culprit = {}',
    '/\\ stage = [ gateway |-> "idle",',
    '  brake |-> "idle" ]',
    '',
    'State 2: <TrialFail line 105, col 5 to line 111, col 46 of module OTACampaign>',
    '/\\ culprit = {"gateway"}',
    '/\\ stage = [gateway |-> "failed", brake |-> "idle"]',
    '',
    '1017 states generated, 665 distinct states found, 142 states left on queue.',
    ''))


def test_parse_values() -> None:
    assert parse_value('[a |-> 1, b |-> "x", c |-> TRUE]') == {'a': 1, 'b': 'x', 'c': True}
    assert parse_value('{"b", "a"}') == ['a', 'b']
    assert parse_value('{}') == []


def test_parse_trace_handles_wrapped_values_and_action_names() -> None:
    parsed = parse_trace(SAMPLE)
    assert [item['action'] for item in parsed['states']] == ['Initial', 'TrialFail']
    assert parsed['states'][0]['vars']['stage'] == {'gateway': 'idle', 'brake': 'idle'}
    assert parsed['states'][1]['vars']['culprit'] == ['gateway']
    assert parsed['ending'] == 'finite'


def test_parse_trace_detects_stuttering_and_loops() -> None:
    assert parse_trace(SAMPLE.replace('1017 states', 'State 3: Stuttering\n1017 states'))['ending'] == 'stuttering'
    looped = parse_trace(SAMPLE.replace('1017 states', 'Back to state 1: <Next>\n1017 states'))
    assert (looped['ending'], looped['loop_to']) == ('loop', 1)


def test_changed_ecus() -> None:
    assert changed_ecus(state(), state(active={'brake': 2})) == ['brake']


def test_replay_confirms_a_genuine_s1_violation() -> None:
    assert e0.replay('S1', trace(state(), state(active={'brake': 2})))


@pytest.mark.parametrize('states', [
    (state(), state()),
    (state(active={'brake': 2}), state(active={'brake': 2})),
])
def test_replay_rejects_traces_not_ending_at_the_first_violation(states: tuple[dict[str, Any], ...]) -> None:
    assert not e0.replay('S1', trace(*states))


def test_replay_of_liveness_needs_an_unfinished_endless_trace() -> None:
    assert e0.replay('L1', trace(state(campaign='rollback'), ending='stuttering'))
    assert not e0.replay('L1', trace(state(campaign='aborted'), ending='stuttering'))
    assert not e0.replay('L1', trace(state(campaign='rollback')))


@pytest.mark.parametrize(('code', 'output', 'expected'), [
    (0, 'Model checking completed. No error has been found.', 'holds'),
    (12, 'Error: Invariant CompatAlways is violated.', 'violated'),
    (13, 'Error: Temporal properties were violated.', 'violated'),
    (12, 'Error: Invariant TypeOK is violated.', 'error'),
    (0, 'something unrecognized', 'error'),
    (1, 'Error: Parsing or semantic analysis failed.', 'error'),
])
def test_unrecognized_tlc_output_is_never_a_pass(code: int, output: str, expected: str) -> None:
    assert e0.verdict(code, output, 'CompatAlways') == expected


def test_problems_flags_surprises_and_failed_replays() -> None:
    base = dict(design='none', name='X', fault_budget=2, verdict='holds', expected_at_budget_2='holds', trace_replay='')
    assert e0.problems([base]) == []
    assert 'expected holds' in e0.problems([{**base, 'verdict': 'violated', 'trace_replay': True}])[0]
    failed = {**base, 'verdict': 'violated', 'expected_at_budget_2': 'violated', 'trace_replay': False}
    assert 'replay' in e0.problems([failed])[0]
