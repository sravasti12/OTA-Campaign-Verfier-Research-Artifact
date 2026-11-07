"""Serial, bounded scalability execution with raw evidence and no production changes."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import logging
import os
from pathlib import Path
import platform
import random
import subprocess
import sys
from time import monotonic, perf_counter_ns, sleep
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'eval')]
from scalability.memory import memory_observation, system_memory
from scalability.worker import write_json
from scalability.workloads import FAMILIES, SEEDS, SIZES, canonical, digest, generate

LOGGER = logging.getLogger(__name__)
HERE = Path(__file__).resolve().parent


def file_hash(path: Path) -> str:
    """Hash actual file bytes for immutable evidence indices."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protected_sources() -> dict[str, str]:
    """Fingerprint existing production code, not concurrent unrelated research additions."""
    names = ('models.py', 'versions.py', 'compat.py', 'policy.py', 'planner.py', 'scheduling.py',
        'simulator.py', 'simulation_models.py', 'invariants.py', 'recovery.py', 'boot.py',
        'boot_models.py', 'guarded_simulator.py', 'boot_recovery.py', 'boot_comparison.py', 'graph.py')
    paths = [ROOT / 'src/ota_verifier' / name for name in names]
    paths += list((ROOT / 'src/ota_verifier/llm').glob('*.py')) + list((ROOT / 'app').glob('*.py'))
    return {path.relative_to(ROOT).as_posix(): file_hash(path) for path in paths}


def verify_mcuboot() -> dict[str, str]:
    """Verify and fingerprint both existing final evidence manifests without executing them."""
    result = {}
    for name in ('phase1e-fresh', 'phase1e-replay'):
        root = ROOT / 'validation/mcuboot/final_evidence' / name
        manifest = root / 'SHA256SUMS.json'
        for relative, expected in json.loads(manifest.read_text(encoding='utf-8')).items():
            path = (root / relative).resolve()
            if not path.is_relative_to(root.resolve()) or file_hash(path) != expected:
                raise ValueError(f'MCUboot evidence changed: {relative}')
        result[name] = file_hash(manifest)
    return result


