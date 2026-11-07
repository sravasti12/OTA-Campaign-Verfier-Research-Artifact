"""Execute real-process supervision probes and one unpooled planner confirmation run."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from time import sleep

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'eval')]
from scalability.memory import memory_observation
from scalability.run import environment, file_hash, protected_sources, run_process, verify_mcuboot
from scalability.worker import write_json


def main() -> int:
    """Preserve a launcher diagnosis, real allocation stop and actual Z3 execution."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    protected, boot = protected_sources(), verify_mcuboot()
    write_json(output / 'environment.json', environment())
    (output / 'source_snapshot').mkdir()
    for source in Path(__file__).parent.glob('*.py'):
        (output / 'source_snapshot' / source.name).write_bytes(source.read_bytes())
    # Reproduce the old launch mechanism, independently of corrected supervision.
    pid_file, marker = output / 'legacy-pid.json', output / 'legacy-finished.json'
    code = ("import json,os,time; from pathlib import Path; blob=bytearray(64*1024**2); "
            f"Path({str(pid_file)!r}).write_text(json.dumps({{'pid':os.getpid()}})); "
            f"time.sleep(2); Path({str(marker)!r}).write_text('{{}}')")
    process = subprocess.Popen([sys.executable, '-c', code], cwd=ROOT)
    for _ in range(200):
        if pid_file.exists():
            break
        sleep(.01)
    try:
        actual_pid = json.loads(pid_file.read_text())['pid']
        diagnosis = {'popen_pid': process.pid, 'worker_pid': actual_pid,
                     'launcher_memory': memory_observation(process.pid),
                     'worker_memory': memory_observation(actual_pid)}
    finally:
        process.kill()
        process.wait()
    sleep(2.1)
    diagnosis['completion_marker_after_launcher_kill'] = marker.exists()
    write_json(output / 'launcher-diagnosis.json', diagnosis)
    allocation = output / 'allocation.json'
    code = ("import json,os,time; from pathlib import Path; blob=bytearray(64*1024**2); "
            f"Path({str(allocation)!r}).write_text(json.dumps({{'status':'probe','process_id':os.getpid()}})); time.sleep(5)")
    guarded = run_process([sys.executable, '-c', code], allocation, watchdog_seconds=4,
                          memory_limit_bytes=32*1024**2, poll_seconds=.01)
    write_json(output / 'allocation.supervised.json', guarded)
    input_path = output / 'input.json'
    input_path.write_bytes(args.input.read_bytes())
    actual = run_process([sys.executable, str(Path(__file__).parent / 'worker.py'), '--input', str(input_path),
                          '--output', str(output / 'z3.json'), '--algorithm', 'z3'], output / 'z3.json',
                         watchdog_seconds=45, memory_limit_bytes=2*1024**3)
    write_json(output / 'z3.supervised.json', actual)
    last = actual.get('last_progress', actual)
    result = {'separate_from_primary_statistics': True,
              'legacy_parent_memory_unreliable': diagnosis['popen_pid'] != diagnosis['worker_pid'],
              'legacy_worker_continued_to_marker_after_kill': marker.exists(),
              'real_allocation_guard_status': guarded['status'], 'z3_status': actual['status'],
              'z3_supervised_pid_matches_worker': actual['supervised_pid'] == last.get('process_id'),
              'protected_sources_unchanged': protected_sources() == protected,
              'mcuboot_manifests_unchanged': verify_mcuboot() == boot}
    write_json(output / 'audit.json', result)
    write_json(output / 'SHA256SUMS.json', {path.relative_to(output).as_posix():file_hash(path)
        for path in output.rglob('*') if path.is_file()})
    sys.stdout.write(json.dumps(result)+'\n')
    return 0 if (guarded['status'] == 'MEMORY_LIMIT' and result['z3_supervised_pid_matches_worker']
                 and not marker.exists() and result['protected_sources_unchanged']
                 and result['mcuboot_manifests_unchanged']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
