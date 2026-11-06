"""Single entry point for the research artifact.

Every run writes to results/raw/<suite>/<run-id>/ with a manifest recording the
commit, environment, commands, exit codes and artifact hashes. A stage that
cannot run is reported as skipped, never as passed.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TOOLS = ROOT / 'tools'
SEED = 42
SMOKE_TESTS = ('tests/test_research_corpus.py', 'tests/test_run_all.py', 'tests/test_invariants.py',
               'tests/test_recovery.py', 'tests/test_simulator.py')
TLC_SUMMARY = re.compile(r'([\d,]+) states generated, ([\d,]+) distinct states found')
EXPERIMENTS = {'e0_small_campaign': ROOT / 'experiments' / 'e0_small_campaign.py'}


@dataclass
class Stage:
    """Outcome of one stage; status is passed, failed or skipped."""
    name: str
    status: str
    detail: str = ''
    command: tuple[str, ...] = ()
    exit_code: int | None = None


def run_command(name: str, command: list[str], run_dir: Path) -> tuple[int, str]:
    """Run a command from the repo root, logging its combined output."""
    env = {**os.environ, 'PYTHONPATH': str(ROOT / 'src'), 'PYTHONDONTWRITEBYTECODE': '1',
           'LANGSMITH_TRACING': 'false', 'LANGCHAIN_TRACING_V2': 'false'}
    done = subprocess.run(command, cwd=ROOT, env=env, text=True, encoding='utf-8', errors='replace',
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    (run_dir / f'{name}.log').write_text(done.stdout, encoding='utf-8')
    return done.returncode, done.stdout


def from_command(name: str, command: list[str], run_dir: Path) -> Stage:
    """Turn a command's exit code into a stage result."""
    code, _ = run_command(name, command, run_dir)
    return Stage(name, 'passed' if code == 0 else 'failed', command=tuple(command), exit_code=code)


def git(*args: str) -> str:
    """Return git output, or 'unknown' outside a repository."""
    done = subprocess.run(('git', *args), cwd=ROOT, text=True, capture_output=True, check=False)
    return done.stdout.strip() if done.returncode == 0 else 'unknown'


def java_version() -> str | None:
    """Return the first line of `java -version`, or None without Java."""
    if shutil.which('java') is None:
        return None
    done = subprocess.run(('java', '-version'), text=True, capture_output=True, check=False)
    return (done.stderr or done.stdout).splitlines()[0]


def environment() -> dict[str, object]:
    """Record what is needed to interpret and repeat a run."""
    freeze = subprocess.run((sys.executable, '-m', 'pip', 'freeze', '--exclude-editable'),
                            text=True, capture_output=True, check=False)
    return {'commit': git('rev-parse', 'HEAD'), 'dirty_files': git('status', '--porcelain', '--', '.', ':(exclude)results/raw').splitlines(),
            'seed': SEED, 'python': platform.python_version(), 'platform': platform.platform(),
            'machine': platform.machine(), 'logical_cpus': os.cpu_count(), 'java': java_version(),
            'packages': freeze.stdout.splitlines()}


def parse_tlc(output: str) -> tuple[int, int] | None:
    """Return (generated, distinct) from TLC's last summary line."""
    matches = TLC_SUMMARY.findall(output)
    if not matches:
        return None
    generated, distinct = (int(value.replace(',', '')) for value in matches[-1])
    return generated, distinct


def tlc_command(jar: Path, config: str, metadir: Path) -> list[str]:
    """Build a deterministic single-worker TLC invocation for the smoke spec."""
    return ['java', '-XX:+UseParallelGC', '-cp', str(jar), 'tlc2.TLC', '-workers', '1', '-seed', str(SEED),
            '-fp', '0', '-metadir', str(metadir), '-config', str(TOOLS / 'smoke' / config),
            str(TOOLS / 'smoke' / 'Smoke.tla')]


def stage_tlc(run_dir: Path, require: bool) -> list[Stage]:
    """Check TLC accepts a safe model and reports a seeded violation."""
    sys.path.insert(0, str(TOOLS))
    import fetch_tools
    pin = fetch_tools.load_pins()['tla2tools']
    jar = ROOT / str(pin['path'])
    problem = fetch_tools.verify(jar, pin)
    if java_version() is None:
        problem = 'java is not installed'
    if problem is not None:
        return [Stage('tlc', 'failed' if require else 'skipped', problem)]
    results = []
    for name, config, want_violation in (('tlc-holds', 'Holds.cfg', False), ('tlc-fails', 'Fails.cfg', True)):
        command = tlc_command(jar, config, run_dir / f'{name}-states')
        code, output = run_command(name, command, run_dir)
        violated = 'Invariant Fails is violated' in output
        counts = parse_tlc(output)
        if want_violation:
            good, detail = violated and code != 0, 'seeded violation reported' if violated else 'violation missed'
        else:
            good, detail = code == 0 and counts is not None and counts[1] == 4, f'generated, distinct = {counts}'
        results.append(Stage(name, 'passed' if good else 'failed', detail, tuple(command), code))
    return results


