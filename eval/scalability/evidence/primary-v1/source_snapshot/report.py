"""Verified aggregation and standalone plots of actual recorded scalability trials."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import json
import logging
from math import ceil
from pathlib import Path
import statistics
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'eval')]
from scalability.run import file_hash
from scalability.worker import write_json
from scalability.workloads import FAMILIES, SIZES


def describe(values: list[float]) -> dict[str, float | int | None]:
    """Retain sample size and nearest-rank p95; undefined statistics are null."""
    ordered = sorted(values)
    return {'n': len(values), 'median': statistics.median(values) if values else None,
            'p95_nearest_rank': ordered[ceil(0.95*len(ordered))-1] if values else None,
            'min': min(values) if values else None, 'max': max(values) if values else None}


def verify(directory: Path) -> int:
    """Verify every frozen file, rejecting missing evidence and escaping paths."""
    manifest = json.loads((directory / 'SHA256SUMS.json').read_text(encoding='utf-8'))
    for relative, expected in manifest.items():
        path = (directory / relative).resolve()
        if not path.is_relative_to(directory.resolve()) or file_hash(path) != expected:
            raise ValueError(f'Invalid evidence artifact: {path}')
    return len(manifest)


def summarize(directory: Path) -> dict[str, Any]:
    """Aggregate all scheduled measured rows, including unknown/failed/not-run outcomes."""
    verified = verify(directory)
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    rows = [json.loads(line) for line in (directory / 'trials.jsonl').read_text(encoding='utf-8').splitlines()]
    if [row['trial_id'] for row in rows] != [trial['trial_id'] for trial in manifest['trials']]:
        raise ValueError('A scheduled trial is missing, duplicated or out of order')
    measured = [row for row in rows if row['role'] == 'measured']
    groups: dict[tuple[str, int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in measured:
        groups[(row['family'], row['size'], row['algorithm'])].append(row)
    cells = []
    for (family, size, algorithm), values in sorted(groups.items()):
        memories = [row['memory_after_api']['peak_bytes']/1024**2 for row in values
                    if row.get('memory_after_api', {}).get('peak_bytes') is not None]
        cores = [len(row['conflict']['items']) for row in values if row.get('conflict')]
        cells.append({'family': family, 'size': size, 'algorithm': algorithm,
            'scheduled': len(values), 'statuses': dict(Counter(row['status'] for row in values)),
            'api_ms': describe([row['planner_api_ms'] for row in values if row.get('planner_api_ms') is not None]),
            'worker_ms': describe([row['worker_total_ms'] for row in values if row.get('worker_total_ms') is not None]),
            'external_validation_ms': describe([row['external_validation_ms'] for row in values if row.get('external_validation_ms') is not None]),
            'api_peak_working_set_mib': describe(memories), 'core_items': describe(cores),
            'subset_minimal_cores': sum(bool(row.get('conflict', {}).get('subset_minimal')) for row in values if row.get('conflict')),
            'feasible_optimal': sum(row['status'] == 'feasible' and row.get('optimal') is True for row in values),
            'feasible_unproven': sum(row['status'] == 'feasible' and row.get('optimal') is False for row in values),
            'parent_censored_memory': sum(bool(row.get('parent_peak_censored')) for row in values)})
    seed_groups: dict[tuple[str, int, int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in measured:
        seed_groups[(row['family'], row['size'], row['seed'], row['algorithm'])].append(row)
    per_seed = [{'family': family, 'size': size, 'seed': seed, 'algorithm': algorithm,
                 'statuses': dict(Counter(row['status'] for row in values)),
                 'api_ms': describe([row['planner_api_ms'] for row in values if row.get('planner_api_ms') is not None])}
                for (family, size, seed, algorithm), values in sorted(seed_groups.items())]
    pairs: dict[tuple[str, int], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in measured:
        pairs[(row['input_key'], row['repetition'])][row['algorithm']] = row
    paired = []
    for (key, repetition), values in pairs.items():
        z3, baseline = values.get('z3'), values.get('sequential')
        comparable = bool(z3 and baseline and z3['status'] == baseline['status'] == 'feasible')
        paired.append({'input_key': key, 'repetition': repetition, 'comparable': comparable,
            'family': (z3 or baseline)['family'], 'size': (z3 or baseline)['size'],
            'makespan_ratio_sequential_over_z3': baseline['makespan_ms']/z3['makespan_ms'] if comparable else None,
            'api_runtime_ratio_sequential_over_z3': baseline['planner_api_ms']/z3['planner_api_ms'] if comparable else None,
            'z3_optimal': z3.get('optimal') if z3 else None,
            'z3_status': z3['status'] if z3 else 'MISSING',
            'sequential_status': baseline['status'] if baseline else 'MISSING'})
    return {'format': 'scalability-summary-v1', 'source_directory': str(directory), 'profile': manifest['profile'],
        'verified_artifacts': verified, 'synthetic_only': True,
        'warmup_rows': sum(row['role'] == 'warmup' for row in rows), 'measured_rows': len(measured),
        'z3_statuses': dict(Counter(row['status'] for row in measured if row['algorithm'] == 'z3')),
        'baseline_statuses': dict(Counter(row['status'] for row in measured if row['algorithm'] == 'sequential')),
        'completion': json.loads((directory / 'completion.json').read_text(encoding='utf-8')),
        'cells': cells, 'per_seed': per_seed, 'pairs': paired,
        'limitations': ['API timing includes construction, optimization and internal replay, not pure solver check time.',
            'Latency/memory statistics require a returned API result; watchdog rows are separate, not zero-valued samples.',
            'Memory includes imports/Python/native allocations; it is not isolated Z3 heap allocation.',
            'Greedy sequential baseline is not a complete feasibility solver or parallel optimizer.',
            'Host not dedicated; results are machine/workload specific, not vehicle-fleet measurements.',
            'Nearest-rank p95 with fifteen observations per cell is descriptive, not a population-tail estimate.']}


def plots(summary: dict[str, Any], output: Path) -> None:
    """Plot measured values with missing/censored outcomes explicitly separated."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'svg.hashsalt': 'ota-scalability-v1', 'font.size': 8})
    cells = {(row['family'], row['size'], row['algorithm']): row for row in summary['cells']}
    for field, title, filename in (
        ('api_ms', 'Completed planning API time (ms; includes build/optimization/internal replay)', 'api_latency'),
        ('api_peak_working_set_mib', 'Completed API peak working set (MiB; includes imports/native allocations)', 'memory')):
        fig, axes = plt.subplots(2, 5, figsize=(16, 6), sharex=True)
        for family, axis in zip(FAMILIES, axes.flat):
            for algorithm, color in (('z3', 'tab:blue'), ('sequential', 'tab:orange')):
                found = [(size, cells[(family, size, algorithm)][field]) for size in SIZES
                         if (family, size, algorithm) in cells and cells[(family, size, algorithm)][field]['n']]
                if found:
                    axis.plot([size for size, _ in found], [value['median'] for _, value in found],
                              marker='o', color=color, label=algorithm)
                    axis.plot([size for size, _ in found], [value['p95_nearest_rank'] for _, value in found],
                              linestyle=':', color=color)
            axis.set_title(family)
            axis.set_yscale('log')
            axis.set_xticks(SIZES)
            axis.grid(alpha=0.2)
        axes[0, 0].legend()
        fig.suptitle(title+'\nSolid: median; dotted: nearest-rank p95. Missing/terminated API calls excluded; see outcome chart.')
        fig.supxlabel('Synthetic total ECU count')
        fig.tight_layout(rect=(0, 0.03, 1, 0.91))
        for suffix in ('png', 'svg'):
            fig.savefig(output / f'{filename}.{suffix}', dpi=160)
        plt.close(fig)
    fig, axis = plt.subplots(figsize=(10, 5))
    statuses = ('feasible', 'infeasible', 'unknown', 'WATCHDOG_TIMEOUT', 'MEMORY_LIMIT', 'WORKER_ERROR', 'WORKER_CRASH', 'NOT_RUN')
    bottoms = [0]*len(SIZES)
    for status in statuses:
        counts = [sum(row['statuses'].get(status, 0) for row in summary['cells']
                      if row['size'] == size and row['algorithm'] == 'z3') for size in SIZES]
        if sum(counts):
            axis.bar([str(size) for size in SIZES], counts, bottom=bottoms, label=status)
            bottoms = [a+b for a, b in zip(bottoms, counts)]
    axis.set(xlabel='Synthetic total ECU count', ylabel='All scheduled measured Z3 trials',
             title='Outcome distribution: timeouts/unknowns are retained, not scored as infeasible')
    axis.legend(loc='upper left', bbox_to_anchor=(1, 1))
    fig.tight_layout()
    for suffix in ('png', 'svg'):
        fig.savefig(output / f'outcomes.{suffix}', dpi=160)
    plt.close(fig)
    fig, axes = plt.subplots(2, 5, figsize=(16, 6), sharex=True)
    for family, axis in zip(FAMILIES, axes.flat):
        pairs = [row for row in summary['pairs'] if row['family'] == family and row['comparable']]
        points = [(size, [row['makespan_ratio_sequential_over_z3'] for row in pairs if row['size'] == size]) for size in SIZES]
        points = [(size, values) for size, values in points if values]
        if points:
            axis.plot([size for size, _ in points], [statistics.median(values) for _, values in points], marker='o')
        axis.axhline(1, color='gray', linewidth=0.6)
        axis.set_title(family)
        axis.set_xticks(SIZES)
        axis.grid(alpha=0.2)
    fig.suptitle('Sequential/Z3 makespan ratio: valid paired plans only; unproved optimality retained in JSON\nSequential heuristic and parallel makespan minimization are different objectives.')
    fig.supxlabel('Synthetic total ECU count')
    fig.tight_layout(rect=(0, 0.03, 1, 0.91))
    for suffix in ('png', 'svg'):
        fig.savefig(output / f'makespan_ratios.{suffix}', dpi=160)
    plt.close(fig)


