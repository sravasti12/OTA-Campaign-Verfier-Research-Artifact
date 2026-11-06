"""Run TLC under a wall-clock limit, measuring states, time and peak memory."""
import ctypes
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

SEED = 42
HEAP = '4g'
COUNTS = re.compile(r'([\d,]+) states generated(?: \([^)]*\))?, ([\d,]+) distinct states found, '
                    r'([\d,]+) states left on queue')
DEPTH = re.compile(r'The depth of the complete state graph search is (\d+)')


@dataclass(frozen=True)
class TlcResult:
    """One TLC run. A DNF run's counts are what it reached before it was stopped."""
    status: str  # completed, DNF(time), DNF(memory) or error
    verdict: str  # holds, violated or unknown
    generated: int | None
    distinct: int | None
    queue: int | None
    depth: int | None
    wall_seconds: float
    peak_rss_mb: float | None
    exit_code: int | None


@lru_cache(maxsize=1)
def java_executable() -> str:
    """Find the real JVM binary.

    On Windows, `java` on PATH can be a small launcher that starts the JVM as a
    child. Measuring or killing the launcher would miss the JVM itself.
    """
    done = subprocess.run(('java', '-XshowSettings:properties', '-version'), text=True, capture_output=True, check=True)
    match = re.search(r'java\.home = (.+)', done.stderr)
    if match is None:
        raise RuntimeError('Could not determine java.home')
    binary = Path(match[1].strip()) / 'bin' / ('java.exe' if sys.platform == 'win32' else 'java')
    if not binary.is_file():
        raise RuntimeError(f'No JVM at {binary}')
    return str(binary)


def peak_rss_mb(process: subprocess.Popen[bytes]) -> float | None:
    """Read a finished process's peak working set. Only implemented on Windows."""
    if sys.platform != 'win32':
        return None

    class Counters(ctypes.Structure):
        _fields_ = [('cb', ctypes.c_ulong), ('PageFaultCount', ctypes.c_ulong), ('PeakWorkingSetSize', ctypes.c_size_t),
                    ('WorkingSetSize', ctypes.c_size_t), ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPagedPoolUsage', ctypes.c_size_t), ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaNonPagedPoolUsage', ctypes.c_size_t), ('PagefileUsage', ctypes.c_size_t),
                    ('PeakPagefileUsage', ctypes.c_size_t)]

    counters = Counters()
    counters.cb = ctypes.sizeof(Counters)
    function = ctypes.WinDLL('psapi').GetProcessMemoryInfo
    function.argtypes = (ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.c_ulong)
    if not function(int(process._handle), ctypes.byref(counters), counters.cb):  # type: ignore[attr-defined]
        return None
    return counters.PeakWorkingSetSize / 2**20


def classify(output: str, code: int | None, timed_out: bool) -> tuple[str, str]:
    """Return (status, verdict). Unrecognized output is an error, never a pass."""
    if 'OutOfMemoryError' in output:
        return 'DNF(memory)', 'unknown'
    if timed_out:
        return 'DNF(time)', 'unknown'
    if 'Invariant TypeOK is violated' in output:
        return 'error', 'unknown'
    if re.search(r'Invariant \w+ is violated', output) or 'Temporal properties were violated' in output \
            or 'Action property' in output and 'is violated' in output:
        return 'completed', 'violated'
    if code == 0 and 'Model checking completed. No error has been found.' in output:
        return 'completed', 'holds'
    return 'error', 'unknown'


def parse_counts(output: str) -> tuple[int | None, int | None, int | None]:
    """Read the most recent state counts, from the summary or a progress line."""
    found = COUNTS.findall(output)
    if not found:
        return None, None, None
    generated, distinct, queue = (int(value.replace(',', '')) for value in found[-1])
    return generated, distinct, queue


def run_tlc(jar: Path, spec: str, spec_dir: Path, cfg: Path, log: Path, limit_seconds: float) -> TlcResult:
    """Run TLC with one worker and a fixed seed; stop it at the limit and report DNF."""
    metadir = Path(tempfile.mkdtemp(prefix='tlc-states-'))
    command = [java_executable(), '-XX:+UseParallelGC', f'-Xmx{HEAP}', '-cp', str(jar), 'tlc2.TLC', '-workers', '1',
               '-seed', str(SEED), '-fp', '0', '-metadir', str(metadir), '-config', str(cfg), spec]
    started = time.perf_counter()
    timed_out = False
    with log.open('wb') as handle:
        process = subprocess.Popen(command, cwd=spec_dir, stdout=handle, stderr=subprocess.STDOUT)
        try:
            process.wait(timeout=limit_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            process.wait()
    elapsed = time.perf_counter() - started
    memory = peak_rss_mb(process)
    shutil.rmtree(metadir, ignore_errors=True)
    output = log.read_text(encoding='utf-8', errors='replace')
    status, verdict = classify(output, process.returncode, timed_out)
    generated, distinct, queue = parse_counts(output)
    depth = DEPTH.findall(output)
    return TlcResult(status, verdict, generated, distinct, queue, int(depth[-1]) if depth else None,
                     elapsed, memory, process.returncode)
