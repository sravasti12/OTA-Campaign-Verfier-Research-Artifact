"""Generate every number and table in the paper from the raw results.

Nothing in paper/generated/ is edited by hand. Run: python paper/make_paper_data.py
Each source run is named below; changing a run means changing it here, in one place.
"""
import csv
import sys
import json
from collections import Counter
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent.parent
E0 = ROOT / 'results/raw/e0_small_campaign/20261106T140103Z-fc95dee'
E3 = ROOT / 'results/raw/e3_scaling/20261106T141615Z-ce3eefb'
E5 = ROOT / 'results/raw/e5_sil/20261108T074756Z-e593539'
PREDICT = ROOT / 'results/raw/e5_predict/20261107T095332Z-19423e3'
OUT = ROOT / 'paper' / 'generated'
PROPS = ('S1', 'S2', 'S3', 'S4', 'L1')
DESIGNS = {'none': 'Correct', 'LocalRollback': 'LocalRollback', 'EarlyErase': 'EarlyErase', 'SkipVerify': 'SkipVerify'}


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding='utf-8', newline='') as handle:
        return list(csv.DictReader(handle))


def num(value: float) -> str:
    """Thousands separators in LaTeX, decimals kept as given."""
    if isinstance(value, int) or float(value).is_integer():
        return f'{int(value):,}'.replace(',', '{,}')
    return f'{value:,.2f}'.replace(',', '{,}')


def manifest(run: Path) -> dict:
    return json.loads((run / 'manifest.json').read_text(encoding='utf-8'))


def e0(macros: dict[str, str]) -> None:
    data = rows(E0 / 'results.csv')
    macros['EzeroChecks'] = num(len(data))
    for budget, name in ((0, 'Zero'), (1, 'One'), (2, 'Two')):
        states = {r['distinct_states'] for r in data if r['design'] == 'none' and r['fault_budget'] == str(budget) and r['property'] != 'sanity'}
        assert len(states) == 1
        macros[f'EzeroStates{name}'] = num(int(states.pop()))
    macros['EzeroAllExpected'] = 'yes' if all(r['verdict'] == r['expected_at_budget_2'] for r in data if r['fault_budget'] == '2') else 'NO'
    lines = []
    for design, label in DESIGNS.items():
        cells = []
        for prop in PROPS:
            hit = sorted(int(r['fault_budget']) for r in data if r['design'] == design and r['property'] == prop and r['verdict'] == 'violated')
            cells.append(f'\\textbf{{violated}} ({hit[0]})' if hit else 'holds')
        lines.append(f'{label} & ' + ' & '.join(cells) + ' \\\\')
    (OUT / 'e0_verdicts.tex').write_text('\n'.join(lines) + '\n\\bottomrule\n', encoding='utf-8')


