"""Plot results/scaling.csv as results/scaling.png and results/scaling.svg.

Usage: python experiments/plot_scaling.py [path/to/scaling.csv]
"""
import csv
import sys
from pathlib import Path
from statistics import median
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FixedLocator, NullLocator, ScalarFormatter

ROOT = Path(__file__).resolve().parent.parent
SURFACE, INK, MUTED, GRID = '#fcfcfb', '#0b0b0b', '#52514e', '#e4e3df'
MONOLITHIC, PAIR = '#2a78d6', '#eb6834'
PANELS = (('distinct_states', 'Distinct states'), ('wall_seconds', 'Wall-clock time (s)'),
          ('peak_rss_mb', 'Peak memory (MB)'))


def load(path: Path) -> list[dict[str, str]]:
    """Read the rows for the safety series."""
    with path.open(encoding='utf-8', newline='') as handle:
        return [row for row in csv.DictReader(handle) if row['properties'] == 'S1-S4']


def split(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    """Separate finished monolithic runs, stopped monolithic runs, and pair runs."""
    monolithic = [row for row in rows if row['method'] == 'monolithic']
    return ([row for row in monolithic if row['status'] == 'completed'],
            [row for row in monolithic if row['status'].startswith('DNF')],
            [row for row in rows if row['method'] == 'pair'])


def points(rows: list[dict[str, str]], field: str) -> tuple[list[int], list[float]]:
    """Return usable (n, value) pairs."""
    usable = [row for row in rows if row[field] not in ('', None)]
    return [int(row['n']) for row in usable], [float(row[field]) for row in usable]


def medians(xs: list[int], ys: list[float]) -> tuple[list[int], list[float]]:
    """Median value at each size."""
    sizes = sorted(set(xs))
    return sizes, [median(y for x, y in zip(xs, ys) if x == size) for size in sizes]


def panel(axis: plt.Axes, field: str, title: str, done: list[dict[str, str]], stopped: list[dict[str, str]],
          pair: list[dict[str, str]], sizes: list[int]) -> None:
    """Draw one measure."""
    xs, ys = points(done, field)
    axis.plot(*medians(xs, ys), color=MONOLITHIC, linewidth=2, zorder=2)
    axis.scatter(xs, ys, s=30, color=MONOLITHIC, edgecolors=SURFACE, linewidths=1, zorder=3)
    xs, ys = points(stopped, field)
    axis.scatter(xs, ys, s=38, facecolors=SURFACE, edgecolors=MONOLITHIC, linewidths=1.5, zorder=3)
    values = [float(row[field]) for row in pair if row[field]]  # Pair rows have n = 'any'.
    if values:
        axis.axhline(max(values), color=PAIR, linewidth=2, linestyle=(0, (6, 3)), zorder=1)
    axis.set_title(title, loc='left', fontsize=11, color=INK, fontweight='semibold')
    axis.set_xscale('log')
    axis.set_yscale('log')
    axis.set_xlim(min(sizes) * 0.9, max(sizes) * 1.1)  # Same range everywhere, even with no stopped points.
    axis.xaxis.set_major_locator(FixedLocator(sizes))
    axis.xaxis.set_minor_locator(NullLocator())
    axis.xaxis.set_major_formatter(ScalarFormatter())
    axis.set_xlabel('ECUs (N)', color=MUTED, fontsize=9)
    axis.tick_params(which='both', colors=MUTED, labelsize=8, length=0)
    axis.grid(True, axis='y', color=GRID, linewidth=0.8)
    axis.set_axisbelow(True)
    axis.set_facecolor(SURFACE)
    for side in ('top', 'right', 'left'):
        axis.spines[side].set_visible(False)
    axis.spines['bottom'].set_color(GRID)


def main() -> None:
    """Draw the three panels and save both formats next to the CSV."""
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'results' / 'scaling.csv'
    done, stopped, pair = split(load(source))
    sizes = sorted({int(row['n']) for row in (*done, *stopped) if row['n'].isdigit()} & {5, 7, 10, 20, 50})
    figure, axes = plt.subplots(1, 3, figsize=(11, 4.2), facecolor=SURFACE)
    for axis, (field, title) in zip(axes, PANELS):
        panel(axis, field, title, done, stopped, pair, sizes)
    legend = [
        Line2D([], [], color=MONOLITHIC, marker='o', markersize=6, linewidth=2, label='Monolithic TLC, finished (line: median of finished graphs only)'),
        Line2D([], [], color='none', marker='o', markersize=7, markerfacecolor=SURFACE, markeredgecolor=MONOLITHIC,
               markeredgewidth=1.5, label='Monolithic TLC, stopped at time limit (partial, not a total)'),
        Line2D([], [], color=PAIR, linewidth=2, linestyle=(0, (6, 3)), label='Pair abstraction, safety only (larger of 2 shapes; same for any N)'),
    ]
    figure.legend(handles=legend, loc='lower center', ncol=2, frameon=False, fontsize=8.5, labelcolor=INK)
    figure.tight_layout(rect=(0, 0.12, 1, 1))
    for suffix in ('png', 'svg'):
        figure.savefig(source.with_suffix(f'.{suffix}'), dpi=200, facecolor=SURFACE)


if __name__ == '__main__':
    main()