def stage_corpus(run_dir: Path) -> Stage:
    """Check the committed research campaigns still derive from frozen v1."""
    code = ('from ota_verifier.formal.research_corpus import is_current;'
            'raise SystemExit(0 if is_current() else 1)')
    return from_command('research-corpus', [sys.executable, '-c', code], run_dir)


def smoke(run_dir: Path, require_tlc: bool) -> list[Stage]:
    """Run a fast end-to-end check of every toolchain the experiments rely on."""
    benchmark = run_dir / 'benchmark-core.json'
    return [
        stage_corpus(run_dir),
        from_command('benchmark-core', [sys.executable, '-m', 'ota_verifier.benchmark.runner', '--mode', 'core',
                                        '--split', 'all', '--fail-on-findings', '--output', str(benchmark)], run_dir),
        from_command('pytest', [sys.executable, '-m', 'pytest', '-q', *SMOKE_TESTS, '-p', 'no:cacheprovider',
                                f'--basetemp={run_dir / "pytest-tmp"}',
                                f'--junitxml={run_dir / "pytest.xml"}'], run_dir),
        *stage_tlc(run_dir, require_tlc),
    ]


def artifact_hashes(run_dir: Path) -> dict[str, str]:
    """Hash every file in a run, skipping checker and pytest scratch folders."""
    hashes = {}
    for path in sorted(run_dir.rglob('*')):
        relative = path.relative_to(run_dir).as_posix()
        if path.is_file() and path.name != 'manifest.json' and '-states/' not in relative \
                and not relative.startswith('pytest-tmp/'):
            hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def write_manifest(run_dir: Path, suite: str, stages: list[Stage]) -> str:
    """Write the run record and return the overall status."""
    statuses = {stage.status for stage in stages}
    overall = 'failed' if 'failed' in statuses else 'incomplete' if 'skipped' in statuses else 'passed'
    manifest = {'suite': suite, 'status': overall, 'created_utc': datetime.now(timezone.utc).isoformat(),
                'environment': environment(), 'stages': [asdict(stage) for stage in stages],
                'artifacts_sha256': artifact_hashes(run_dir)}
    (run_dir / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return overall


def new_run_dir(suite: str) -> Path:
    """Create a fresh run folder; existing evidence is never overwritten."""
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    run_dir = ROOT / 'results' / 'raw' / suite / f'{stamp}-{git("rev-parse", "--short", "HEAD")}'
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def run_experiment(name: str, run_dir: Path) -> list[Stage]:
    """Run one registered experiment; it returns the problems it found."""
    sys.path[:0] = [str(ROOT / 'src'), str(TOOLS)]
    import fetch_tools
    pin = fetch_tools.load_pins()['tla2tools']
    problem = fetch_tools.verify(ROOT / str(pin['path']), pin)
    if problem is None and java_version() is None:
        problem = 'java is not installed'
    if problem is not None:
        return [Stage(name, 'failed', problem)]
    spec = importlib.util.spec_from_file_location(name, EXPERIMENTS[name])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    problems = module.run(run_dir, ROOT / str(pin['path']), ROOT)
    return [Stage(name, 'failed' if problems else 'passed', '; '.join(problems))]


def main(argv: list[str] | None = None) -> int:
    """Run the requested suite; exit 0 only if nothing failed."""
    parser = argparse.ArgumentParser(description='Run research experiments reproducibly.')
    parser.add_argument('--smoke', action='store_true', help='fast check of all toolchains')
    parser.add_argument('--require-tlc', action='store_true', help='fail instead of skipping when TLC cannot run')
    parser.add_argument('--experiment', choices=sorted(EXPERIMENTS), help='run one experiment')
    args = parser.parse_args(argv)
    if args.smoke == bool(args.experiment):
        parser.error('choose exactly one of --smoke or --experiment')
    suite = args.experiment or 'smoke'
    run_dir = new_run_dir(suite)
    stages = run_experiment(suite, run_dir) if args.experiment else smoke(run_dir, args.require_tlc)
    overall = write_manifest(run_dir, suite, stages)
    for stage in stages:
        print(f'{stage.status:8} {stage.name} {stage.detail}'.rstrip())
    print(f'{overall}: {run_dir.relative_to(ROOT).as_posix()}')
    return 1 if overall == 'failed' else 0


if __name__ == '__main__':
    sys.exit(main())