def main() -> int:
    """Verify raw measurements before producing JSON, CSV and static charts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--no-plots', action='store_true')
    args = parser.parse_args()
    summary = summarize(args.input.resolve())
    args.output.mkdir(exist_ok=False, parents=True)
    write_json(args.output / 'summary.json', summary)
    with (args.output / 'cells.csv').open('w', encoding='utf-8', newline='') as stream:
        fields = ('family', 'size', 'algorithm', 'scheduled', 'statuses', 'median_api_ms', 'p95_api_ms',
                  'median_api_peak_mib', 'feasible_optimal', 'feasible_unproven', 'subset_minimal_cores')
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for cell in summary['cells']:
            writer.writerow({key: cell[key] for key in fields if key in cell} | {
                'statuses': json.dumps(cell['statuses'], sort_keys=True), 'median_api_ms': cell['api_ms']['median'],
                'p95_api_ms': cell['api_ms']['p95_nearest_rank'],
                'median_api_peak_mib': cell['api_peak_working_set_mib']['median']})
    if not args.no_plots:
        plots(summary, args.output)
    write_json(args.output / 'SHA256SUMS.json', {path.name: file_hash(path) for path in args.output.iterdir() if path.is_file()})
    logging.info('Summary: Z3=%s baseline=%s', summary['z3_statuses'], summary['baseline_statuses'])
    return 0


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
