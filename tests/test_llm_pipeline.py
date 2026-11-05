"""Fail-closed extraction/verification and reproducible handoff evidence."""
import json
from typing import Any
import pytest
from ota_verifier.data.generate import generate_case
from ota_verifier.evaluation import fixture_client
from ota_verifier.llm.client import FixtureClient, LLMError
from ota_verifier.llm.models import DocumentRequest, ExtractionRun
from ota_verifier.llm.pipeline import extract_and_verify, verified_campaign
from ota_verifier.models import FeasibleResult
from ota_verifier.planner import plan_campaign
from ota_verifier.simulator import stress_test


@pytest.mark.parametrize(('scenario', 'expected'), [('clear', 'ready'), ('dependency_only', 'ready'),
    ('order_conflict', 'ready'), ('intermediate_trap', 'ready'), ('ambiguous', 'blocked'), ('unsupported', 'blocked')])
def test_reference_handoff(scenario: str, expected: str) -> None:
    case = generate_case(scenario)
    run = extract_and_verify(case.request, fixture_client(case))
    assert run.status == expected
    assert all(call.origin == 'fixture' for call in run.calls)
    restored = ExtractionRun.model_validate_json(run.model_dump_json())
    assert restored == run
    if expected == 'ready':
        assert len(run.calls) == 2
        assert verified_campaign(restored) == case.truth_campaign
    else:
        assert len(run.calls) == 1  # Deterministic/extractor review issue already blocks the handoff.
        assert run.campaign is None
        with pytest.raises(ValueError, match='blocked'):
            verified_campaign(run)


@pytest.mark.parametrize(('mutation', 'code'), [('unknown_ecu', 'reference_error'), ('wrong_doc', 'source_error'),
    ('wrong_quote', 'source_error'), ('wrong_offset', 'source_error'), ('duplicate', 'duplicate_constraint')])
def test_deterministic_errors_block_before_verifier(mutation: str, code: str) -> None:
    case = generate_case()
    draft = json.loads(case.reference_draft.model_dump_json())
    entry = draft['constraints'][0]
    if mutation == 'unknown_ecu':
        entry['constraint']['needs'] = 'unknown'
    elif mutation == 'wrong_doc':
        entry['constraint']['source_document_id'] = 'unknown'
    elif mutation == 'wrong_quote':
        entry['constraint']['source_text'] += ' invented'
    elif mutation == 'wrong_offset':
        entry['evidence']['start_char'] += 1
    else:
        draft['constraints'].append(entry)
    run = extract_and_verify(case.request, FixtureClient((json.dumps(draft),)))
    assert run.status == 'blocked'
    assert code in {issue.code for issue in run.issues}
    assert len(run.calls) == 1


@pytest.mark.parametrize('raw', ['{}', '{"constraints":[],"issues":[],"plan":[]}',
    '{"constraints":[],"constraints":[],"issues":[]}', '```json\n{}\n```'])
def test_malformed_extraction_preserves_raw_response(raw: str) -> None:
    case = generate_case()
    run = extract_and_verify(case.request, FixtureClient((raw,)))
    assert run.status == 'blocked'
    assert run.draft is None
    assert run.calls[0].response_text == raw
    assert run.issues[0].code == 'llm_boundary_error'


@pytest.mark.parametrize('profile', ['omission', 'reversed'])
def test_separate_review_detects_semantically_wrong_but_well_formed_draft(profile: str) -> None:
    case = generate_case('dependency_only')
    run = extract_and_verify(case.request, fixture_client(case, profile))
    assert run.status == 'blocked'
    assert len(run.calls) == 2
    assert run.verification.faithful is False
    assert {'missing_requirement', 'incorrect_constraint'} & {issue.code for issue in run.issues}


@pytest.mark.parametrize('mutation', ['missing_doc', 'missing_constraint', 'duplicate_doc', 'wrong_issue_ref', 'invalid_quote', 'false_without_findings', 'approval_with_issues'])
def test_invalid_verification_cannot_approve(mutation: str) -> None:
    case = generate_case()
    verdict = json.loads(case.reference_verdict.model_dump_json())
    if mutation == 'missing_doc':
        verdict['reviewed_document_ids'].pop()
    elif mutation == 'missing_constraint':
        verdict['reviewed_constraint_ids'].pop()
    elif mutation == 'duplicate_doc':
        verdict['reviewed_document_ids'].append(verdict['reviewed_document_ids'][0])
    elif mutation == 'false_without_findings':
        verdict['faithful'] = False
    else:
        entry = case.reference_draft.constraints[0]
        verdict['faithful'] = mutation == 'approval_with_issues'
        verdict['issues'] = [dict(kind='incorrect_constraint', constraint_id='unknown' if mutation == 'wrong_issue_ref' else entry.constraint.id,
            evidence=entry.evidence.model_dump(), source_text='invented' if mutation == 'invalid_quote' else entry.constraint.source_text,
            message='Cannot establish support')]
    run = extract_and_verify(case.request, FixtureClient((case.reference_draft.model_dump_json(), json.dumps(verdict))))
    assert run.status == 'blocked'
    assert len(run.calls) == 2
    assert run.campaign is None


@pytest.mark.parametrize('mutation', ['source', 'request_hash', 'raw_response', 'campaign_permission', 'call_payload'])
def test_saved_evidence_changes_cannot_bypass_handoff_recheck(mutation: str) -> None:
    case = generate_case()
    run = extract_and_verify(case.request, fixture_client(case))
    raw = json.loads(run.model_dump_json())
    if mutation == 'source':
        raw['request']['documents'][0]['text'] += ' Changed.'
    elif mutation == 'request_hash':
        raw['input_hash'] = '0' * 64
    elif mutation == 'raw_response':
        raw['calls'][0]['response_text'] = '{"constraints":[],"issues":[]}'
    elif mutation == 'call_payload':
        raw['calls'][0]['request_json'] += ' '
    else:
        raw['campaign']['downgrade_authorizations'] = [dict(ecu_id='gateway', version='1', authorized_by='invented', reason='Not authoritative')]
    changed = ExtractionRun.model_validate_json(json.dumps(raw))
    with pytest.raises(ValueError):
        verified_campaign(changed)


def test_oversized_sources_are_blocked_without_truncation_or_calls() -> None:
    case = generate_case()
    raw = json.loads(case.request.model_dump_json())
    raw['documents'][0]['text'] = 'x' * 100001
    request = DocumentRequest.model_validate_json(json.dumps(raw))
    run = extract_and_verify(request, FixtureClient(()))
    assert run.status == 'blocked'
    assert run.issues[0].code == 'input_too_large'
    assert run.calls == ()
    assert len(run.request.documents[0].text) == 100001


def test_boundary_error_is_reported_without_inventing_a_verdict() -> None:
    class FailedClient:
        def generate_json(self, **kwargs: Any) -> Any:
            raise LLMError('Provider connection failed')
    case = generate_case()
    run = extract_and_verify(case.request, FailedClient())
    assert run.status == 'blocked'
    assert run.verification is None
    assert run.calls == ()


def test_deterministic_core_never_calls_the_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    case = generate_case()
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError('Deterministic code attempted an LLM call')
    monkeypatch.setattr('ota_verifier.llm.client.LLMClient.generate_json', forbidden)
    result = plan_campaign(case.truth_campaign)
    assert isinstance(result, FeasibleResult)
    assert stress_test(case.truth_campaign, result.plan).nominal.assessment == 'passed'
