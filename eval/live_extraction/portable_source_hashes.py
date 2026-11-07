import hashlib
import json
from pathlib import Path


def verify_portable_sources(root: Path, baseline_path: Path) -> bool:
    """Verify source content across Windows and Linux."""
    expected = json.loads(baseline_path.read_text(encoding="utf-8"))

    source_dir = root / "src" / "ota_verifier"
    actual_paths = {
        path.relative_to(root).as_posix()
        for path in source_dir.rglob("*.py")
    }

    if actual_paths != set(expected):
        return False

    for name, digest in expected.items():
        data = (root / name).read_bytes()
        normalized = data.replace(b"\r\n", b"\n")

        if hashlib.sha256(normalized).hexdigest() != digest:
            return False

    return True
