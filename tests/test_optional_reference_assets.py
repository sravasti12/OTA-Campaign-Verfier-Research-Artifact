"""Optional external files never weaken first-party or present-file integrity."""
import hashlib
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'eval/live_extraction'))
from verify_reference_assets import OPTIONAL_ASSETS, check_asset


@pytest.mark.parametrize('relative', sorted(OPTIONAL_ASSETS))
@pytest.mark.parametrize('state', ['absent', 'correct', 'corrupt'])
def test_external_reference_status_and_tamper_detection(tmp_path: Path, relative: str, state: str) -> None:
    path = tmp_path / relative
    expected = hashlib.sha256(b'expected reference bytes').hexdigest()
    if state != 'absent':
        path.parent.mkdir(parents=True)
        path.write_bytes(b'expected reference bytes' if state == 'correct' else b'corruption')
    if state == 'corrupt':
        with pytest.raises(ValueError, match='hash mismatch'):
            check_asset(tmp_path, path, expected)
    else:
        assert check_asset(tmp_path, path, expected) == (
            'VERIFIED' if state == 'correct' else 'UNAVAILABLE_EXTERNAL_REFERENCE')


def test_missing_first_party_file_still_fails(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match='Missing required evidence'):
        check_asset(tmp_path, tmp_path / 'eval/live_extraction/real-review-v3/candidates.json', '0' * 64)


def test_manifest_path_escape_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        check_asset(tmp_path, tmp_path.parent / 'escaped', '0' * 64)
