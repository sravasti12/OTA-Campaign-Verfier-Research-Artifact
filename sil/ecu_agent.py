"""One simulated ECU, run as its own OS process. Standard library only.

All persistent state is in files in this ECU's folder, like flash:
  slotA.img, slotB.img    image bytes
  slotA.meta, slotB.meta  version of a verified image; written only after verification
  boot.json               which slot boots

Commands arrive on stdin as JSON lines and replies leave on stdout. Killing this
process at any moment loses only what was not yet on disk.
"""
import hashlib
import json
import os
import sys
from pathlib import Path

CHUNKS = 16
CHUNK_BYTES = 4096


def payload(version: int) -> bytes:
    """The image bytes for a version."""
    block = hashlib.sha256(f'image-v{version}'.encode()).digest()
    return block * (CHUNKS * CHUNK_BYTES // len(block))


def durable_write(path: Path, data: bytes) -> None:
    """Replace a file atomically, so a crash leaves the old or new content, never a mix."""
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('wb') as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


class Agent:
    """Executes commands against this ECU's files."""

    def __init__(self, folder: Path) -> None:
        self.folder = folder

    def boot(self) -> dict:
        return json.loads((self.folder / 'boot.json').read_text(encoding='utf-8'))

    def other(self) -> str:
        return 'B' if self.boot()['active'] == 'A' else 'A'

    def meta(self, slot: str) -> Path:
        return self.folder / f'slot{slot}.meta'

    def image(self, slot: str) -> Path:
        return self.folder / f'slot{slot}.img'

    def clear(self, slot: str) -> None:
        self.meta(slot).unlink(missing_ok=True)
        self.image(slot).unlink(missing_ok=True)

    def download(self, command: dict) -> dict:
        """Write the image to the inactive slot in chunks, optionally pausing halfway."""
        slot = self.other()
        self.clear(slot)
        data = bytearray(payload(command['version']))
        if command.get('corrupt'):
            data[len(data) // 2] ^= 0xFF
        with self.image(slot).open('wb') as handle:
            for index in range(CHUNKS):
                handle.write(data[index * CHUNK_BYTES:(index + 1) * CHUNK_BYTES])
                handle.flush()
                os.fsync(handle.fileno())
                if command.get('pause_half') and index == CHUNKS // 2 - 1:
                    print(json.dumps({'half': True}), flush=True)
                    sys.stdin.readline()  # The harness cuts power here; this never returns.
        return {'ok': True}

    def verify(self, command: dict) -> dict:
        """Check the inactive image's hash, unless this design skips verification."""
        slot = self.other()
        actual = hashlib.sha256(self.image(slot).read_bytes()).hexdigest()
        good = actual == hashlib.sha256(payload(command['version'])).hexdigest()
        if good or command.get('skip'):
            durable_write(self.meta(slot), json.dumps({'version': command['version']}).encode())
            return {'ok': True}
        return {'ok': False}

    def activate(self, command: dict) -> dict:
        """Boot the other slot, optionally erasing the old image to free flash."""
        old = self.boot()['active']
        durable_write(self.folder / 'boot.json', json.dumps({'active': self.other()}).encode())
        if command.get('erase_old'):
            self.clear(old)
        return {'ok': True}

    def rollback(self, _command: dict) -> dict:
        """Boot the other slot if it holds a verified image."""
        slot = self.other()
        if not self.meta(slot).is_file():
            return {'ok': False}
        durable_write(self.folder / 'boot.json', json.dumps({'active': slot}).encode())
        return {'ok': True}

    def version(self, _command: dict) -> dict:
        """Report the running version."""
        meta = json.loads(self.meta(self.boot()['active']).read_text(encoding='utf-8'))
        return {'ok': True, 'version': meta['version']}

    def can_rollback(self, _command: dict) -> dict:
        """Report whether a verified image is available in the other slot."""
        return {'ok': self.meta(self.other()).is_file()}


def main() -> None:
    agent = Agent(Path(sys.argv[1]))
    print(json.dumps({'ready': True}), flush=True)
    for line in sys.stdin:
        command = json.loads(line)
        print(json.dumps(getattr(agent, command['cmd'])(command)), flush=True)


if __name__ == '__main__':
    main()
