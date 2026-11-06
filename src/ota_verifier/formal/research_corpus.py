"""Research campaign set derived from the frozen v1 corpus, without editing it.

Benchmark v1 stays hash-pinned as a regression artifact. Two of its core cases
are the same campaign under different names, so counting v1 cases overstates
coverage. Experiments use this derived set, where each campaign appears once.
"""
import hashlib
import json
from pathlib import Path
from typing import Any
from ..benchmark.corpus import CORPUS_SHA256, CORPUS_VERSION, CoreCase, load_corpus

RESEARCH_VERSION = 'ota-research-v1'
DEFAULT_PATH = Path(__file__).resolve().parents[3] / 'campaigns' / 'research_v1.json'


def fingerprint(case: CoreCase) -> str:
    """Hash what a case checks: its campaign and options, ignoring its names."""
    campaign = case.campaign.model_dump(mode='json', exclude={'id'})
    options = case.options.model_dump(mode='json')
    payload = json.dumps({'campaign': campaign, 'options': options}, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def _labels(case: CoreCase) -> tuple[Any, ...]:
    return (case.expected_planning, case.expected_makespan_ms, case.expected_baseline,
            case.expected_rollback_unavailable)


def build_research_corpus() -> dict[str, Any]:
    """Keep the first case of each duplicate group and merge the group's tags."""
    groups: dict[str, list[CoreCase]] = {}
    for case in load_corpus().core:
        groups.setdefault(fingerprint(case), []).append(case)
    campaigns, removed = [], []
    for digest, group in groups.items():
        kept = group[0]
        if any(_labels(case) != _labels(kept) for case in group):
            raise ValueError(f'Identical campaigns carry different labels: {[case.id for case in group]}')
        tags = sorted({tag for case in group for tag in case.tags})
        campaigns.append({'id': kept.id, 'fingerprint': digest, 'also_known_as': [case.id for case in group[1:]],
                          'tags': tags, 'case': kept.model_dump(mode='json')})
        removed.extend({'id': case.id, 'duplicate_of': kept.id} for case in group[1:])
    return {'version': RESEARCH_VERSION, 'source_corpus': CORPUS_VERSION, 'source_sha256': CORPUS_SHA256,
            'removed': removed, 'campaigns': campaigns}


def render(corpus: dict[str, Any]) -> str:
    """Serialize deterministically so the committed file can be compared exactly."""
    return json.dumps(corpus, indent=2, sort_keys=True) + '\n'


def is_current(path: Path = DEFAULT_PATH) -> bool:
    """Report whether the committed research set matches a fresh derivation."""
    return path.is_file() and json.loads(path.read_text(encoding='utf-8')) == build_research_corpus()


def main() -> None:
    """Regenerate the committed research set."""
    corpus = build_research_corpus()
    DEFAULT_PATH.parent.mkdir(exist_ok=True)
    DEFAULT_PATH.write_text(render(corpus), encoding='utf-8', newline='\n')
    print(f'{len(corpus["campaigns"])} campaigns, {len(corpus["removed"])} removed: {DEFAULT_PATH}')


if __name__ == '__main__':
    main()
