"""Numeric version syntax and ordering regression tests."""
import pytest
from ota_verifier.versions import matches, parse_spec, parse_version


@pytest.mark.parametrize(('version', 'spec', 'expected'), [
    ('4.10', '>4.2', True), ('4.2', '>=4.2', True), ('4.2', '>4.2', False),
    ('4.2.0', '==4.2', True), ('4.2.1', '>4.2', True), ('4', '<4.0.1', True),
    ('4', '<=4', True), ('4', '!=4.0', False), ('5', '!=4', True),
    ('10', '<2', False), ('4', '==5', False), ('4', '>=5', False),
])
def test_comparisons(version: str, spec: str, expected: bool) -> None:
    assert matches(version, spec) is expected


@pytest.mark.parametrize('version', ['', 'v1', '1-beta', '1..2', '-1', ' 1', '1 ', '1e2'])
def test_bad_versions(version: str) -> None:
    with pytest.raises(ValueError):
        parse_version(version)


@pytest.mark.parametrize('spec', ['4.2', '~=4', '>=1,<2', '>= 1', '>=v1', '=1'])
def test_bad_specs(spec: str) -> None:
    with pytest.raises(ValueError):
        parse_spec(spec)
