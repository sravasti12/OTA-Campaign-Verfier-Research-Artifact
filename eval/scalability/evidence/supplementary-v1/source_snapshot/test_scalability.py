"""Synthetic generator/baseline contracts, not performance claims."""
from dataclasses import replace
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'eval')]
from ota_verifier.compat import check_compatibility
from ota_verifier.models import Campaign, FeasibleResult, InfeasibleResult, PlanningOptions
from ota_verifier.planner import plan_campaign
from ota_verifier.scheduling import validate_plan
from scalability.memory import memory_observation
from scalability.workloads import (FAMILIES, SIZES, baseline, canonical, digest, generate,
                                   milliseconds, sequential_plan, verify_gold)


@pytest.mark.parametrize('size', SIZES)
@pytest.mark.parametrize('family', FAMILIES)
def test_schema_and_analytic_or_constructive_gold(family: str, size: int) -> None:
    """Every requested size/family has verified gold and exact source provenance."""
    case = generate(family, size, 11)
    assert Campaign.model_validate_json(canonical(case.payload()['campaign'])) == case.campaign
    assert case.metadata['network_size'] == case.metadata['changed_ecus'] == size
    assert all(rule.source_document_id == 'synthetic-ground-truth' for rule in case.campaign.constraints)
    verify_gold(case)


def test_fixed_seed_materializes_identical_input() -> None:
    """Campaigns, not just seed labels, are reproducible and hashable."""
    assert digest(generate('dense', 10, 29).payload()) == digest(generate('dense', 10, 29).payload())
    assert digest(generate('dense', 10, 29).payload()) != digest(generate('dense', 10, 47).payload())


@pytest.mark.parametrize(('family', 'variant'), [
    ('cycle', 'benign_cycle'), ('chain', 'order_chain'), ('mutex_order', 'relaxed_deadline'),
    ('environment', 'allowed_environment'), ('downgrade', 'authorized_downgrade'),
    ('independent', 'half_noop'), ('independent', 'rounding')])
def test_positive_controls_and_baseline(family: str, variant: str) -> None:
    """Controls are validated schedules, not labels inferred from the solver."""
    case = generate(family, 10, 11, variant=variant)
    result = baseline(case.campaign, case.options)
    assert result['status'] == 'feasible'
    assert validate_plan(case.campaign, result['plan']) == ()


@pytest.mark.parametrize('family', ('cycle', 'environment', 'downgrade'))
def test_genuine_contradictions_match_actual_solver(family: str) -> None:
    """Tiny negative certificates agree with real Z3, including serialized activation cycles."""
    case = generate(family, 3, 11)
    result = plan_campaign(case.campaign, case.options)
    assert isinstance(result, InfeasibleResult)
    assert result.conflict.items
    assert baseline(case.campaign, case.options)['status'] == 'NO_BASELINE_SCHEDULE'


def test_cycle_does_not_mean_infeasible() -> None:
    """An always-satisfied dependency cycle is a feasible control."""
    case = generate('cycle', 3, 11, variant='benign_cycle')
    assert isinstance(plan_campaign(case.campaign, case.options), FeasibleResult)


def test_bad_positive_certificate_is_rejected() -> None:
    """A negative input cannot be labelled positive without a valid witness."""
    case = generate('cycle', 3, 11)
    with pytest.raises(ValueError, match='witness'):
        verify_gold(replace(case, certificate={'kind': 'compatible_sequential_witness', 'expected': 'feasible'}))


def test_noops_and_rounding_are_explicit() -> None:
    """Inventory count is distinct from work count; sub-millisecond writes round upward."""
    case = generate('independent', 10, 11, variant='half_noop')
    assert case.metadata['changed_ecus'] == 5
    assert milliseconds(0.00001) == 1


def test_tight_deadline_control_is_not_invalid_input() -> None:
    """A schema-valid deadline below the longest write is genuinely impossible."""
    case = generate('mutex_order', 3, 11, variant='tight_deadline')
    assert isinstance(plan_campaign(case.campaign, case.options), InfeasibleResult)


def test_requires_chain_does_not_force_sequential_writes() -> None:
    """Finish/start order and active-version dependence have different schedules."""
    dependency = generate('chain', 3, 11)
    ordered = generate('chain', 3, 11, variant='order_chain')
    first = plan_campaign(dependency.campaign, dependency.options)
    second = plan_campaign(ordered.campaign, ordered.options)
    assert isinstance(first, FeasibleResult) and isinstance(second, FeasibleResult)
    assert first.plan.makespan_ms < second.plan.makespan_ms


