"""Frozen benchmarks, honest metric denominators, and no-model core checks."""
import json
from pathlib import Path
from typing import Any
import pytest
from ota_verifier.benchmark.corpus import CORPUS_SHA256, build_corpus, corpus_hash, load_corpus
from ota_verifier.benchmark.metrics import extraction_metrics
from ota_verifier.benchmark.oracle import exhaustive_optimum
from ota_verifier.benchmark.runner import main, run_benchmark
from ota_verifier.evaluation import fixture_client
from ota_verifier.llm.client import FixtureClient
from ota_verifier.llm.pipeline import extract_and_verify
from ota_verifier.models import Campaign, FeasibleResult, PlanningOptions
from ota_verifier.planner import plan_campaign


def test_frozen_corpus_matches_generator_and_has_disjoint_templates() -> None:
    corpus = load_corpus()
    assert corpus == build_corpus()
    assert corpus_hash(corpus) == CORPUS_SHA256
    assert len(corpus.core) == 11
    assert len(corpus.development) == len(corpus.heldout) == 6
    development_text = {document.text for case in corpus.development for document in case.request.documents}
    heldout_text = {document.text for case in corpus.heldout for document in case.request.documents}
    assert development_text.isdisjoint(heldout_text)
    assert {'rollback_trap', 'dependency_cycle', 'incompatible_intermediate', 'concurrency_limit', 'infeasible'} <= {tag for case in corpus.core for tag in case.tags}


def test_corpus_edits_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('ota_verifier.benchmark.corpus.CORPUS_SHA256', '0' * 64)
    with pytest.raises(ValueError, match='hash mismatch'):
        load_corpus()


def test_complete_core_benchmark_has_no_model_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError('Core attempted a model call')
    monkeypatch.setattr('ota_verifier.llm.client.LLMClient.generate_json', forbidden)
    monkeypatch.setattr('ota_verifier.llm.client.FixtureClient.generate_json', forbidden)
    monkeypatch.setattr('ota_verifier.llm.explainer.FixtureExplanationClient.generate_json', forbidden)
    report = run_benchmark(mode='core')
    assert report.checks_passed
    assert report.extraction == report.call_timings == ()
    assert all(row.checks_passed for row in report.core)
    assert sum(row.fault_cases for row in report.core) == 252
    assert all(row.fault_cases == row.expected_fault_cases for row in report.core)
    assert next(row for row in report.core if row.case_id == 'core-authorized-recovery').rollback_unavailable_cases == 0
    assert next(row for row in report.core if row.case_id == 'core-rollback-trap').rollback_unavailable_cases > 0


