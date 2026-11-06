"""E0: check the 3-ECU campaign and its flawed variants with TLC.

Each property is checked alone, because TLC stops at the first violation and one
combined run would hide the rest. Every counterexample is re-checked in Python
without TLC, and expected verdicts are declared here before running.
"""
import csv
import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable
from ota_verifier.formal.tlc_trace import changed_ecus, parse_trace

SEED = 42
ECUS = ('gateway', 'brake', 'infotainment')
FAULT_BUDGETS = (0, 1, 2)
DESIGNS = ('none', 'LocalRollback', 'EarlyErase', 'SkipVerify')
PROPERTIES = {'S1': 'CompatAlways', 'S2': 'WayBackKept', 'S3': 'AllOrNothing', 'S4': 'OnlyVerifiedRuns',
              'L1': 'CampaignFinishes'}
SANITY = ('NeverCommits', 'NeverAborts', 'NeverRevertsAnything')
EXPECTED_VIOLATIONS = {'none': set(), 'LocalRollback': {'S1', 'S3'}, 'EarlyErase': {'S2', 'L1'},
                       'SkipVerify': {'S4'}}
FIELDS = ('design', 'property', 'name', 'fault_budget', 'verdict', 'expected_at_budget_2', 'exit_code',
          'states_generated', 'distinct_states', 'trace_states', 'trace_ending', 'trace_replay',
          'wall_seconds', 'log', 'trace')
ENDED = ('committed', 'aborted')


def s1(state: dict[str, Any]) -> bool:
    return state['active']['brake'] != 2 or state['active']['gateway'] == 2


def s2(state: dict[str, Any]) -> bool:
    return state['campaign'] == 'committed' or all(
        state['inactive'][ecu] == 1 for ecu in ECUS if state['active'][ecu] == 2)


def s3(state: dict[str, Any]) -> bool:
    return state['campaign'] not in ENDED or len(set(state['active'].values())) == 1


def s4(state: dict[str, Any]) -> bool:
    return not any(state['active'][ecu] == 2 and state['corrupt'][ecu] for ecu in ECUS)


CHECKS: dict[str, Callable[[dict[str, Any]], bool]] = {'S1': s1, 'S2': s2, 'S3': s3, 'S4': s4}


def replay(prop: str, trace: dict[str, Any]) -> bool:
    """Confirm a trace shows the violation, using only the Python definitions above."""
    states = [item['vars'] for item in trace['states']]
    if not states:
        return False
    if prop == 'L1':
        return trace['ending'] in ('stuttering', 'loop') and all(state['campaign'] not in ENDED for state in states)
    check = CHECKS[prop]
    return all(check(state) for state in states[:-1]) and not check(states[-1])


def config(design: str, budget: int, kind: str, name: str) -> str:
    """Render a TLC configuration checking exactly one property."""
    check = f'PROPERTY {name}' if kind == 'temporal' else f'INVARIANT TypeOK\nINVARIANT {name}'
    return ('SPECIFICATION Spec\nCONSTANTS\n  ECUs <- SmallECUs\n  Deps <- SmallDeps\n'
            f'  MaxFaults = {budget}\n  Flaw = "{design}"\n{check}\nCHECK_DEADLOCK FALSE\n')


def verdict(code: int, output: str, name: str) -> str:
    """Classify a TLC run; anything unrecognized is an error, never a pass."""
    if 'Invariant TypeOK is violated' in output:
        return 'error'
    if code == 0 and 'Model checking completed. No error has been found.' in output:
        return 'holds'
    if f'Invariant {name} is violated' in output or 'Temporal properties were violated' in output:
        return 'violated'
    return 'error'


