"""OS-backed single-workspace execution lock; automatically released on process exit."""
from contextlib import contextmanager
from pathlib import Path
from time import monotonic, sleep
from collections.abc import Iterator
import os


class WorkspaceBusy(RuntimeError):
    """Another process is analyzing or changing the same workspace."""


@contextmanager
def execution_lock(path: Path, timeout: float = 10) -> Iterator[None]:
    """Serialize graph mutation across processes without holding a SQL transaction."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b'0')
            handle.flush()
        deadline = monotonic() + timeout
        while True:
            try:
                handle.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (OSError, BlockingIOError):
                if monotonic() >= deadline:
                    raise WorkspaceBusy('Workspace is busy; retry after the current operation completes') from None
                sleep(0.05)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
