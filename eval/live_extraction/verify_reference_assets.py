"""Read-only integrity checks with four explicitly optional external references.

No downloads, inference, evidence rewriting or label approval occur here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPTIONAL_ASSETS = frozenset({
    'eval/live_extraction/real-review-v2/sources/flysky-nb4-manual.pdf',
    'eval/live_extraction/real-review-v3/sources/flysky-nb4-manual.pdf',
    'eval/live_extraction/real-review-v3/rendered-pages/flysky-page-7.png',
    'eval/live_extraction/real-review-v3/rendered-pages/flysky-page-67.png',
})


def check_asset(root: Path, path: Path, expected: str) -> str:
    """Only allow absence of an exact listed asset; present bytes must match."""
    root, path = root.resolve(), path.resolve()
    relative = path.relative_to(root).as_posix()  # Reject escaping manifests.
    if not path.exists() and relative in OPTIONAL_ASSETS:
        return 'UNAVAILABLE_EXTERNAL_REFERENCE'
    if not path.is_file():
        raise ValueError(f'Missing required evidence: {relative}')
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError(f'Evidence hash mismatch: {relative}')
    return 'VERIFIED'


def verify_assets(root: Path = ROOT) -> dict[str, object]:
    """Check all published SHA256SUMS entries, reporting optional absence separately."""
    verified = 0
    unavailable: set[str] = set()
    manifests = 0
    for directory in ('eval/live_extraction', 'eval/scalability',
                      'validation/mcuboot', 'examples/engineering_evidence_v1'):
        for manifest in sorted((root / directory).rglob('SHA256SUMS.json')):
            manifests += 1
            entries = json.loads(manifest.read_text(encoding='utf-8'))
            for relative, expected in entries.items():
                path = manifest.parent / relative.replace('\\', '/')
                if check_asset(root, path, expected) == 'VERIFIED':
                    verified += 1
                else:
                    unavailable.add(path.relative_to(root).as_posix())
    # Require each optional reference to be bound by a published manifest too.
    for relative in OPTIONAL_ASSETS:
        path = root / relative
        packet = root / '/'.join(relative.split('/')[:3])
        entries = json.loads((packet / 'SHA256SUMS.json').read_text(encoding='utf-8'))
        key = next(key for key in entries if key.replace('\\', '/') == path.relative_to(packet).as_posix())
        check_asset(root, path, entries[key])
    return {'mode': 'OFFLINE_READ_ONLY', 'manifests_checked': manifests,
            'verified_entries': verified, 'unavailable_external_references': sorted(unavailable),
            'complete_reference_package_verified': not unavailable}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-external', action='store_true',
                        help='Exit 2 if any of the four optional references is unavailable')
    args = parser.parse_args()
    try:
        result = verify_assets()
    except (ValueError, OSError, KeyError, StopIteration) as error:
        print(json.dumps({'status': 'FAILED', 'error': str(error)}))
        return 1
    print(json.dumps(result, indent=2))
    return 2 if args.require_external and not result['complete_reference_package_verified'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