def e3(macros: dict[str, str]) -> None:
    scaling = rows(E3 / 'scaling.csv')
    mono = [r for r in scaling if r['method'] == 'monolithic' and r['properties'] == 'S1-S4']
    pair = [r for r in scaling if r['method'] == 'pair']
    largest_pair = max(int(r['distinct_states']) for r in pair)
    # Generated tables end with their own rule: LaTeX cannot put \bottomrule right after \input.
    lines, finished_all = [], []
    for size in sorted({int(r['n']) for r in mono}):
        group = [r for r in mono if int(r['n']) == size]
        done = [r for r in group if r['status'] == 'completed']
        if len(done) == len(group):
            finished_all.append(size)
        states = [int(r['distinct_states']) for r in done]
        wall = [float(r['wall_seconds']) for r in done]
        lines.append(' & '.join([
            str(size), f'{len(done)} of {len(group)}', num(int(group[0]['limit_seconds'])),
            num(median(states)) + (r'$^\dagger$' if done and len(done) < len(group) else '') if states else '--',
            num(round(median(wall), 2)) if wall else '--',
            num(max(int(r['peak_rss_mb']) for r in group))]) + ' \\\\')
    (OUT / 'scaling_table.tex').write_text('\n'.join(lines) + '\n\\bottomrule\n', encoding='utf-8')
    first_partial = min(int(r['n']) for r in mono if r['status'] != 'completed')
    macros['ScaleAllFinishMax'] = str(max(finished_all))
    macros['ScaleFirstStop'] = str(first_partial)
    macros['ScaleFirstNone'] = str(min(n for n in {int(r['n']) for r in mono}
                                       if all(r['status'] != 'completed' for r in mono if int(r['n']) == n)))
    at = lambda n: [r for r in mono if int(r['n']) == n]
    macros['ScaleFinishedAtStop'] = str(sum(r['status'] == 'completed' for r in at(first_partial)))
    macros['ScaleSlowestAtMax'] = num(max(float(r['wall_seconds']) for r in at(max(finished_all))))
    macros['ScalePeakRss'] = num(max(int(r['peak_rss_mb']) for r in mono))
    macros['ScaleLongLimit'] = num(max(int(r['limit_seconds']) for r in mono))
    macros['ScaleShortLimit'] = num(min(int(r['limit_seconds']) for r in mono))
    macros['ScaleSeeds'] = str(len({r['seed'] for r in mono}))
    macros['ScaleFaultBudget'] = mono[0]['fault_budget']
    shapes = {r['seed']: r for r in pair}
    macros['PairStatesNone'] = num(int(shapes['none']['distinct_states']))
    macros['PairStatesEdge'] = num(int(shapes['edge']['distinct_states']))
    macros['PairSecondsNone'] = num(float(shapes['none']['wall_seconds']))
    macros['PairSecondsEdge'] = num(float(shapes['edge']['wall_seconds']))
    done_stop = [int(r['distinct_states']) for r in at(first_partial) if r['status'] == 'completed']
    macros['PairRatioAtStop'] = num(round(median(done_stop) / largest_pair))
    seven = [r for r in at(7)]
    sparse, dense = min(seven, key=lambda r: int(r['edges'])), max(seven, key=lambda r: int(r['edges']))
    macros['SevenSparseEdges'], macros['SevenSparseStates'] = sparse['edges'], num(int(sparse['distinct_states']))
    macros['SevenDenseEdges'], macros['SevenDenseStates'] = dense['edges'], num(int(dense['distinct_states']))
    live = [r for r in scaling if r['properties'] == 'L1']
    macros['LiveRuns'] = str(len(live))
    macros['LiveHold'] = str(sum(r['verdict'] == 'holds' for r in live))
    macros['LiveMin'], macros['LiveMax'] = str(min(int(r['n']) for r in live)), str(max(int(r['n']) for r in live))
    refinement = rows(E3 / 'refinement.csv')
    real = [r for r in refinement if r['env_fail_enabled'] == 'True']
    control = [r for r in refinement if r['env_fail_enabled'] != 'True']
    macros['RefineRuns'], macros['RefineHold'] = str(len(real)), str(sum(r['verdict'] == 'holds' for r in real))
    macros['ControlVerdict'] = control[0]['verdict']
    agreement = rows(E3 / 'agreement.csv')
    pairs = Counter((r['pair_prediction'], r['monolithic']) for r in agreement)
    macros['AgreeRuns'] = str(len(agreement))
    macros['AgreeHolds'] = str(pairs[('holds', 'holds')])
    macros['AgreeViolated'] = str(pairs[('violated', 'violated')])
    macros['AgreeUnsound'] = str(pairs[('holds', 'violated')])
    macros['AgreeSpurious'] = str(pairs[('violated', 'holds')])
    macros['AgreeSizes'] = ', '.join(sorted({r['n'] for r in agreement}))
    env = manifest(E3)['environment']
    macros['MachineCpus'] = str(env['logical_cpus'])
    macros['MachineJava'] = env['java'].split('"')[1]
    macros['MachinePython'] = env['python']


