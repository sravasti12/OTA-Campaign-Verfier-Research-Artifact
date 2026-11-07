"""E5 stage 2: run every fault script in the SIL and compare with the frozen predictions.

For each run and property, the model predicted a violation or not, and the SIL observed
one or not. "Match" counts agreement, "miss" is a violation the model did not predict,
and "false alarm" is a predicted violation the SIL did not show. Mismatches are results,
so they are reported rather than treated as failures of this script.
"""
import csv
import hashlib
import importlib
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PROPERTIES = ('S1', 'S2', 'S3', 'S4', 'L1')
WORKERS = 6


def classify(predicted: bool, observed: bool) -> str:
    """Name one cell of the confusion table."""
    if predicted and observed:
        return 'match_violation'
    if not predicted and not observed:
        return 'match_safe'
    return 'false_alarm' if predicted else 'miss'


def compare(prediction: dict[str, Any], observed: dict[str, Any], edges: int = 1) -> dict[str, Any]:
    """Compare one run, by property and by exact path.

    S1 cannot be violated in a campaign with no dependency edges, so its cell is marked vacuous there.
    """
    cells = {prop: classify(prop in prediction['violated'], prop in observed['violated']) for prop in PROPERTIES}
    return {'campaign': prediction['campaign'], 'design': prediction['design'], 'policy': prediction['policy'],
            'script': prediction['script'], 'faults': json.dumps(prediction['faults']),
            'path_key': hashlib.sha256(json.dumps(prediction['actions']).encode()).hexdigest()[:16],
            's1_vacuous': edges == 0,
            'predicted': ' '.join(prediction['violated']), 'observed': ' '.join(sorted(observed['violated'])),
            'same_path': [list(step) for step in prediction['actions']] == observed['actions'],
            'same_end': prediction['final'] == observed['campaign'] and prediction['active'] == observed['running'],
            **cells}


def distinct(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep one row per campaign, design, policy, predicted path and set of verdicts.

    Many fault scripts lead to the same run, so counting every script would weight repeated runs.
    """
    seen, kept = set(), []
    for row in rows:
        key = (row['campaign'], row['design'], row['policy'], row['path_key'], *(row[prop] for prop in PROPERTIES))
        if key not in seen:
            seen.add(key)
            kept.append(row)
    return kept


def confusion(rows: list[dict[str, Any]], key: str | None) -> list[dict[str, Any]]:
    """Count cells overall, or grouped by a column or by property. Vacuous S1 cells are left out."""
    groups: dict[str, Counter[str]] = {}
    for row in rows:
        for prop in PROPERTIES:
            if prop == 'S1' and row['s1_vacuous']:
                continue
            name = 'all' if key is None else prop if key == 'property' else row[key]
            groups.setdefault(name, Counter())[row[prop]] += 1
    return [{'group': name, 'match_violation': counts['match_violation'], 'match_safe': counts['match_safe'],
             'miss': counts['miss'], 'false_alarm': counts['false_alarm']} for name, counts in groups.items()]


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run(run_dir: Path, _jar: Path, root: Path) -> list[str]:
    """Run the sweep. Only a crash in the harness counts as a problem."""
    sys.path.insert(0, str(HERE))
    sys.path.insert(0, str(root / 'sil'))
    harness = importlib.import_module('harness')
    common = importlib.import_module('e5_common')
    source = root / 'results' / 'predictions' / 'e5' / 'predictions.jsonl'
    raw = source.read_bytes()
    (run_dir / 'predictions_sha256.txt').write_text(hashlib.sha256(raw).hexdigest() + '\n', encoding='utf-8')
    predictions = [json.loads(line) for line in raw.decode('utf-8').splitlines()]
    campaigns = common.campaigns()
    rows, problems = [], []
    total = len(predictions)

    def attempt(prediction: dict[str, Any]) -> Any:
        campaign = campaigns[prediction['campaign']]
        setup = harness.Setup(tuple(campaign['ecus']), tuple(tuple(edge) for edge in campaign['edges']),
                              prediction['design'], prediction['policy'])
        try:
            return harness.execute(setup, prediction['faults'])
        except Exception as error:  # A crash must be visible, not silently skipped.
            return error

    # Each run has its own processes and temporary folder, so runs cannot affect each other.
    with ThreadPoolExecutor(WORKERS) as pool, \
            (run_dir / 'observations.jsonl').open('w', encoding='utf-8', newline='\n') as handle:
        for prediction, result in zip(predictions, pool.map(attempt, predictions)):
            if isinstance(result, Exception):
                problems.append(f'{prediction["campaign"]} {prediction["design"]} script {prediction["script"]}: {result!r}')
                continue
            observed = {'violated': sorted(result.violated), 'actions': result.actions, 'campaign': result.campaign,
                        'running': result.running}
            # 'campaign' in an observation is the end state, so the run's name goes under 'campaign_name'.
            identity = {'campaign_name': prediction['campaign'], **{key: prediction[key] for key in ('design', 'policy', 'script')}}
            handle.write(json.dumps(identity | observed) + '\n')
            handle.flush()
            rows.append(compare(prediction, observed, len(campaigns[prediction['campaign']]['edges'])))
            if len(rows) % 200 == 0:
                (run_dir / 'progress.json').write_text(json.dumps({'done': len(rows) + len(problems), 'total': total}) + '\n',
                                                       encoding='utf-8')
    write_csv(run_dir / 'comparison.csv', rows)
    table = [{'view': 'all', **row} for row in confusion(rows, None)]
    for view in ('property', 'design', 'campaign', 'policy'):
        table += [{'view': view, **row} for row in confusion(rows, view)]
    unique = distinct(rows)
    table += [{'view': 'distinct_all', **row} for row in confusion(unique, None)]
    for view in ('property', 'design'):
        table += [{'view': f'distinct_{view}', **row} for row in confusion(unique, view)]
    write_csv(run_dir / 'confusion.csv', table)
    (root / 'results' / 'confusion.csv').write_bytes((run_dir / 'confusion.csv').read_bytes())
    return problems
