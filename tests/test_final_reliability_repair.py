"""Saved live failures remain failures; bounded corrections are tested offline only."""
import importlib.util
import json
from pathlib import Path
from typing import Any
import pytest
pytestmark = pytest.mark.usefixtures('offline_groq_settings')
from ota_verifier.llm.client import FixtureClient, LLMClient, LLMError
from ota_verifier.llm.models import ExtractionRun
from ota_verifier.llm.pipeline import extract_and_verify, verified_campaign
from ota_verifier.llm.source_support import explicit_flash_order
from ota_verifier.llm.verifier import validate_verdict

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'eval/live_extraction/real-pilot-v1'
spec = importlib.util.spec_from_file_location('continuation_plan', ROOT / 'eval/live_extraction/continuation_plan.py')
profile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile)


def saved(identifier: str) -> ExtractionRun:
    """Load a historical raw-response run without rewriting it."""
    return ExtractionRun.model_validate_json(json.dumps(json.loads((RUN / (identifier + '.json')).read_text())['run']))


def test_saved_flysky_false_rejection_is_flagged_but_not_accepted() -> None:
    """Source-direction disagreement adds diagnostics, never permission to plan."""
    original = saved('real-v2-01')
    replay = extract_and_verify(original.request, FixtureClient(tuple(call.response_text for call in original.calls)))
    assert replay.status == 'blocked' and replay.campaign is None
    assert replay.draft == original.draft and replay.verification == original.verification
    assert {'verification_disagreement', 'incorrect_constraint'} <= {i.code for i in replay.issues}
    with pytest.raises(ValueError, match='blocked'):
        verified_campaign(replay)


def test_unknown_verifier_id_and_wrong_source_still_block_without_disagreement_proof() -> None:
    """Literal valid quotation cannot override an unknown ID or incorrect evidence."""
    original = saved('real-v2-01')
    issue = original.verification.issues[0]
    verdict = original.verification.model_copy(update={'issues': (issue.model_copy(update={'constraint_id': 'unknown'}),)})
    findings = validate_verdict(original.request, original.draft, verdict)
    assert 'verification_reference' in {i.code for i in findings}
    assert 'verification_disagreement' not in {i.code for i in findings}
    changed = issue.model_copy(update={'source_text': 'invented'})
    verdict = original.verification.model_copy(update={'issues': (changed,)})
    assert 'source_error' in {i.code for i in validate_verdict(original.request, original.draft, verdict)}


def test_saved_false_unsupported_exclusion_is_not_silently_repaired() -> None:
    """Prompt clarification does not turn a saved model omission into a correct extraction."""
    original = saved('real-v2-02')
    replay = extract_and_verify(original.request, FixtureClient((original.calls[0].response_text,)))
    assert replay.status == 'blocked' and replay.draft == original.draft
    assert replay.draft.constraints == () and replay.draft.issues[0].kind == 'unsupported_requirement'
    assert replay.verification is None


def test_genuinely_reversed_update_order_is_blocked_before_verifier() -> None:
    """The same generic wording check rejects a wrong rule rather than trusting its quote."""
    original = saved('real-v2-01')
    raw = json.loads(original.draft.model_dump_json())
    rule = raw['constraints'][0]['constraint']
    rule['before'], rule['after'] = rule['after'], rule['before']
    run = extract_and_verify(original.request, FixtureClient((json.dumps(raw),)))
    assert run.status == 'blocked' and run.verification is None
    assert 'source_support' in {issue.code for issue in run.issues}


@pytest.mark.parametrize('text', [
    'If parked, You must update the alpha firmware before updating the beta firmware.',
    'You may update the alpha firmware before updating the beta firmware.',
    'You must update the alpha firmware before updating the beta firmware, unless moving.',
])
def test_new_order_grammar_does_not_guess_conditions(text: str) -> None:
    """Unknown or qualified statements remain outside the bounded recognizer."""
    assert explicit_flash_order(text) is None


def test_generic_order_grammar_is_not_tied_to_reviewed_device_names() -> None:
    """The production rule recognizes variable endpoints rather than a corpus answer."""
    assert explicit_flash_order('You must update the alpha firmware before updating the beta firmware.') == ('alpha', 'beta')


def test_saved_http400_is_reported_once_at_proposed_cap_with_mocked_transport() -> None:
    """Replaying a real provider failure still fails, even with a larger supported cap."""
    calls = json.loads((RUN / 'calls.json').read_text())
    failure = next(call for call in calls if call['http_status'] == 400)
    error = json.loads(failure['error_body'])['error']
    assert error['code'] == 'json_validate_failed' and 'max completion tokens' in error['failed_generation']
    observed = []
    def offline_transport(request: Any) -> Any:
        observed.append(request.body)
        assert request.body['max_completion_tokens'] == 4096
        raise LLMError('Replayed HTTP400 json_validate_failed; no network')
    client = LLMClient(profile.proposed_settings('extraction'), transport=offline_transport)
    with pytest.raises(LLMError, match='json_validate_failed'):
        client.generate_json(purpose='extraction', system_prompt='Offline contract only', user_prompt='No network',
                             schema={'type': 'object'}, prompt_version='offline-replay')
    assert len(observed) == 1


def test_proposed_cap_serializes_without_fallback_and_returns_mock_json() -> None:
    """Wire support is tested separately from any claim of successful live completion."""
    def offline_transport(request: Any) -> dict[str, Any]:
        assert request.url == 'https://api.groq.com/openai/v1/chat/completions'
        assert request.body['max_completion_tokens'] == 4096
        assert request.body['response_format'] == {'type': 'json_object'}
        return {'choices': [{'message': {'content': '{}'}, 'finish_reason': 'stop'}]}
    call = LLMClient(profile.proposed_settings('verification'), transport=offline_transport).generate_json(
        purpose='verification', system_prompt='Offline contract only', user_prompt='No network', schema={'type': 'object'}, prompt_version='offline')
    # LLMClient records adapter transport as live; this test is explicitly mocked and is NOT evaluation evidence.
    assert call.max_tokens == 4096 and call.response_text == '{}'


def test_budget_is_bounded_and_new_evaluation_remains_unapproved() -> None:
    """The proposal has finite caps, unchanged labels, and no executable live action."""
    result = profile.budget()
    assert result['maximum_live_requests'] == 10 and result['nominal_requests'] == 8
    assert result['maximum_generated_tokens_all_calls'] == 40960
    assert result['max_estimated_single_request_reservation'] < 8000
    assert result['new_api_requests'] == 0
