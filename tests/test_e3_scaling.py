"""Campaign generator, TLC run classification, and E3's guards against silent errors."""
import importlib.util
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType
import pytest
from ota_verifier.formal.campaign_gen import edges_of, ecu_names, generate, is_acyclic, random_edges
from ota_verifier.formal.tlc_run import classify, java_executable, parse_counts, peak_rss_mb
from ota_verifier.models import Campaign

ROOT = Path(__file__).resolve().parent.parent


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location('e3_scaling', ROOT / 'experiments' / 'e3_scaling.py')
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


e3 = load()


@pytest.mark.parametrize('size', [5, 10, 20, 50])
@pytest.mark.parametrize('seed', [1, 2, 3])
def test_generated_campaigns_are_valid_acyclic_and_repeatable(size: int, seed: int) -> None:
    campaign = generate(size, seed)
    assert len(campaign.ecus) == size
    assert is_acyclic(ecu_names(size), edges_of(campaign))
    assert generate(size, seed) == campaign
    assert Campaign.model_validate_json(campaign.model_dump_json()) == campaign


def test_seed_changes_the_graph_and_known_graph_stays_pinned() -> None:
    assert random_edges(20, 1) != random_edges(20, 2)
    assert random_edges(6, 1) == random_edges(6, 1)
    assert len({frozenset(edge) for edge in random_edges(50, 1)}) == len(random_edges(50, 1))


def test_cycle_detection() -> None:
    assert not is_acyclic(('a', 'b'), (('a', 'b'), ('b', 'a')))
    assert is_acyclic(('a', 'b', 'c'), (('a', 'b'), ('b', 'c')))


def test_generator_rejects_a_single_ecu() -> None:
    with pytest.raises(ValueError):
        generate(1, 1)


@pytest.mark.parametrize(('output', 'code', 'timed_out', 'expected'), [
    ('Model checking completed. No error has been found.', 0, False, ('completed', 'holds')),
    ('Error: Invariant S is violated.', 12, False, ('completed', 'violated')),
    ('Error: Temporal properties were violated.', 13, False, ('completed', 'violated')),
    ('Error: Action property line 3 of module X is violated.', 13, False, ('completed', 'violated')),
    ('Progress(3)', None, True, ('DNF(time)', 'unknown')),
    ('java.lang.OutOfMemoryError: Java heap space', 1, False, ('DNF(memory)', 'unknown')),
    ('Error: Invariant TypeOK is violated.', 12, False, ('error', 'unknown')),
    ('nothing useful', 0, False, ('error', 'unknown')),
])
def test_classify(output: str, code: int | None, timed_out: bool, expected: tuple[str, str]) -> None:
    assert classify(output, code, timed_out) == expected


def test_parse_counts_reads_the_latest_progress_line() -> None:
    output = ('Progress(5) at 2026-11-06 19:00:00: 1,000 states generated (1,000 s/min), 500 distinct states found, '
              '40 states left on queue.\n'
              'Progress(6) at 2026-11-06 19:01:00: 2,500 states generated (1,500 s/min), 1,200 distinct states found, '
              '90 states left on queue.\n')
    assert parse_counts(output) == (2500, 1200, 90)
    assert parse_counts('Finished') == (None, None, None)


@pytest.mark.skipif(shutil.which('java') is None, reason='needs Java')
def test_time_limit_stops_the_real_jvm_and_memory_is_the_jvm_not_a_launcher() -> None:
    probe = ROOT / 'tools' / 'bin' / 'tla2tools.jar'
    process = subprocess.Popen([java_executable(), '-version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    process.wait()
    if sys.platform == 'win32':
        assert peak_rss_mb(process) > 15
    sleeper = subprocess.Popen([java_executable(), '-cp', str(probe), 'tlc2.REPL'], stdin=subprocess.PIPE,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.2)
    sleeper.kill()
    assert sleeper.wait(timeout=10) != 0


def test_applicable_shapes() -> None:
    assert e3.applicable_shapes(3, ()) == {'none'}
    assert e3.applicable_shapes(2, (('a', 'b'),)) == {'edge'}
    assert e3.applicable_shapes(3, (('a', 'b'),)) == {'none', 'edge'}


def ok_row(**changes: object) -> dict[str, object]:
    return {'n': 3, 'seed': 1, 'design': 'none', 'status': 'completed', **changes}


def test_problems_catches_an_unsound_prediction() -> None:
    bad = ok_row(property='S1', pair_prediction='holds', monolithic='violated')
    assert 'UNSOUND' in e3.problems([], [], [bad], [])[0]


def test_spurious_prediction_is_recorded_but_is_not_a_soundness_problem() -> None:
    assert e3.problems([], [], [ok_row(property='S1', pair_prediction='violated', monolithic='holds')], []) == []


def test_problems_requires_the_negative_control_to_fail() -> None:
    control = ok_row(env_fail_enabled=False, verdict='holds')
    assert 'expected violated' in e3.problems([], [control], [], [])[0]


def test_monolithic_dnf_is_a_result_and_a_violation_is_not() -> None:
    row = dict(method='monolithic', properties='S1-S4', n=50, seed=1, status='DNF(time)', verdict='unknown')
    assert e3.problems([], [], [], [row]) == []
    assert e3.problems([], [], [], [{**row, 'status': 'completed', 'verdict': 'violated'}])


def test_limits_are_longer_only_near_the_boundary() -> None:
    assert e3.limit_for('S1-S4', 10) == e3.LONG_LIMIT_SECONDS
    assert e3.limit_for('S1-S4', 20) == e3.LIMIT_SECONDS
    assert e3.limit_for('L1', 6) == e3.LIMIT_SECONDS
