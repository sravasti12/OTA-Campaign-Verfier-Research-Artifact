"""Summarise results/scaling.csv by size into results/processed/scaling_summary.csv.

Medians cover finished runs only, so a size where some graphs stopped is biased low.
Usage: python experiments/summarize_scaling.py
"""
import csv
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent.parent
FIELDS = ('properties', 'n', 'runs', 'finished', 'stopped', 'limit_seconds', 'edges', 'min_states', 'median_states',
          'max_states', 'median_depth', 'median_wall_seconds', 'max_wall_seconds', 'max_peak_rss_mb',
          'median_states_vs_largest_pair')


def summarise(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    """One row per property set and size."""
    pair = max(int(row['distinct_states']) for row in rows if row['method'] == 'pair')
    monolithic = [row for row in rows if row['method'] == 'monolithic']
    table = []
    for key in sorted({(row['properties'], int(row['n'])) for row in monolithic}, key=lambda item: (item[0] != 'S1-S4', item[1])):
        group = [row for row in monolithic if (row['properties'], int(row['n'])) == key]
        done = [row for row in group if row['status'] == 'completed']
        states = [int(row['distinct_states']) for row in done]
        wall = [float(row['wall_seconds']) for row in group]
        table.append({
            'properties': key[0], 'n': key[1], 'runs': len(group), 'finished': len(done), 'stopped': len(group) - len(done),
            'limit_seconds': group[0]['limit_seconds'], 'edges': ' '.join(row['edges'] for row in group),
            'min_states': min(states, default=''), 'median_states': median(states) if states else '',
            'max_states': max(states, default=''),
            'median_depth': median(int(row['depth']) for row in done) if done else '',
            'median_wall_seconds': round(median(float(row['wall_seconds']) for row in done), 2) if done else '',
            'max_wall_seconds': max(wall), 'max_peak_rss_mb': max(int(row['peak_rss_mb']) for row in group),
            'median_states_vs_largest_pair': round(median(states) / pair) if states else ''})
    return table


def main() -> None:
    with (ROOT / 'results' / 'scaling.csv').open(encoding='utf-8', newline='') as handle:
        table = summarise(list(csv.DictReader(handle)))
    with (ROOT / 'results' / 'processed' / 'scaling_summary.csv').open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(table)


if __name__ == '__main__':
    main()