def test_baseline_never_calls_z3(monkeypatch: pytest.MonkeyPatch) -> None:
    """The constructive baseline does not delegate its search to the planner."""
    import ota_verifier.planner as planner
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError('Baseline called Z3')
    monkeypatch.setattr(planner, 'plan_campaign', forbidden)
    case = generate('sparse', 10, 29)
    assert baseline(case.campaign, case.options)['status'] == 'feasible'


def test_native_memory_counter_is_positive_or_explicitly_unavailable() -> None:
    """OS memory readings never use zero as a substitute for missing observations."""
    observed = memory_observation()
    if observed['peak_bytes'] is None:
        assert observed['error']
    else:
        assert observed['peak_bytes'] > 0 and observed['error'] is None


def test_parallel_deadline_does_not_turn_baseline_failure_into_infeasibility() -> None:
    """A sequential heuristic may miss a valid parallel schedule."""
    case = generate('independent', 3, 11)
    deadline = max(milliseconds(ecu.flash_minutes) for ecu in case.campaign.ecus)
    options = PlanningOptions(deadline_ms=deadline)
    assert isinstance(plan_campaign(case.campaign, options), FeasibleResult)
    assert baseline(case.campaign, options)['status'] == 'NO_BASELINE_SCHEDULE'


def test_primary_manifest_has_600_measurements_and_40_warmups() -> None:
    """Sample counts are frozen before measurements, not selected after observing results."""
    from scalability.run import trial_specs
    specs = trial_specs('primary')
    assert sum(item['role'] == 'measured' for item in specs) == 600
    assert sum(item['role'] == 'warmup' for item in specs) == 40
    assert len(trial_specs('supplementary')) == 36


def test_supervisor_retains_watchdog_termination(tmp_path: Path) -> None:
    """An artificial sleeping process tests watchdog logic, not solver speed."""
    from scalability.run import run_process
    result = run_process([sys.executable, '-c', 'import time; time.sleep(10)'], tmp_path / 'sleep.json',
        watchdog_seconds=0.1, memory_limit_bytes=2*1024**3, poll_seconds=0.01)
    assert result['status'] == 'WATCHDOG_TIMEOUT'
    assert result['parent_peak_censored']


def test_supervisor_retains_failed_worker(tmp_path: Path) -> None:
    """Nonzero worker exits are errors, never guessed solver outcomes."""
    from scalability.run import run_process
    result = run_process([sys.executable, '-c', 'raise SystemExit(7)'], tmp_path / 'failed.json',
        watchdog_seconds=5, memory_limit_bytes=2*1024**3)
    assert result['status'] == 'WORKER_ERROR' and result['worker_exit_code'] == 7


def test_llm_import_guard_rejects_model_namespace() -> None:
    """Real worker entry points guard against future accidental model coupling."""
    from scalability.worker import NoLLM
    with pytest.raises(ImportError, match='forbidden'):
        NoLLM().find_spec('ota_verifier.llm.client')


def test_incremental_baseline_validates_dense_hundred_ecu_plan() -> None:
    """Affected-rule filtering must retain full intermediate replay validity."""
    case = generate('dense', 100, 11)
    result = baseline(case.campaign, case.options)
    assert result['status'] == 'feasible'
    assert validate_plan(case.campaign, result['plan']) == ()


def test_descriptive_metrics_do_not_fill_missing_samples_with_zero() -> None:
    """Unknown memory/latency samples are undefined, not perfect measurements."""
    from scalability.report import describe
    assert describe([])['median'] is None
    assert describe([1., 2., 3., 4., 5.]) == {'n': 5, 'median': 3., 'p95_nearest_rank': 5., 'min': 1., 'max': 5.}


def test_memory_stop_is_retained_as_censored_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Artificial memory observations test supervisor classification, not real solver usage."""
    import scalability.run as runner
    monkeypatch.setattr(runner, 'memory_observation', lambda pid: {'peak_bytes': 100, 'error': None})
    result = runner.run_process([sys.executable, '-c', 'import time; time.sleep(10)'], tmp_path / 'memory.json',
                               watchdog_seconds=5, memory_limit_bytes=50)
    assert result['status'] == 'MEMORY_LIMIT' and result['parent_peak_censored']


def test_changed_evidence_fails_verification(tmp_path: Path) -> None:
    """Recorded artifact hashes fail closed if any evidence bytes change."""
    import json
    from scalability.report import verify
    path = tmp_path / 'sample.json'
    path.write_text('{}', encoding='utf-8')
    (tmp_path / 'SHA256SUMS.json').write_text(json.dumps({'sample.json': '0'*64}), encoding='utf-8')
    with pytest.raises(ValueError, match='Invalid evidence'):
        verify(tmp_path)
