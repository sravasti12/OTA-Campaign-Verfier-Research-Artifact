"""E5 stage 1: record what the model predicts for every fault script, before any SIL run."""
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any
from ota_verifier.formal.campaign_gen import tla_edges, tla_set
from ota_verifier.formal.tlc_run import run_tlc
from ota_verifier.formal.tlc_trace import extract_results

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
common = importlib.import_module('e5_common')
MAX_FAULTS = 10
LIMIT_SECONDS = 600
ENDED = ('committed', 'aborted')


def tla_steps(steps: list[tuple[str, str]]) -> str:
    return '<<' + ', '.join(f'<<"{action}", "{ecu}">>' for action, ecu in steps) + '>>'


def tla_script(identifier: int, script: list[dict]) -> str:
    faults = ', '.join(f'[tick |-> {fault["tick"]}, kind |-> "{fault["kind"]}", ecu |-> "{fault["ecu"]}"]'
                       for fault in common.model_faults(script))
    return f'[id |-> {identifier}, faults |-> {{{faults}}}]'


def module(name: str, campaign: dict, policy: str, scripts: list[list[dict]]) -> str:
    edges = tuple(tuple(edge) for edge in campaign['edges'])
    body = ',\n  '.join(tla_script(index, script) for index, script in enumerate(scripts))
    return (f'---- MODULE {name} ----\nEXTENDS OTAScripted\nGenECUs == {tla_set(tuple(campaign["ecus"]))}\n'
            f'GenDeps == {tla_edges(edges)}\nGenPriority == {tla_steps(common.priority(campaign["ecus"], policy))}\n'
            f'GenScripts == {{\n  {body}\n}}\n====\n')


def config(design: str) -> str:
    return ('SPECIFICATION SSpec\nCONSTANTS\n  ECUs <- GenECUs\n  Deps <- GenDeps\n  Priority <- GenPriority\n'
            f'  Scripts <- GenScripts\n  MaxFaults = {MAX_FAULTS}\n  Flaw = "{design}"\nINVARIANT Report\nCHECK_DEADLOCK FALSE\n')


def predict(jar: Path, tla: Path, logs: Path, name: str, campaign: dict, design: str, policy: str) -> tuple[list[dict[str, Any]], str | None]:
    """Run TLC once for every script of one campaign, design and schedule."""
    scripts = common.fault_scripts(campaign['ecus'], policy)
    label = f'P_{name}_{design}_{policy}'
    (tla / f'{label}.tla').write_text(module(label, campaign, policy, scripts), encoding='utf-8')
    (tla / f'{label}.cfg').write_text(config(design), encoding='utf-8')
    log = logs / f'{label}.log'
    result = run_tlc(jar, f'{label}.tla', tla, tla / f'{label}.cfg', log, LIMIT_SECONDS)
    found = {row[1]: row for row in extract_results(log.read_text(encoding='utf-8', errors='replace'))}
    problem = None
    if result.verdict != 'holds' or sorted(found) != list(range(len(scripts))):
        problem = f'{label}: {result.status} {result.verdict}, {len(found)} of {len(scripts)} paths'
    rows = []
    for index, script in enumerate(scripts):
        if index not in found:
            continue
        _, _, seen, status, active, log_entries = found[index]
        violated = sorted({*seen, *([] if status in ENDED else ['L1'])})
        rows.append({'campaign': name, 'design': design, 'policy': policy, 'script': index, 'faults': script,
                     'violated': violated, 'final': status, 'active': active, 'actions': log_entries})
    return rows, problem


def run(run_dir: Path, jar: Path, root: Path) -> list[str]:
    """Write results/predictions/e5/predictions.jsonl."""
    tla, logs = run_dir / 'tla', run_dir / 'logs'
    tla.mkdir()
    logs.mkdir()
    for name in ('OTACampaign.tla', 'OTAScripted.tla'):
        shutil.copy(root / 'specs' / 'tla' / name, tla / name)
    rows, problems = [], []
    for name, campaign in common.campaigns().items():
        for design in common.DESIGNS:
            for policy in common.POLICIES:
                found, problem = predict(jar, tla, logs, name, campaign, design, policy)
                rows += found
                if problem:
                    problems.append(problem)
    target = root / 'results' / 'predictions' / 'e5'
    target.mkdir(parents=True, exist_ok=True)
    text = ''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows)
    (target / 'predictions.jsonl').write_text(text, encoding='utf-8', newline='\n')
    (run_dir / 'predictions.jsonl').write_text(text, encoding='utf-8', newline='\n')
    return problems
