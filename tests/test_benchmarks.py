"""Executable expected outcomes for hand-authored simulation scenarios."""
import json
from pathlib import Path
import pytest
from pydantic import ValidationError
from ota_verifier.compat import check_compatibility
from ota_verifier.models import Campaign, VehicleState

FIXTURES = Path(__file__).parent / 'fixtures'


@pytest.mark.parametrize('name', ['compatible', 'order_sensitive', 'impossible_direct', 'recovery_trap'])
def test_benchmark_states(name: str) -> None:
    payload = json.loads((FIXTURES / f'{name}.json').read_text(encoding='utf-8'))
    campaign = Campaign.model_validate_json(json.dumps(payload['campaign']))
    for case in payload['states']:
        state = VehicleState.model_validate_json(json.dumps(case['state']))
        findings = check_compatibility(campaign, state)
        assert [finding.constraint_id for finding in findings] == case['expected_constraint_ids'], case['name']
        for finding in findings:
            constraint = next(c for c in campaign.constraints if c.id == finding.constraint_id)
            assert finding.source_text == constraint.source_text
            assert finding.source_document_id == constraint.source_document_id
            assert finding.actual_version is not None
            assert finding.expected_version_spec is not None
    assert Campaign.model_validate_json(campaign.model_dump_json()) == campaign


def test_unknown_reference_benchmark() -> None:
    payload = json.loads((FIXTURES / 'invalid_input.json').read_text(encoding='utf-8'))
    with pytest.raises(ValidationError, match=payload['expected_validation_error']):
        Campaign.model_validate_json(json.dumps(payload['campaign']))
