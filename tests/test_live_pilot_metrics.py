"""Offline metric contracts for the bounded synthetic pilot, not live accuracy evidence."""
import importlib.util
from pathlib import Path
import sys

from ota_verifier.benchmark.corpus import load_corpus
from ota_verifier.evaluation import evaluate_case, fixture_client
from ota_verifier.llm.pipeline import extract_and_verify

spec = importlib.util.spec_from_file_location('live_pilot',Path(__file__).resolve().parents[1]/'eval/live_extraction/pilot.py')
pilot = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = pilot
spec.loader.exec_module(pilot)


def test_empty_pilot_denominators_are_undefined() -> None:
    """Not-run or empty data cannot become perfect accuracy."""
    result = pilot.score([],[])
    assert result['precision']['value'] is None
    assert result['recall']['value'] is None
    assert result['f1']['value'] is None
    assert result['real_document_metrics'] is None


def test_reference_semantic_metrics_exclude_unsupported_empty_gold() -> None:
    """Two supported cases supply five rules; the unsupported case is a separate abstention control."""
    corpus = load_corpus()
    cases = [case for case in corpus.development if case.id in pilot.IDS]
    evaluations = [evaluate_case(case,extract_and_verify(case.request,fixture_client(case)),run_stress=False) for case in cases]
    result = pilot.score(evaluations,cases)
    assert result['semantic_counts'] == {'true_positives':5,'false_positives':0,'false_negatives':0}
    assert result['supported_semantic_exact_match']['denominator'] == 2
    assert result['existing_extraction_metrics']['unsupported_or_ambiguous_acceptance']['denominator'] == 1
    assert result['existing_extraction_metrics']['faithfulness_false_acceptance']['value'] is None


def test_blocked_omission_still_counts_as_extraction_false_negative() -> None:
    """Verifier rejection does not erase a parseable extractor omission from accuracy metrics."""
    case = next(case for case in load_corpus().development if case.id=='clear-42')
    run = extract_and_verify(case.request,fixture_client(case,'omission'))
    assert run.status == 'blocked'
    result = pilot.score([evaluate_case(case,run,run_stress=False)],[case])
    assert result['semantic_counts'] == {'true_positives':2,'false_positives':0,'false_negatives':1}
    assert result['recall']['value'] == 2/3
