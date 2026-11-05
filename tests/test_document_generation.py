"""Synthetic labels precede rendering; source-only requests cannot leak gold labels."""
from pathlib import Path
import pytest
from pydantic import ValidationError
from ota_verifier.data.generate import SyntheticCase, generate_case, generate_cases, main
from ota_verifier.llm.evidence import evidence_error
from ota_verifier.llm.extractor import extraction_prompt
from ota_verifier.llm.models import DocumentRequest
from ota_verifier.llm.verifier import validate_draft


@pytest.mark.parametrize('seed', [0, 1, 17])
def test_generator_is_reproducible_and_sources_are_exact(seed: int) -> None:
    cases = generate_cases(seed)
    assert cases == generate_cases(seed)
    assert len({case.id for case in cases}) == 6
    for case in cases:
        assert SyntheticCase.model_validate_json(case.model_dump_json()) == case
        for entry in case.reference_draft.constraints:
            assert evidence_error(case.request, entry.evidence, entry.constraint.source_text) is None
        if not case.expected_blocked:
            assert validate_draft(case.request, case.reference_draft) == ()
        prompt = extraction_prompt(case.request)
        assert 'truth_campaign' not in prompt
        assert 'expected_blocked' not in prompt
        assert 'reference_verdict' not in prompt
        assert case.id not in prompt  # Scenario labels must not leak through source IDs.


def test_request_schema_rejects_labeled_case_input() -> None:
    case = generate_case()
    with pytest.raises(ValidationError):
        DocumentRequest.model_validate_json(case.model_dump_json())


def test_generator_writes_separate_inputs_without_overwriting(tmp_path: Path) -> None:
    assert main(['--output-dir', str(tmp_path), '--count', '1']) == 0
    case_path = tmp_path / 'clear-0.case.json'
    request_path = tmp_path / 'clear-0.request.json'
    original = case_path.read_bytes()
    assert DocumentRequest.model_validate_json(request_path.read_text()).documents
    with pytest.raises(FileExistsError):
        main(['--output-dir', str(tmp_path), '--count', '1'])
    assert case_path.read_bytes() == original


def test_input_inventory_cannot_contain_prepopulated_constraints() -> None:
    case = generate_case()
    with pytest.raises(ValidationError, match='empty constraints'):
        DocumentRequest(campaign=case.truth_campaign, documents=case.request.documents)