@pytest.mark.parametrize('split', ['development', 'heldout'])
def test_reference_fixture_metrics_are_exact_and_explicit(split: str, monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError('Fixture benchmark attempted provider access')
    monkeypatch.setattr('ota_verifier.llm.client.LLMClient.generate_json', forbidden)
    report = run_benchmark(split=split)
    assert report.checks_passed
    assert report.mode == 'fixtures'
    assert len(report.extraction) == 6
    assert all(metric.precision == metric.recall == 1 for metric in report.metrics.per_constraint_type.values())
    assert report.metrics.evidence_span_accuracy.value == 1
    assert report.metrics.evidence_span_recall.value == 1
    assert report.metrics.faithfulness_false_acceptance.value is None
    assert report.metrics.schema_rejection.value == 0
    assert report.metrics.unsupported_or_ambiguous_acceptance.value == 0
    assert report.metrics.valid_case_blocking.value == 0
    assert len(report.call_timings) == 10  # Extraction issues stop before verification.
    assert all(timing.elapsed_ms >= 0 for timing in report.call_timings)
    assert all(call.origin == 'fixture' for case in report.extraction for call in case.run.calls)


@pytest.mark.parametrize('profile', ['omission', 'reversed', 'false_approval', 'malformed'])
def test_negative_profiles_expose_failures(profile: str) -> None:
    report = run_benchmark(profile=profile)
    assert not report.checks_passed
    if profile == 'false_approval':
        assert report.metrics.faithfulness_false_acceptance.value == 1
        assert any(case.false_acceptance for case in report.extraction)
        assert report.metrics.per_constraint_type['requires'].recall < 1
    elif profile == 'malformed':
        assert report.metrics.schema_rejection.value == 1
        assert report.metrics.valid_case_blocking.value == 1
    else:
        assert report.metrics.faithfulness_false_acceptance.value == 0
        assert report.metrics.valid_case_blocking.value > 0


def test_semantic_digest_excludes_observed_timings() -> None:
    first, second = run_benchmark(), run_benchmark()
    assert first.semantic_digest == second.semantic_digest
    assert first.call_timings != second.call_timings


def test_empty_metric_denominators_are_undefined() -> None:
    metrics = extraction_metrics(())
    assert metrics.evidence_span_accuracy.value is None
    assert metrics.faithfulness_false_acceptance.value is None
    assert metrics.schema_rejection.value is None
    assert metrics.unsupported_or_ambiguous_acceptance.value is None


def test_semantically_correct_wrong_citation_is_not_a_correct_gold_span() -> None:
    case = load_corpus().heldout[1]
    draft = case.reference_draft.model_dump(mode='json')
    entry = draft['constraints'][0]
    # A legal source segment exists, but it does not support the dependency.
    from ota_verifier.llm.evidence import source_segments
    segment = source_segments(case.request.documents[0])[0]
    entry['evidence'] = segment.evidence.model_dump(mode='json')
    entry['constraint']['source_text'] = segment.text
    run = extract_and_verify(case.request, FixtureClient((json.dumps(draft), case.reference_verdict.model_dump_json())))
    metrics = extraction_metrics(((case, run),))
    assert metrics.per_constraint_type['requires'].precision == 1
    assert metrics.evidence_span_accuracy.denominator == 1
    assert metrics.evidence_span_accuracy.value == 0
    assert metrics.evidence_span_precision.value == 0


def test_per_case_errors_cannot_cancel_in_aggregate() -> None:
    cases = [case for case in load_corpus().heldout if case.scenario in ('clear', 'dependency_only')]
    first, second = cases
    # Omit the shared dependency from one case; duplicate it in another.
    draft1 = first.reference_draft.model_copy(update={'constraints': tuple(entry for entry in first.reference_draft.constraints if entry.constraint.type != 'requires')})
    duplicate = second.reference_draft.constraints[0]
    duplicate = duplicate.model_copy(update={'constraint': duplicate.constraint.model_copy(update={'id': 'duplicate'})})
    draft2 = second.reference_draft.model_copy(update={'constraints': (*second.reference_draft.constraints, duplicate)})
    verdict1 = first.reference_verdict.model_copy(update={'reviewed_constraint_ids': tuple(entry.constraint.id for entry in draft1.constraints)})
    verdict2 = second.reference_verdict.model_copy(update={'reviewed_constraint_ids': tuple(entry.constraint.id for entry in draft2.constraints)})
    run1 = extract_and_verify(first.request, FixtureClient((draft1.model_dump_json(), verdict1.model_dump_json())))
    run2 = extract_and_verify(second.request, FixtureClient((draft2.model_dump_json(), verdict2.model_dump_json())))
    metrics = extraction_metrics(((first, run1), (second, run2))).per_constraint_type['requires']
    assert metrics.true_positives == metrics.false_positives == metrics.false_negatives == 1
    assert metrics.precision == metrics.recall == 0.5


@pytest.mark.parametrize('case', load_corpus().core, ids=lambda case: case.id)
def test_tiny_oracle_and_metamorphic_input_reordering(case: Any) -> None:
    expected = exhaustive_optimum(case.campaign, case.options)
    # Renaming source constraint IDs and reordering inventory/rules preserve meaning.
    source = case.campaign.model_dump(mode='json')
    source['ecus'].reverse()
    source['initial_state']['ecus'].reverse()
    source['constraints'].reverse()
    for index, rule in enumerate(source['constraints']):
        rule['id'] = f'renamed-{index}'
    transformed = Campaign.model_validate_json(json.dumps(source))
    result = plan_campaign(transformed, case.options)
    assert exhaustive_optimum(transformed, case.options) == expected
    assert (result.status == 'feasible') == (expected is not None)
    if isinstance(result, FeasibleResult):
        assert result.plan.makespan_ms == expected


def test_relaxing_capacity_cannot_increase_optimal_duration() -> None:
    campaign = load_corpus().core[0].campaign
    durations = []
    for capacity in (1, 2, 3):
        result = plan_campaign(campaign, PlanningOptions(max_parallel=capacity))
        assert isinstance(result, FeasibleResult)
        durations.append(result.plan.makespan_ms)
    assert durations == sorted(durations, reverse=True)


def test_oracle_refuses_out_of_scope_inputs() -> None:
    case = load_corpus().core[0]
    with pytest.raises(ValueError, match='deadlines'):
        exhaustive_optimum(case.campaign, PlanningOptions(deadline_ms=1))
    changed = case.campaign.model_copy(update={'ecus': tuple(ecu.model_copy(update={'flash_minutes': 0.5}) for ecu in case.campaign.ecus)})
    with pytest.raises(ValueError, match='Oracle supports'):
        exhaustive_optimum(changed, case.options)


def test_cli_offline_report_and_no_overwrite(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output = tmp_path / 'report.json'
    assert main(['--mode', 'core', '--output', str(output), '--fail-on-findings']) == 0
    report = json.loads(capsys.readouterr().out)
    assert json.loads(output.read_text()) == report
    assert report['checks_passed']
    with pytest.raises(SystemExit):
        main(['--output', str(output)])
    assert json.loads(output.read_text()) == report


def test_cli_fails_on_measured_errors(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(['--profile', 'false_approval', '--fail-on-findings']) == 4
    assert json.loads(capsys.readouterr().out)['checks_passed'] is False


def test_live_mode_cannot_be_inferred_or_labeled_from_fixtures() -> None:
    with pytest.raises(ValueError, match='explicit clients'):
        run_benchmark(mode='live')
    with pytest.raises(ValueError, match='Offline'):
        run_benchmark(clients=(FixtureClient(()), FixtureClient(())))


def test_live_api_rejects_fixture_origin() -> None:
    from ota_verifier.llm.client import ClientSettings
    from ota_verifier.persistence.recipes import PublicSettings
    settings = PublicSettings.capture(ClientSettings(provider='ollama', model='mock'))
    case = load_corpus().heldout[0]
    client = fixture_client(case)
    with pytest.raises(ValueError, match='Fixture responses'):
        run_benchmark(mode='live', clients=(client, client),
            provider_configuration={'extraction': settings, 'verification': settings})


def test_live_adapter_with_mock_transport_retains_config_without_credentials() -> None:
    from collections import deque
    from pydantic import SecretStr
    from ota_verifier.llm.client import ClientSettings, HttpRequest, LLMClient
    from ota_verifier.persistence.recipes import PublicSettings
    responses = deque()
    for case in load_corpus().heldout:
        responses.append(case.reference_draft.model_dump_json())
        if not case.expected_blocked:
            responses.append(case.reference_verdict.model_dump_json())
    sent = []
    def transport(request: HttpRequest) -> dict[str, Any]:
        sent.append(request)
        prompt = request.body['messages'][-1]['content']
        assert 'truth_campaign' not in prompt
        assert 'reference_draft' not in prompt
        assert 'expected_blocked' not in prompt
        return {'done': True, 'done_reason': 'stop', 'message': {'content': responses.popleft()}}
    settings = ClientSettings(provider='ollama', model='mock-not-a-real-model', api_key=SecretStr('test-only-secret'))
    client = LLMClient(settings, transport=transport)
    public = PublicSettings.capture(settings)
    report = run_benchmark(mode='live', clients=(client, client), provider_configuration={'extraction': public, 'verification': public})
    assert report.checks_passed
    assert len(sent) == len(report.call_timings) == 10
    assert 'test-only-secret' not in report.model_dump_json()
    assert report.mode == 'live'
    assert report.provider_configuration['extraction'].model == settings.model
    assert all(call.origin == 'live' for row in report.extraction for call in row.run.calls)


def test_schema_rejection_is_distinct_from_transport_failure() -> None:
    from ota_verifier.llm.client import LLMError
    class FailedClient:
        def generate_json(self, **kwargs: Any) -> Any:
            raise LLMError('Mock transport unavailable')
    case = load_corpus().heldout[1]
    run = extract_and_verify(case.request, FailedClient())
    metrics = extraction_metrics(((case, run),))
    assert metrics.schema_rejection.denominator == 0
    assert metrics.schema_rejection.value is None
    assert metrics.missing_extraction_responses == 1
    assert metrics.valid_case_blocking.value == 1


def test_cli_negative_profile_cannot_trigger_live_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError('Invalid arguments attempted credential loading')
    monkeypatch.setattr('ota_verifier.benchmark.runner.ClientSettings.from_env', forbidden)
    with pytest.raises(SystemExit):
        main(['--mode', 'live', '--profile', 'malformed'])


def test_reference_summary_matches_recorded_baseline() -> None:
    baseline = json.loads((Path(__file__).parents[1] / 'eval' / 'baseline_v1.json').read_text(encoding='utf-8-sig'))
    report = run_benchmark(split='all')
    assert report.corpus_sha256 == baseline['corpus_sha256']
    assert report.metrics.model_dump(mode='json') == baseline['metrics']
    assert [row.model_dump(mode='json') for row in report.core] == baseline['core']
    assert sum(row.run.status == 'ready' for row in report.extraction) == baseline['extraction_ready']
    assert sum(row.run.status == 'blocked' for row in report.extraction) == baseline['extraction_blocked']


def test_tight_deadline_rejection_becomes_feasible_when_relaxed() -> None:
    case = next(case for case in load_corpus().core if case.id == 'core-deadline')
    assert plan_campaign(case.campaign, case.options).status == 'infeasible'
    relaxed = case.options.model_copy(update={'deadline_ms': 180000})
    result = plan_campaign(case.campaign, relaxed)
    assert isinstance(result, FeasibleResult)
    assert result.plan.makespan_ms == exhaustive_optimum(case.campaign, relaxed) == 180000


def test_granting_recovery_permission_does_not_change_nominal_schedule() -> None:
    cases = {case.id: case for case in load_corpus().core}
    before, after = cases['core-rollback-trap'], cases['core-authorized-recovery']
    assert before.campaign.ecus == after.campaign.ecus
    first = plan_campaign(before.campaign, before.options)
    second = plan_campaign(after.campaign, after.options)
    assert isinstance(first, FeasibleResult) and isinstance(second, FeasibleResult)
    assert first.plan.steps == second.plan.steps
    assert first.plan.makespan_ms == second.plan.makespan_ms


def test_core_mode_rejects_unused_fixture_profile() -> None:
    with pytest.raises(ValueError, match='Fixture profiles'):
        run_benchmark(mode='core', profile='malformed')


def test_wrong_gold_citation_fails_benchmark_even_if_semantics_match(monkeypatch: pytest.MonkeyPatch) -> None:
    from ota_verifier.llm.evidence import source_segments
    corpus = load_corpus()
    case = corpus.heldout[1]
    draft = case.reference_draft.model_dump(mode='json')
    segment = source_segments(case.request.documents[0])[0]
    draft['constraints'][0]['evidence'] = segment.evidence.model_dump(mode='json')
    draft['constraints'][0]['constraint']['source_text'] = segment.text
    monkeypatch.setattr('ota_verifier.benchmark.runner.load_corpus', lambda: corpus.model_copy(update={'heldout': (case,)}))
    monkeypatch.setattr('ota_verifier.benchmark.runner.fixture_client',
        lambda *args: FixtureClient((json.dumps(draft), case.reference_verdict.model_dump_json())))
    report = run_benchmark()
    assert report.metrics.per_constraint_type['requires'].precision == 1
    assert report.metrics.evidence_span_accuracy.value == 0
    assert report.checks_passed is False
