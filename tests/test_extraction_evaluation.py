"""Extraction error measurements include deterministic downstream consequences."""
import json
from typing import Any
import pytest
from ota_verifier.data.generate import generate_case
from ota_verifier.evaluation import compare_constraints, evaluate_case, fixture_client, main, summarize
from ota_verifier.llm.client import FixtureClient
from ota_verifier.llm.models import ExtractionRun
from ota_verifier.llm.pipeline import extract_and_verify
from ota_verifier.models import Requires


@pytest.mark.parametrize('profile', ['reference', 'omission', 'reversed', 'false_approval', 'malformed'])
def test_profiles_expose_distinct_errors(profile: str) -> None:
    case = generate_case('dependency_only')
    run = extract_and_verify(case.request, fixture_client(case, profile))
    row = evaluate_case(case, run)
    if profile == 'reference':
        assert row.run.status == 'ready'
        assert row.metrics.precision == row.metrics.recall == 1
        assert row.fault_outcome_differences == row.missed_fault_violations == 0
    elif profile == 'false_approval':
        assert row.run.status == 'ready'  # Both scripted responses made the same omission.
        assert row.accepted_semantic_error
        assert row.false_acceptance
        assert row.metrics.false_negatives == 1
        assert any(finding.code == 'incompatible_versions' for finding in row.truth_plan_violations)
        assert row.planning_status == 'feasible'
    else:
        assert row.run.status == 'blocked'
        assert row.planning_status == 'not_run'
        assert not row.false_acceptance


def test_equal_semantics_with_new_ids_do_not_create_false_safety_failures() -> None:
    case = generate_case()
    draft = json.loads(case.reference_draft.model_dump_json())
    for index, entry in enumerate(draft['constraints']):
        entry['constraint']['id'] = f'extracted-{index}'
    verdict = json.loads(case.reference_verdict.model_dump_json())
    verdict['reviewed_constraint_ids'] = [entry['constraint']['id'] for entry in draft['constraints']]
    run = extract_and_verify(case.request, FixtureClient((json.dumps(draft), json.dumps(verdict))))
    row = evaluate_case(case, run)
    assert row.run.status == 'ready'
    assert row.metrics.precision == row.metrics.recall == 1
    assert row.truth_plan_violations == ()
    assert not row.false_acceptance


def test_normalization_and_duplicate_penalty() -> None:
    case = generate_case('dependency_only')
    rule = case.truth_campaign.constraints[0]
    equivalent = Requires(**rule.model_dump(exclude={'version_spec', 'needs_version_spec'}),
                          version_spec='>=2.0', needs_version_spec='>=2.0.0')
    metrics = compare_constraints((rule,), (equivalent, equivalent))
    assert metrics.true_positives == metrics.false_positives == 1
    assert metrics.false_negatives == 0
    assert metrics.precision == 0.5
    assert metrics.recall == 1
    empty = compare_constraints((), ())
    assert empty.precision is empty.recall is None


def test_false_infeasibility_is_separate_from_unsafe_plan_acceptance() -> None:
    case = generate_case('dependency_only')
    draft = json.loads(case.reference_draft.model_dump_json())
    original = draft['constraints'][0]
    for index, (before, after) in enumerate((('gateway', 'brake'), ('brake', 'gateway'))):
        draft['constraints'].append({'constraint': dict(type='order', id=f'invented-{index}', before=before, after=after,
            source_document_id=original['constraint']['source_document_id'], source_text=original['constraint']['source_text']),
            'evidence': original['evidence']})
    verdict = json.loads(case.reference_verdict.model_dump_json())
    verdict['reviewed_constraint_ids'] = [entry['constraint']['id'] for entry in draft['constraints']]
    run = extract_and_verify(case.request, FixtureClient((json.dumps(draft), json.dumps(verdict))))
    row = evaluate_case(case, run)
    assert row.planning_status == 'infeasible'
    assert row.truth_planning_status == 'feasible'
    assert row.false_infeasibility
    assert row.accepted_semantic_error
    assert not row.false_acceptance


def test_unsupported_requirement_cannot_be_scored_as_safe_by_the_partial_core() -> None:
    case = generate_case('unsupported')
    # Deliberately suppress the unsupported requirement in both fixture responses.
    draft = '{"constraints":[],"issues":[]}'
    verdict = json.loads(case.reference_verdict.model_dump_json())
    verdict.update(faithful=True, issues=[])
    run = extract_and_verify(case.request, FixtureClient((draft, json.dumps(verdict))))
    row = evaluate_case(case, run)
    assert row.false_acceptance
    assert row.truth_planning_status == 'not_run'


def test_summary_denominators_and_blocked_only_rates() -> None:
    case = generate_case('dependency_only')
    run = extract_and_verify(case.request, fixture_client(case, 'false_approval'))
    row = evaluate_case(case, run, run_stress=False)
    report = summarize((row,), 'fixtures', 'false_approval')
    assert report.false_acceptances == report.false_acceptance_denominator == 1
    assert report.false_acceptance_rate == 1
    blocked = evaluate_case(case, extract_and_verify(case.request, fixture_client(case, 'malformed')))
    report = summarize((blocked,), 'fixtures', 'malformed')
    assert report.false_acceptance_rate is None
    assert report.ready_count == 0
    assert report.blocked_count == 1


def test_evaluation_rejects_foreign_run() -> None:
    case = generate_case(seed=0)
    other = generate_case(seed=1)
    run = extract_and_verify(other.request, fixture_client(other))
    with pytest.raises(ValueError, match='does not belong'):
        evaluate_case(case, run)


def test_fixture_evaluation_is_offline_and_truthful(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError('Offline fixture evaluation attempted a provider call')
    monkeypatch.setattr('ota_verifier.llm.client.LLMClient.generate_json', forbidden)
    assert main(['--mode', 'fixtures', '--no-stress']) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['mode'] == 'fixtures'
    assert report['ready_count'] == 4
    assert report['blocked_count'] == 2
    assert report['false_acceptances'] == 0
    assert all(call['origin'] == 'fixture' for case in report['cases'] for call in case['run']['calls'])


def test_cli_can_fail_on_false_acceptance(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(['--mode', 'fixtures', '--profile', 'false_approval', '--count', '2', '--no-stress', '--fail-on-false-acceptance']) == 4
    report = json.loads(capsys.readouterr().out)
    assert report['false_acceptances'] >= 1


def test_ambiguous_gold_intent_does_not_penalize_correct_abstention() -> None:
    case = generate_case('ambiguous')
    run = extract_and_verify(case.request, fixture_client(case))
    row = evaluate_case(case, run)
    assert row.metrics is None
    assert row.run.status == 'blocked'
    report = summarize((row,), 'fixtures', 'reference')
    assert report.semantically_evaluable_cases == 0
    assert report.micro_metrics.recall is None
    assert report.false_acceptances == 0