def e5(macros: dict[str, str]) -> None:
    if not (E5 / 'manifest.json').is_file():
        macros['SilAvailable'] = 'no'
        (OUT / 'confusion.tex').write_text('\\multicolumn{5}{c}{TODO: SIL run not complete} \\\\\n', encoding='utf-8')
        return
    info = manifest(E5)
    assert info['status'] == 'passed' and info['environment']['dirty_files'] == [], 'E5 run is not clean'
    macros['SilAvailable'] = 'yes'
    macros['SilCommit'] = info['environment']['commit'][:7]
    predict = manifest(PREDICT)['environment']['commit'][:7]
    macros['PredictCommit'] = predict
    comparison = rows(E5 / 'comparison.csv')
    macros['SilRuns'] = num(len(comparison))
    macros['SilSamePath'] = num(sum(r['same_path'] == 'True' for r in comparison))
    macros['SilSameEnd'] = num(sum(r['same_end'] == 'True' for r in comparison))
    macros['SilCampaigns'] = str(len({r['campaign'] for r in comparison}))
    table = rows(E5 / 'confusion.csv')
    get = lambda view, group: next(r for r in table if r['view'] == view and r['group'] == group)
    for view, prefix in (('all', 'SilAll'), ('distinct_all', 'SilDistinct')):
        row = get(view, 'all')
        for cell, name in (('match_violation', 'MatchViol'), ('match_safe', 'MatchSafe'), ('miss', 'Miss'), ('false_alarm', 'FalseAlarm')):
            macros[prefix + name] = num(int(row[cell]))
    lines = []
    for prop in PROPS:
        a, d = get('property', prop), get('distinct_property', prop)
        lines.append(f'{prop} & ' + ' & '.join(f"{num(int(a[c]))} ({num(int(d[c]))})"
                                               for c in ('match_violation', 'match_safe', 'miss', 'false_alarm')) + ' \\\\')
    (OUT / 'confusion.tex').write_text('\n'.join(lines) + '\n\\bottomrule\n', encoding='utf-8')


def table(name: str, lines: list[str]) -> None:
    """Write a table body. It ends with its own rule: LaTeX cannot put \\bottomrule right after \\input."""
    (OUT / f'{name}.tex').write_text('\n'.join(lines) + '\n\\bottomrule\n', encoding='utf-8')


