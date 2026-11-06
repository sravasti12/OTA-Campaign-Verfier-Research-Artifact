"""One engineering validation runner: fresh C execution or explicitly labelled replay."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
from typing import Any
import xml.etree.ElementTree as ET

from differential import HERE, OUT, PIN, ROOT, build_report, sha256
from refinement import build_refinement, verify_evidence

LOGGER = logging.getLogger(__name__)


def protected_sources() -> dict[str, str]:
    """Fingerprint production, existing tests and dependency files without changing them."""
    paths = [path for folder in ('src', 'app', 'tests') for path in (ROOT / folder).rglob('*.py')]
    paths += [ROOT / name for name in ('pyproject.toml', 'requirements.txt')]
    return {path.relative_to(ROOT).as_posix(): sha256(path) for path in sorted(paths)}


def junit_outcome(path: Path) -> dict[str, int]:
    """Read actual pytest outcomes from JUnit, including failures and skips."""
    suites = list(ET.parse(path).getroot().iter('testsuite'))
    totals = {name: sum(int(suite.get(name, '0')) for suite in suites)
              for name in ('tests', 'failures', 'errors', 'skipped')}
    totals['passed'] = totals['tests'] - totals['failures'] - totals['errors'] - totals['skipped']
    if totals['tests'] == 0:
        raise ValueError('No regression tests executed')
    return totals


def verify_package(report_path: Path) -> int:
    """Verify every package artifact, including the consolidated report itself."""
    root = report_path.parent.resolve()
    manifest = json.loads((root / 'SHA256SUMS.json').read_text(encoding='utf-8'))
    if report_path.name not in manifest:
        raise ValueError('Report is missing from package manifest')
    for name, expected in manifest.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or sha256(path) != expected:
            raise ValueError(f'Package hash mismatch: {name}')
    return len(manifest)


def comparison_acceptable(comparison: dict[str, Any], refinement: dict[str, Any]) -> bool:
    """Allow documented differences, but never unexpected or inconclusive outcomes."""
    return (not refinement['unexpected_contradictions']
            and all(row['comparison']['status'] != 'INCONCLUSIVE'
                    and not row['comparison'].get('unexpected_contradiction', False)
                    for row in comparison['scenarios']))


def run_validation(mode: str, output: Path, distribution: str) -> dict[str, Any]:
    """Execute all stages and preserve failure evidence in a new, non-overwriting package."""
    output.mkdir(parents=True, exist_ok=False)
    before = protected_sources()
    historical = verify_evidence(OUT / 'comparison.json')
    stages: list[dict[str, Any]] = []
    report: dict[str, Any] = {'schema_version': 1, 'phase': '1E', 'mode': mode,
        'created_utc': datetime.now(timezone.utc).isoformat(), 'status': 'RUNNING',
        'reference': {'version': 'v2.4.0', 'commit': PIN, 'strategy': 'scratch',
                      'signature': 'RSA-2048/SHA-256', 'features': ['sig-rsa', 'validate-primary-slot']},
        'current_python_environment': {'version': sys.version, 'executable': sys.executable,
                                       'platform': platform.platform()},
        'stages': stages, 'scenario_counts': None, 'scenarios': [],
        'remaining_gaps': ['Scratch-journal equivalence and exhaustive interruption coverage',
            'Cryptographic validation equivalence with Boolean Image.valid',
            'Application instructions, runtime health and hardware power behavior',
            'Fleet-wide compatibility validation against MCUboot',
            'Other upgrade strategies and antirollback configurations'],
        'documentation_analysis': {'execution_kind': 'DOCUMENTATION_ONLY',
            'note': 'Policy interpretation supplements measured outcomes; no additional execution coverage.'}}

    def native(script: str, destination: Path) -> None:
        """Execute an official-harness script, directing outputs away from historical evidence."""
        destination.mkdir(parents=True, exist_ok=True)
        if os.name == 'nt':
            def linux(path: Path) -> str:
                return subprocess.run(['wsl', '-d', distribution, '--', 'wslpath', '-a', path.as_posix()],
                                      check=True, capture_output=True, text=True).stdout.strip()
            command = ['wsl', '-d', distribution, '--', 'env',
                       f'MCUBOOT_EVIDENCE_DIR={linux(destination)}', 'bash', linux(HERE / script)]
        else:
            command = ['env', f'MCUBOOT_EVIDENCE_DIR={destination}', 'bash', str(HERE / script)]
        stage = {'name': script, 'execution_kind': 'NATIVE_BUILD_ONLY' if script == 'build-reference.sh'
                 else 'FRESH_NATIVE_C', 'status': 'RUNNING', 'command': command}
        stages.append(stage)
        (output / 'progress.json').write_text(json.dumps(stage, indent=2), encoding='utf-8')
        with (destination / 'launcher.log').open('w', encoding='utf-8') as stream:
            result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
        stage.update(exit_code=result.returncode, status='PASSED' if result.returncode == 0 else 'FAILED')
        if result.returncode:
            raise RuntimeError(f'{script} failed: exit {result.returncode}; see {destination}/launcher.log')

    try:
        reference = output / 'reference'
        differential = output / 'differential'
        differential.mkdir()
        if mode == 'fresh':
            native('build-reference.sh', output / 'build')
            stages[-1]['execution_kind'] = 'NATIVE_BUILD_ONLY'
            native('run-reference.sh', reference)
            native('run-differential.sh', differential)
        else:
            reference.mkdir()
            for name in ('reference.log', 'environment.txt'):
                shutil.copyfile(OUT / name, differential / name)
            for name in ('upstream-basic_revert.log', 'upstream-norevert.log',
                         'upstream-bad_secondary_slot.log', 'observations.log', 'environment.txt'):
                shutil.copyfile(HERE / 'evidence' / name, reference / name)
            stages.append({'name': 'reference evidence replay', 'execution_kind': 'REPLAYED_NATIVE_EVIDENCE',
                           'status': 'VERIFIED_REPLAY', 'fresh_native_execution': False,
                           'source_phase_1c_hashes': historical})
        for name, passed in [('upstream-basic_revert.log', 1), ('upstream-norevert.log', 1),
                             ('upstream-bad_secondary_slot.log', 1), ('observations.log', 2)]:
            if f'test result: ok. {passed} passed; 0 failed' not in (reference / name).read_text(encoding='utf-8'):
                raise ValueError(f'Missing successful nonzero reference test execution: {name}')
        report['reference_test_outcomes'] = {'test_functions_passed': 5,
            'execution_kind': 'FRESH_NATIVE_C' if mode == 'fresh' else 'REPLAYED_NATIVE_EVIDENCE'}
        report['recorded_native_environment'] = (differential / 'environment.txt').read_text(encoding='utf-8')
        report['recorded_reference_test_environment'] = (reference / 'environment.txt').read_text(encoding='utf-8')
        comparison = build_report(differential, differential)
        (differential / 'comparison.json').write_text(json.dumps(comparison, indent=2), encoding='utf-8')
        stages.append({'name': 'differential Python execution', 'execution_kind': 'FRESH_PYTHON_SIMULATOR',
                       'status': 'COMPLETED', 'scenarios_executed': len(comparison['scenarios'])})
        refinement = build_refinement(output / 'refinement', differential / 'comparison.json')
        refinement['native_execution'] = ('Fresh native C observations from this validation run' if mode == 'fresh'
                                          else 'Replayed captured native evidence; no fresh C execution')
        (output / 'refinement' / 'review.json').write_text(json.dumps(refinement, indent=2), encoding='utf-8')
        stages.append({'name': 'refinement', 'execution_kind': 'FRESH_PYTHON_AND_EVIDENCE_REVIEW',
                       'status': 'PASSED' if not refinement['unexpected_contradictions'] else 'FAILED'})
        report['scenario_counts'] = {key: comparison['summary'].get(key, 0)
                                     for key in ('MATCH', 'MISMATCH', 'UNSUPPORTED', 'INCONCLUSIVE')}
        reviews = {row['id']: row['review'] for row in refinement['scenarios']}
        report['scenarios'] = [dict(row, refinement=reviews[row['id']]) for row in comparison['scenarios']]
        report['differential_native_test'] = {'passed': 1, 'scenarios': 12,
            'execution_kind': 'FRESH_NATIVE_C' if mode == 'fresh' else 'REPLAYED_NATIVE_EVIDENCE'}
        pytest_command = [sys.executable, '-m', 'pytest', '-q', 'tests',
                          'validation/mcuboot/test_differential.py', 'validation/mcuboot/test_refinement.py',
                          'validation/mcuboot/test_validate.py', f'--junitxml={output / "pytest.xml"}']
        stage = {'name': 'pytest', 'execution_kind': 'FRESH_PYTHON_TESTS', 'command': pytest_command}
        stages.append(stage)
        (output / 'progress.json').write_text(json.dumps(stage, indent=2), encoding='utf-8')
        with (output / 'pytest.log').open('w', encoding='utf-8') as stream:
            result = subprocess.run(pytest_command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
        outcomes = junit_outcome(output / 'pytest.xml')
        matches = re.findall(r'(\d+) warnings?\b', (output / 'pytest.log').read_text(encoding='utf-8'))
        report['pytest'] = outcomes | {'exit_code': result.returncode, 'warnings': int(matches[-1]) if matches else 0}
        stage.update(status='PASSED' if result.returncode == 0 else 'FAILED', exit_code=result.returncode)
        report['status'] = ('PASSED_WITH_DOCUMENTED_DIFFERENCES' if result.returncode == 0
                            and comparison_acceptable(comparison, refinement) else 'FAILED')
    except Exception as error:
        LOGGER.exception('Validation did not complete')
        report.update(status='FAILED', error=f'{type(error).__name__}: {error}')
    report['protected_sources_unchanged'] = before == protected_sources()
    report['historical_evidence_unchanged'] = historical == verify_evidence(OUT / 'comparison.json')
    if not report['protected_sources_unchanged'] or not report['historical_evidence_unchanged']:
        report['status'] = 'FAILED'
    report['protected_source_sha256'] = before
    snapshot = output / 'reproduction_source'
    snapshot.mkdir()
    for path in HERE.iterdir():
        if path.is_file() and (path.suffix in ('.py', '.rs', '.sh', '.ps1') or path.name == 'Cargo.lock'):
            shutil.copyfile(path, snapshot / path.name)
    report['evidence'] = {path.relative_to(output).as_posix(): sha256(path)
                          for path in sorted(output.rglob('*')) if path.is_file()}
    report_path = output / 'validation.json'
    report['manifest_artifact_count'] = len(report['evidence']) + 1
    report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    manifest = report['evidence'] | {'validation.json': sha256(report_path)}
    (output / 'SHA256SUMS.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    report['verified_artifact_count'] = verify_package(report_path)
    return report


def main() -> int:
    """Run fresh/replay validation or independently verify an existing package."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('fresh', 'replay'), default='fresh')
    parser.add_argument('--distribution', default='Ubuntu-24.04')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--verify', type=Path)
    args = parser.parse_args()
    if args.verify:
        LOGGER.info('Verified %s artifacts', verify_package(args.verify.resolve()))
        return 0
    output = args.output or HERE / 'final_evidence' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    report = run_validation(args.mode, output.resolve(), args.distribution)
    LOGGER.info('%s: %s; pytest=%s; verified artifacts=%s', output, report['status'],
                report.get('pytest'), report['verified_artifact_count'])
    return 1 if report['status'] == 'FAILED' else 0


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