def run_tlc(jar: Path, spec_dir: Path, run_dir: Path, label: str, text: str) -> tuple[int, str, float]:
    """Run TLC once, keeping its config and complete output."""
    for folder in ('cfg', 'logs'):
        (run_dir / folder).mkdir(exist_ok=True)
    cfg = run_dir / 'cfg' / f'{label}.cfg'
    cfg.write_text(text, encoding='utf-8')
    metadir = run_dir / 'tlc-states'
    command = ['java', '-XX:+UseParallelGC', '-cp', str(jar), 'tlc2.TLC', '-workers', '1', '-seed', str(SEED),
               '-fp', '0', '-metadir', str(metadir), '-config', str(cfg), 'SmallCampaign.tla']
    started = time.perf_counter()
    done = subprocess.run(command, cwd=spec_dir, text=True, encoding='utf-8', errors='replace',
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    elapsed = time.perf_counter() - started
    shutil.rmtree(metadir, ignore_errors=True)
    (run_dir / 'logs' / f'{label}.log').write_text(done.stdout, encoding='utf-8')
    return done.returncode, done.stdout, elapsed


def counts(output: str) -> tuple[int | None, int | None]:
    """Read TLC's final state counts."""
    found = re.findall(r'([\d,]+) states generated, ([\d,]+) distinct states found', output)
    return (int(found[-1][0].replace(',', '')), int(found[-1][1].replace(',', ''))) if found else (None, None)


def render(label: str, trace: dict[str, Any]) -> str:
    """Render a trace as a table a person can read."""
    lines = [f'# {label}', '', '| # | Step | ECU | gateway | brake | infotainment | Campaign | Faults |',
             '| --- | --- | --- | --- | --- | --- | --- | --- |']
    previous = None
    for number, item in enumerate(trace['states'], 1):
        state = item['vars']
        touched = ', '.join(changed_ecus(previous, state)) if previous else ''
        cells = [f'v{state["active"][ecu]} {state["stage"][ecu]}' + (' (corrupt)' if state['corrupt'][ecu] else '')
                 + f', spare v{state["inactive"][ecu]}' for ecu in ECUS]
        lines.append(f'| {number} | {item["action"]} | {touched} | {" | ".join(cells)} | {state["campaign"]} '
                     f'| {state["faults"]} |')
        previous = state
    if trace['ending'] == 'stuttering':
        lines += ['', 'The system then stays in the last state forever.']
    elif trace['ending'] == 'loop':
        lines += ['', f'The system then loops back to state {trace["loop_to"]} forever.']
    return '\n'.join(lines) + '\n'


def save_trace(run_dir: Path, label: str, output: str, prop: str) -> tuple[dict[str, Any], bool]:
    """Write the JSON and readable trace, and replay it."""
    folder = run_dir / 'traces'
    folder.mkdir(exist_ok=True)
    trace = parse_trace(output)
    confirmed = prop not in PROPERTIES or replay(prop, trace)
    trace['replay_confirmed'] = confirmed
    (folder / f'{label}.json').write_text(json.dumps(trace, indent=2) + '\n', encoding='utf-8')
    (folder / f'{label}.md').write_text(render(label, trace), encoding='utf-8')
    return trace, confirmed


def check_one(jar: Path, spec_dir: Path, run_dir: Path, design: str, budget: int, prop: str, name: str) -> dict[str, Any]:
    """Check one property of one design at one fault budget."""
    label = f'{design}__{prop}__F{budget}'
    kind = 'temporal' if prop == 'L1' else 'invariant'
    code, output, elapsed = run_tlc(jar, spec_dir, run_dir, label, config(design, budget, kind, name))
    result = verdict(code, output, name)
    generated, distinct = counts(output)
    row: dict[str, Any] = {
        'design': design, 'property': prop, 'name': name, 'fault_budget': budget, 'verdict': result,
        'expected_at_budget_2': 'violated' if prop in EXPECTED_VIOLATIONS[design] else 'holds',
        'exit_code': code, 'states_generated': generated, 'distinct_states': distinct, 'trace_states': '',
        'trace_ending': '', 'trace_replay': '', 'wall_seconds': f'{elapsed:.2f}', 'log': f'logs/{label}.log', 'trace': ''}
    if result == 'violated':
        trace, confirmed = save_trace(run_dir, label, output, prop)
        row.update(trace_states=len(trace['states']), trace_ending=trace['ending'], trace_replay=confirmed,
                   trace=f'traces/{label}.json')
    return row


def problems(rows: list[dict[str, Any]]) -> list[str]:
    """List anything that must not pass silently."""
    found = []
    for row in rows:
        label = f'{row["design"]} {row["name"]} F={row["fault_budget"]}'
        if row['verdict'] == 'error':
            found.append(f'{label}: TLC error')
        if row['verdict'] == 'violated' and row['trace_replay'] is False:
            found.append(f'{label}: trace failed the independent replay')
        if row['fault_budget'] == max(FAULT_BUDGETS) and row['verdict'] != row['expected_at_budget_2']:
            found.append(f'{label}: expected {row["expected_at_budget_2"]}, got {row["verdict"]}')
    return found


def run(run_dir: Path, jar: Path, root: Path) -> list[str]:
    """Run the full matrix and return any problems."""
    spec_dir = root / 'specs' / 'tla'
    rows = [check_one(jar, spec_dir, run_dir, design, budget, prop, name)
            for design in DESIGNS for budget in FAULT_BUDGETS for prop, name in PROPERTIES.items()]
    rows += [sanity(jar, spec_dir, run_dir, name) for name in SANITY]
    with (run_dir / 'results.csv').open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return problems(rows)


def sanity(jar: Path, spec_dir: Path, run_dir: Path, name: str) -> dict[str, Any]:
    """A reachability check on the correct design: this invariant must be violated."""
    row = check_one(jar, spec_dir, run_dir, 'none', max(FAULT_BUDGETS), name, name)
    row.update(property='sanity', expected_at_budget_2='violated')
    return row
