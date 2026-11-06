"""The research campaign set must stay derived from, and separate from, frozen v1."""
import pytest
from ota_verifier.benchmark.corpus import load_corpus
from ota_verifier.formal import research_corpus
from ota_verifier.formal.research_corpus import build_research_corpus, fingerprint, is_current


def test_each_campaign_appears_once_and_the_known_duplicate_is_recorded() -> None:
    corpus = build_research_corpus()
    prints = [row['fingerprint'] for row in corpus['campaigns']]
    assert len(prints) == len(set(prints)) == 10
    assert corpus['removed'] == [{'id': 'core-rollback-trap', 'duplicate_of': 'core-parallel'}]


def test_merged_case_keeps_tags_of_the_removed_name() -> None:
    row = next(row for row in build_research_corpus()['campaigns'] if row['id'] == 'core-parallel')
    assert row['also_known_as'] == ['core-rollback-trap']
    assert {'parallel', 'rollback_trap', 'unauthorized_rollback'} <= set(row['tags'])


def test_fingerprint_ignores_names_but_not_content() -> None:
    cases = {case.id: case for case in load_corpus().core}
    assert fingerprint(cases['core-parallel']) == fingerprint(cases['core-rollback-trap'])
    assert fingerprint(cases['core-parallel']) != fingerprint(cases['core-authorized-recovery'])
    assert fingerprint(cases['core-parallel']) != fingerprint(cases['core-serial'])


def test_conflicting_labels_on_identical_campaigns_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    corpus = load_corpus()
    altered = tuple(case.model_copy(update={'expected_baseline': 'passed'}) if case.id == 'core-rollback-trap'
                    else case for case in corpus.core)
    monkeypatch.setattr(research_corpus, 'load_corpus', lambda: corpus.model_copy(update={'core': altered}))
    with pytest.raises(ValueError, match='different labels'):
        build_research_corpus()


def test_committed_file_matches_a_fresh_derivation() -> None:
    assert is_current()