def environment() -> dict[str, Any]:
    """Record actual software/host identifiers without inspecting provider credentials."""
    import z3
    packages = sorted({(item.metadata['Name'], item.version) for item in importlib.metadata.distributions()
                       if item.metadata['Name']})
    git = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    dirty = subprocess.run(['git', 'status', '--short'], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return {'utc': datetime.now(timezone.utc).isoformat(), 'python': sys.version,
            'python_executable': sys.executable, 'platform': platform.platform(), 'processor': platform.processor(),
            'logical_cpus': os.cpu_count(), 'z3_native': z3.get_full_version(), 'git_commit': git,
            'system_memory': system_memory(),
            'dirty_worktree': dirty, 'packages': [{'name': name, 'version': version} for name, version in packages],
            'host_dedicated': False, 'background_load_controlled': False,
            'benchmark_sources': {path.name: file_hash(path) for path in HERE.glob('*.py')}}


def trial_specs(profile: str) -> list[dict[str, Any]]:
    """Freeze profiles before measurement, including explicit supplementary controls."""
    sizes = (10,) if profile == 'smoke' else SIZES
    seeds = SEEDS if profile == 'primary' else (SEEDS[0],)
    repetitions = 5 if profile == 'primary' else 1
    specs = []
    if profile == 'supplementary':
        controls = [('cycle', 'benign_cycle'), ('chain', 'order_chain'), ('mutex_order', 'tight_deadline'),
            ('mutex_order', 'relaxed_deadline'), ('environment', 'allowed_environment'),
            ('downgrade', 'authorized_downgrade'), ('independent', 'half_noop'), ('independent', 'rounding')]
        for family, variant in controls:
            for size in SIZES:
                specs.append(dict(family=family, size=size, seed=11, variant=variant, timeout_ms=10000,
                                  repetition=0, role='measured'))
        for family in ('dense', 'resource'):
            for timeout in (1000, 30000):
                specs.append(dict(family=family, size=100, seed=11, variant='primary', timeout_ms=timeout,
                                  repetition=0, role='measured'))
    else:
        for family in FAMILIES:
            for size in sizes:
                for seed in seeds:
                    for repetition in range(repetitions):
                        specs.append(dict(family=family, size=size, seed=seed, variant='primary', timeout_ms=10000,
                                          repetition=repetition, role='measured'))
    random.Random(20261106).shuffle(specs)
    if profile == 'primary':
        warmups = [dict(family=family, size=size, seed=11, variant='primary', timeout_ms=10000,
                        repetition=-1, role='warmup') for family in FAMILIES for size in SIZES]
        specs = warmups + specs
    return specs


def run_process(command: list[str], output: Path, *, watchdog_seconds: float,
                memory_limit_bytes: int, poll_seconds: float = 0.1) -> dict[str, Any]:
    """Supervise one child, preserving timeout/memory/crash rows and partial-stage evidence."""
    started = monotonic()
    peak: int | None = None
    errors: set[str] = set()
    termination = None
    launched_command = list(command)
    launch_environment = None
    direct_interpreter = (os.name == 'nt' and Path(command[0]).resolve() == Path(sys.executable).resolve()
                          and sys.prefix != sys.base_prefix)
    if direct_interpreter:
        # Windows venv python.exe is a redirector: its PID is not the worker PID.
        # Start the real interpreter with the same venv path configuration.
        launched_command[0] = sys._base_executable
        launch_environment = os.environ.copy()
        launch_environment['__PYVENV_LAUNCHER__'] = sys.executable
    with output.with_suffix('.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen(launched_command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                   env=launch_environment)
        while process.poll() is None:
            observed = memory_observation(process.pid)
            value = observed['peak_bytes']
            if value is not None:
                peak = max(peak or 0, value)
            elif observed['error']:
                errors.add(observed['error'])
            if monotonic() - started > watchdog_seconds:
                termination = 'WATCHDOG_TIMEOUT'
            elif peak is not None and peak > memory_limit_bytes:
                termination = 'MEMORY_LIMIT'
            if termination:
                process.kill()
                break
            sleep(poll_seconds)
        exit_code = process.wait()
    if output.exists():
        try:
            record = json.loads(output.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            record = {'status': 'WORKER_ERROR', 'partial_output_error': str(error)}
    else:
        record = {'status': termination or 'WORKER_CRASH'}
    if termination:
        record = {'status': termination, 'partial_worker_result': record}
    elif exit_code != 0:
        record['status'] = 'WORKER_ERROR'
    partial = output.with_suffix('.progress.json')
    if partial.exists():
        record['last_progress'] = json.loads(partial.read_text(encoding='utf-8'))
    record.update(worker_exit_code=exit_code, worker_total_ms=(monotonic()-started)*1000,
                  parent_observed_peak_bytes=peak, parent_memory_errors=sorted(errors),
                  parent_peak_censored=bool(termination), command=command,
                  launched_command=launched_command, supervised_pid=process.pid,
                  windows_direct_interpreter=direct_interpreter)
    return record


def run(profile: str, output: Path, *, watchdog_seconds: float = 45,
        wall_seconds: float = 21600, memory_limit_bytes: int = 2*1024**3) -> dict[str, Any]:
    """Execute a predeclared serial matrix; never drop a slow, failed or unattempted row."""
    experiment_started = monotonic()
    output.mkdir(exist_ok=False, parents=True)
    (output / 'inputs').mkdir()
    (output / 'trials').mkdir()
    source_hashes, boot_hashes = protected_sources(), verify_mcuboot()
    runtime = environment()
    (output / 'source_snapshot').mkdir()
    for source in HERE.glob('*.py'):
        (output / 'source_snapshot' / source.name).write_bytes(source.read_bytes())
    write_json(output / 'environment.json', runtime)
    (output / 'requirements-measured.txt').write_text('\n'.join(
        f"{item['name']}=={item['version']}" for item in runtime['packages'] if item['name'].lower() != 'ota-verifier')+'\n',
        encoding='utf-8', newline='\n')
    specs = trial_specs(profile)
    inputs: dict[str, dict[str, Any]] = {}
    trials = []
    for spec in specs:
        key = f"{spec['family']}-n{spec['size']}-s{spec['seed']}-{spec['variant']}-t{spec['timeout_ms']}"
        if key not in inputs:
            started = perf_counter_ns()
            case = generate(spec['family'], spec['size'], spec['seed'], variant=spec['variant'], timeout_ms=spec['timeout_ms'])
            generation_ms = (perf_counter_ns()-started)/1e6
            payload = case.payload()
            path = output / 'inputs' / (key+'.json')
            write_json(path, payload)
            inputs[key] = {'path': str(path), 'sha256': file_hash(path), 'semantic_sha256': digest(payload),
                           'generation_and_gold_ms': generation_ms, 'metadata': case.metadata,
                           'expected': case.certificate['expected'], 'certificate': case.certificate}
        for algorithm in (('z3',) if spec['role'] == 'warmup' else ('z3', 'sequential')):
            identifier = f"{spec['role']}-{key}-r{spec['repetition']}-{algorithm}"
            trials.append(spec | {'input_key': key, 'algorithm': algorithm, 'trial_id': identifier})
    manifest = {'format': 'scalability-run-v1', 'profile': profile, 'synthetic_only': True,
        'inputs': inputs, 'trials': trials, 'watchdog_seconds': watchdog_seconds,
        'memory_limit_bytes': memory_limit_bytes, 'wall_budget_seconds': wall_seconds,
        'parent_memory_scope': 'worker_interpreter_direct',
        'production_sources': source_hashes, 'mcuboot_manifests': boot_hashes,
        'note': 'Generation/gold outside timed trials. Warmups retained but excluded from measured summaries.'}
    write_json(output / 'manifest.json', manifest)
    started = experiment_started
    findings: list[str] = []
    counts: Counter[str] = Counter()
    complete = 0
    aborted = False
    with (output / 'trials.jsonl').open('w', encoding='utf-8', newline='\n') as stream:
        for index, trial in enumerate(trials):
            record = dict(trial)
            path = output / 'trials' / (trial['trial_id']+'.json')
            if aborted or monotonic()-started >= wall_seconds:
                record.update(status='NOT_RUN', reason='Earlier harness finding' if aborted else 'Experiment wall budget')
            else:
                command = [sys.executable, str(HERE / 'worker.py'), '--input', inputs[trial['input_key']]['path'],
                           '--output', str(path), '--algorithm', trial['algorithm']]
                record.update(run_process(command, path, watchdog_seconds=watchdog_seconds,
                    memory_limit_bytes=memory_limit_bytes))
                expected = inputs[trial['input_key']]['expected']
                if record['status'] in ('feasible', 'infeasible') and record['status'] != expected:
                    findings.append(f"Truth contradiction: {trial['trial_id']}")
                    aborted = True
                if record['status'] in ('WORKER_ERROR', 'WORKER_CRASH'):
                    findings.append(f"Worker failed: {trial['trial_id']}")
                    aborted = True
                if not record.get('parent_observed_peak_bytes'):
                    findings.append(f"Parent memory monitor unavailable: {trial['trial_id']}")
                    aborted = True
            write_json(path.with_suffix('.supervised.json'), record)
            stream.write(canonical(record)+'\n')
            stream.flush()
            counts[record['status']] += 1
            complete += 1
            if index % 10 == 0 or complete == len(trials):
                progress = {'finished': complete, 'scheduled': len(trials), 'elapsed_seconds': monotonic()-started,
                            'statuses': dict(counts), 'last_trial': trial['trial_id'], 'findings': findings}
                write_json(output / 'progress.json', progress)
                LOGGER.info('%s %s/%s %s', profile, complete, len(trials), dict(counts))
    benchmark_unchanged = runtime['benchmark_sources'] == {path.name: file_hash(path) for path in HERE.glob('*.py')}
    unchanged = protected_sources() == source_hashes and verify_mcuboot() == boot_hashes and benchmark_unchanged
    if not unchanged:
        findings.append('Protected production source or MCUboot evidence changed during measurement')
    summary = {'profile': profile, 'scheduled': len(trials), 'statuses': dict(counts), 'findings': findings,
               'protected_sources_and_mcuboot_unchanged': unchanged, 'elapsed_seconds': monotonic()-started,
               'benchmark_sources_unchanged': benchmark_unchanged,
               'protocol_complete': not findings and counts['NOT_RUN'] == 0}
    write_json(output / 'completion.json', summary)
    hashes = {path.relative_to(output).as_posix(): file_hash(path) for path in output.rglob('*') if path.is_file()}
    write_json(output / 'SHA256SUMS.json', hashes)
    return summary


def main() -> int:
    """Run one stage with explicit resource limits and a new output directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=('smoke', 'pilot', 'primary', 'supplementary'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--watchdog-seconds', type=float, default=45)
    parser.add_argument('--wall-seconds', type=float, default=21600)
    parser.add_argument('--memory-limit-mib', type=int, default=2048)
    args = parser.parse_args()
    if args.watchdog_seconds <= 0 or args.wall_seconds <= 0 or args.memory_limit_mib <= 0:
        parser.error('Resource limits must be positive')
    result = run(args.profile, args.output.resolve(), watchdog_seconds=args.watchdog_seconds,
                 wall_seconds=args.wall_seconds, memory_limit_bytes=args.memory_limit_mib*1024**2)
    LOGGER.info('Completed: %s', result)
    return 0 if result['protocol_complete'] else 1


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    raise SystemExit(main())
