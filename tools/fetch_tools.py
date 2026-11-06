"""Download pinned research tools and refuse anything that fails its checksum."""
import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSIONS = ROOT / 'tools' / 'versions.json'


def sha256(path: Path) -> str:
    """Return the SHA-256 hex digest of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_pins(path: Path = VERSIONS) -> dict[str, dict[str, str | int]]:
    """Load the tool pins."""
    return json.loads(path.read_text(encoding='utf-8'))


def verify(path: Path, pin: dict[str, str | int]) -> str | None:
    """Return a problem description, or None when the file matches its pin."""
    if not path.is_file():
        return f'{path} is missing'
    digest = sha256(path)
    if digest != pin['sha256']:
        return f'{path} has SHA-256 {digest}, expected {pin["sha256"]}'
    return None


def fetch(name: str, pin: dict[str, str | int], root: Path = ROOT) -> Path:
    """Ensure one pinned tool is present, downloading it only when needed."""
    target = root / str(pin['path'])
    if verify(target, pin) is None:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + '.part')
    with urllib.request.urlopen(str(pin['url']), timeout=120) as response:
        partial.write_bytes(response.read())
    problem = verify(partial, pin)
    if problem is not None:
        partial.unlink()
        raise RuntimeError(f'Refusing {name}: {problem}')
    partial.replace(target)
    return target


def main() -> int:
    """Fetch every pinned tool, or only check them with --check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='verify without downloading')
    args = parser.parse_args()
    status = 0
    for name, pin in load_pins().items():
        if args.check:
            problem = verify(ROOT / str(pin['path']), pin)
            if problem is not None:
                print(f'{name}: {problem}', file=sys.stderr)
                status = 1
                continue
        else:
            fetch(name, pin)
        print(f'{name} {pin["version"]}: ok')
    return status


if __name__ == '__main__':
    sys.exit(main())
