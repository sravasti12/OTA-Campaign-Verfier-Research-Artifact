"""The new corpus revision preserves unapproved status and checks exclusion support offline."""
import importlib.util
import json
from pathlib import Path
from typing import Any
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('validate_real_v3', ROOT / 'eval/live_extraction/validate_real_v3.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_revision_and_existing_exclusion_support_without_live_inference(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gold-fixture gate tests and actual Z3 controls must not call a provider."""
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError('Live provider prohibited during corpus preparation')
    monkeypatch.setattr('ota_verifier.llm.client.LLMClient.generate_json', forbidden)
    result = module.validate()
    unavailable = [row['id'] for row in result['cases']
                   if row['source_hash'] == 'UNAVAILABLE_EXTERNAL_REFERENCE']
    if unavailable:
        import warnings
        warnings.warn(f'External source verification unavailable for {unavailable}; all first-party checks run', UserWarning)
    assert len(result['cases']) == 5 and result['new_provider_requests'] == 0
    assert result['precise_exclusion_supported'] is True


def test_case03_includes_exact_pinned_context_without_changing_other_source_labels() -> None:
    """Context and offsets change in the revision; the parent packet stays intact."""
    parent = json.loads((ROOT / 'eval/live_extraction/real-review-v2/candidates.json').read_text(encoding='utf-8'))
    revision = json.loads((ROOT / 'eval/live_extraction/real-review-v3/candidates.json').read_text(encoding='utf-8'))
    old, new = parent['cases'][2], revision['cases'][2]
    assert new['ingested_document']['text'].startswith('A Version is defined or formatted as "Major.Minor.Patch"')
    assert new['ingested_document']['text'].endswith(old['ingested_document']['text'])
    assert new['proposed_draft']['issues'][0]['evidence']['start_char'] > 0
    for index in (0, 1, 3, 4):
        assert revision['cases'][index]['proposed_draft'] == parent['cases'][index]['proposed_draft']
    assert all(row['review_status'] == 'UNREVIEWED' and not row['admitted'] for row in revision['cases'])
