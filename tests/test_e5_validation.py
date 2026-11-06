"""SIL behaviour and comparison logic. These run small scripts on real ECU processes."""
import ast
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
import pytest
from ota_verifier.formal.tlc_trace import extract_results, parse_value

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / 'experiments'), str(ROOT / 'sil')]
import e5_common as common  # noqa: E402
import harness  # noqa: E402
from harness import Setup, execute  # noqa: E402


def load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / 'experiments' / f'{name}.py')
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


e5 = load('e5_sil')
ECUS = ('gateway', 'brake', 'infotainment')
EDGES = (('brake', 'gateway'),)


def setup(design: str = 'none', policy: str = 'rolling') -> Setup:
    return Setup(ECUS, EDGES, design, policy)


def fault(tick: int, kind: str, ecu: str = '') -> dict:
    return {'tick': tick, 'kind': kind, 'ecu': ecu}


def tick_of(action: str, ecu: str, policy: str = 'rolling') -> int:
    return common.nominal_steps(list(ECUS), policy).index((action, ecu))


def test_sil_does_not_import_the_model_or_the_package() -> None:
    for name in ('harness.py', 'ecu_agent.py'):
        tree = ast.parse((ROOT / 'sil' / name).read_text(encoding='utf-8'))
        imported = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
        imported |= {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        assert not any(module.split('.')[0] == 'ota_verifier' for module in imported)


@pytest.mark.parametrize('policy', common.POLICIES)
def test_nominal_run_follows_the_written_schedule_and_commits(policy: str) -> None:
    run = execute(setup(policy=policy), [])
    assert run.campaign == 'committed' and not run.violated
    assert [tuple(step) for step in run.actions] == common.nominal_steps(list(ECUS), policy)
    assert set(run.running.values()) == {2}


def test_correct_design_rolls_back_every_ecu_after_a_trial_failure() -> None:
    run = execute(setup(), [fault(tick_of('Confirm', 'brake'), 'TrialFail', 'brake')])
    assert run.campaign == 'aborted' and not run.violated
    assert set(run.running.values()) == {1}


def test_local_rollback_leaves_brake_on_v2_with_gateway_on_v1() -> None:
    tick = tick_of('Confirm', 'gateway', 'late_confirm')
    run = execute(setup('LocalRollback', 'late_confirm'), [fault(tick, 'TrialFail', 'gateway')])
    assert run.running == {'gateway': 1, 'brake': 2, 'infotainment': 2}
    assert run.campaign == 'aborted' and {'S1', 'S3'} <= run.violated


def test_correct_design_handles_the_same_fault_safely() -> None:
    tick = tick_of('Confirm', 'gateway', 'late_confirm')
    run = execute(setup('none', 'late_confirm'), [fault(tick, 'TrialFail', 'gateway')])
    assert run.campaign == 'aborted' and not run.violated and set(run.running.values()) == {1}


def test_early_erase_gets_stuck_after_a_late_failure() -> None:
    run = execute(setup('EarlyErase'), [fault(tick_of('Confirm', 'brake'), 'TrialFail', 'brake')])
    assert run.campaign == 'rollback' and {'S2', 'L1'} <= run.violated


def test_skip_verify_runs_really_corrupt_bytes() -> None:
    run = execute(setup('SkipVerify'), [fault(tick_of('Download', 'gateway'), 'DownloadCorrupt', 'gateway')])
    assert 'S4' in run.violated


def test_corrupt_image_is_rejected_by_real_hash_check() -> None:
    run = execute(setup(), [fault(tick_of('Download', 'brake'), 'DownloadCorrupt', 'brake')])
    assert ['VerifyReject', 'brake'] in run.actions and run.campaign == 'aborted' and not run.violated


def test_power_cut_during_a_write_leaves_a_safe_vehicle() -> None:
    run = execute(setup(), [fault(tick_of('Download', 'brake'), 'PowerCutMidDownload', 'brake')])
    assert ['PowerLoss', ''] in run.actions and run.campaign == 'aborted' and not run.violated


def test_rollback_resumes_after_power_loss_during_rollback() -> None:
    tick = tick_of('Confirm', 'brake')
    run = execute(setup(), [fault(tick, 'TrialFail', 'brake'), fault(tick + 1, 'PowerLoss')])
    assert run.campaign == 'aborted' and set(run.running.values()) == {1} and not run.violated


def test_inapplicable_fault_is_skipped() -> None:
    run = execute(setup(), [fault(0, 'TrialFail', 'gateway')])
    assert run.campaign == 'committed'


def test_fault_scripts_cover_every_step_with_power_loss() -> None:
    steps = common.nominal_steps(list(ECUS), 'batch')
    singles = [script[0] for script in common.fault_scripts(list(ECUS), 'batch') if len(script) == 1]
    assert {f['tick'] for f in singles if f['kind'] == 'PowerLoss'} == set(range(len(steps)))
    assert {f['ecu'] for f in singles if f['kind'] == 'TrialFail'} == set(ECUS)


def test_mid_write_cut_is_a_power_loss_in_the_model() -> None:
    assert common.model_faults([fault(2, 'PowerCutMidDownload', 'a')]) == [fault(2, 'PowerLoss')]


@pytest.mark.parametrize(('predicted', 'observed', 'cell'), [
    (True, True, 'match_violation'), (False, False, 'match_safe'), (False, True, 'miss'), (True, False, 'false_alarm')])
def test_classify(predicted: bool, observed: bool, cell: str) -> None:
    assert e5.classify(predicted, observed) == cell


def test_compare_detects_a_different_path_even_when_verdicts_agree() -> None:
    prediction = dict(campaign='c', design='d', policy='p', script=0, faults=[], violated=[], final='aborted',
                      active={'a': 1}, actions=[['PowerLoss', '']])
    observed = dict(violated=[], actions=[['Commit', '']], campaign='aborted', running={'a': 1})
    row = e5.compare(prediction, observed)
    assert row['same_path'] is False and row['same_end'] is True and row['S1'] == 'match_safe'


def test_extract_results_reads_wrapped_printt_output() -> None:
    output = 'noise\n<< "RESULT",\n  3, {"S1"}, "aborted", [a |-> 1],\n  <<<<"PowerLoss", "">>>>>>\nmore\n<<"RESULT", 4, {}, "run", [a |-> 2], <<>>>>\n'
    assert extract_results(output) == [['RESULT', 3, ['S1'], 'aborted', {'a': 1}, [['PowerLoss', '']]],
                                       ['RESULT', 4, [], 'run', {'a': 2}, []]]
    assert parse_value('<<1, "x">>') == [1, 'x']


def test_harness_constants_are_for_both_versions() -> None:
    assert set(harness.GOOD_HASH) == {1, 2}