def extra_tables(macros: dict[str, str]) -> None:
    """Supporting tables: counterexamples, pair models, agreement, liveness and SIL breakdowns."""
    data = rows(E0 / 'results.csv')
    lines = []
    for design, label in DESIGNS.items():
        for prop in PROPS:
            hits = sorted((r for r in data if r['design'] == design and r['property'] == prop and r['verdict'] == 'violated'),
                          key=lambda r: int(r['fault_budget']))
            if hits:
                r = hits[0]
                lines.append(f"{label} & {prop} & {r['fault_budget']} & {r['trace_states']} & {r['trace_ending']} & "
                             f"{num(int(r['distinct_states']))} & {'yes' if r['trace_replay'] == 'True' else 'NO'} \\\\")
    table('e0_counterexamples', lines)
    macros['ReplayAll'] = 'yes' if all(r['trace_replay'] == 'True' for r in data if r['verdict'] == 'violated') else 'NO'

    pair = rows(E3 / 'pair_checks.csv')
    lines = []
    for design, label in DESIGNS.items():
        for shape in ('none', 'edge'):
            group = [r for r in pair if r['design'] == design and r['shape'] == shape]
            holding = [r for r in group if r['verdict'] == 'holds']
            violated = ' '.join(r['property'] for r in group if r['verdict'] == 'violated') or '--'
            states = num(int(holding[0]['distinct_states'])) if holding else '--'
            lines.append(f"{label} & {shape} & {states} & {violated} \\\\")
    table('pair_checks', lines)

    agreement = rows(E3 / 'agreement.csv')
    lines = []
    for design, label in DESIGNS.items():
        c = Counter((r['pair_prediction'], r['monolithic']) for r in agreement if r['design'] == design)
        lines.append(f"{label} & {c[('holds', 'holds')]} & {c[('violated', 'violated')]} & {c[('holds', 'violated')]} & {c[('violated', 'holds')]} \\\\")
    table('agreement', lines)

    live = [r for r in rows(E3 / 'scaling.csv') if r['properties'] == 'L1']
    lines = []
    for size in sorted({int(r['n']) for r in live}):
        group = [r for r in live if int(r['n']) == size]
        lines.append(f"{size} & {' / '.join(r['edges'] for r in group)} & "
                     f"{' / '.join(num(int(r['distinct_states'])) for r in group)} & "
                     f"{num(max(float(r['wall_seconds']) for r in group))} & "
                     f"{sum(r['verdict'] == 'holds' for r in group)} of {len(group)} \\\\")
    table('liveness', lines)

    if macros.get('SilAvailable') != 'yes':
        return
    comparison = rows(E5 / 'comparison.csv')
    confusion = rows(E5 / 'confusion.csv')
    get = lambda view, group: next(r for r in confusion if r['view'] == view and r['group'] == group)
    # Sizes and edge counts come from the same generator the experiment used.
    sys.path[:0] = [str(ROOT / 'experiments'), str(ROOT / 'src')]
    import e5_common
    campaigns = e5_common.campaigns()
    sizes = {name: (len(c['ecus']), len(c['edges'])) for name, c in campaigns.items()}
    names = {name: 'Three-ECU' if name == 'small' else f"{len(c['ecus'])} ECUs, seed {name.rsplit('_s', 1)[1]}"
             for name, c in campaigns.items()}
    lines = []
    for campaign, (ecus, edges) in sizes.items():
        group = [r for r in comparison if r['campaign'] == campaign]
        paths = len({(r['design'], r['policy'], r['path_key']) for r in group})
        cells = get('campaign', campaign)
        lines.append(f"{names[campaign]} & {ecus} & {edges} & {num(len(group))} & {num(paths)} & "
                     f"{num(int(cells['match_violation']))} & {int(cells['miss']) + int(cells['false_alarm'])} \\\\")
    table('sil_campaigns', lines)
    macros['SilScriptsSmall'] = num(sum(r['campaign'] == 'small' for r in comparison) // 12)
    s1 = [r for r in comparison if r['S1'] == 'match_violation']
    macros['SilSOneViol'] = num(len(s1))
    macros['SilSOneDesigns'] = ', '.join(sorted({r['design'] for r in s1}))
    macros['SilSOnePolicies'] = ', '.join(sorted({{'late_confirm': 'late confirmation'}.get(r['policy'], r['policy']) for r in s1}))
    lines = []
    for view, labels in (('design', DESIGNS), ('policy', {'batch': 'Batch', 'rolling': 'Rolling', 'late_confirm': 'Late confirmation'})):
        for group, label in labels.items():
            c = get(view, group)
            lines.append(f"{label} & {num(int(c['match_violation']))} & {num(int(c['match_safe']))} & {c['miss']} & {c['false_alarm']} \\\\")
        if view == 'design':
            lines.append('\\midrule')
    table('sil_breakdown', lines)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    macros: dict[str, str] = {}
    e0(macros)
    e3(macros)
    e5(macros)
    extra_tables(macros)
    text = '% Generated by paper/make_paper_data.py. Do not edit.\n'
    text += '\\newif\\ifsil\n' + ('\\siltrue\n' if macros['SilAvailable'] == 'yes' else '\\silfalse\n')
    text += ''.join(f'\\newcommand{{\\{name}}}{{{value}}}\n' for name, value in sorted(macros.items()))
    (OUT / 'numbers.tex').write_text(text, encoding='utf-8')
    print(f'{len(macros)} numbers written to {OUT.relative_to(ROOT).as_posix()}')


if __name__ == '__main__':
    main()
