"""E3: how far monolithic TLC scales, and a pair abstraction that does not depend on N.

Four parts, cheapest first:
  pair        S1-S4 on the two abstract pair models, for each design
  refinement  TLC checks the full model refines the pair model on small instances
  agreement   pair verdicts against monolithic verdicts where both finish
  monolithic  safety and liveness on generated campaigns, up to the time limit
"""
import csv
import hashlib
import json
import shutil
from dataclasses import asdict
from itertools import combinations
from pathlib import Path
from typing import Any
from ota_verifier.formal.campaign_gen import edges_of, ecu_names, generate, is_acyclic, tla_edges, tla_set
from ota_verifier.formal.tlc_run import HEAP, TlcResult, run_tlc

SIZES = (5, 6, 7, 8, 9, 10, 20, 50)
LIVENESS_SIZES = (3, 4, 5, 6)
SEEDS = (1, 2, 3)
FAULT_BUDGET = 1
LIMIT_SECONDS = 300
LONG_LIMIT_SECONDS = 1200  # Sizes near the practical boundary get longer, so the boundary is measured.
LONG_LIMIT_MAX_SIZE = 10
SMALL_LIMIT_SECONDS = 120
SMALL_SIZES = (3, 4, 5)
AGREEMENT_FAULTS = 2
DESIGNS = ('none', 'LocalRollback', 'EarlyErase', 'SkipVerify')
SAFETY = {'S1': 'CompatAlways', 'S2': 'WayBackKept', 'S3': 'AllOrNothing', 'S4': 'OnlyVerifiedRuns'}
SHAPES = {'none': '{}', 'edge': '{<<"a", "b">>}'}
SCALING_FIELDS = ('method', 'properties', 'n', 'seed', 'edges', 'graph_sha256', 'fault_budget', 'status', 'verdict',
                  'distinct_states', 'states_generated', 'queue_left', 'depth', 'wall_seconds', 'peak_rss_mb',
                  'limit_seconds', 'heap', 'workers', 'log')


def write_csv(path: Path, rows: list[dict[str, Any]], fields: tuple[str, ...] | None = None) -> None:
    """Write rows as CSV."""
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields or tuple(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def measured(result: TlcResult) -> dict[str, Any]:
    """The columns every TLC run reports."""
    return {'status': result.status, 'verdict': result.verdict, 'distinct_states': result.distinct,
            'states_generated': result.generated, 'queue_left': result.queue, 'depth': result.depth,
            'wall_seconds': f'{result.wall_seconds:.2f}',
            'peak_rss_mb': '' if result.peak_rss_mb is None else f'{result.peak_rss_mb:.0f}'}


class Workspace:
    """Generated TLA+ modules, configs and logs for one run."""

    def __init__(self, run_dir: Path, jar: Path, root: Path) -> None:
        self.jar = jar
        self.tla = run_dir / 'tla'
        self.logs = run_dir / 'logs'
        self.tla.mkdir()
        self.logs.mkdir()
        for name in ('OTACampaign.tla', 'OTAPair.tla'):
            shutil.copy(root / 'specs' / 'tla' / name, self.tla / name)

    def check(self, module: str, body: str, label: str, config: str, limit: float) -> TlcResult:
        """Write a module and config, then run TLC on them."""
        (self.tla / f'{module}.tla').write_text(f'---- MODULE {module} ----\n{body}\n====\n', encoding='utf-8')
        cfg = self.tla / f'{label}.cfg'
        cfg.write_text(config, encoding='utf-8')
        return run_tlc(self.jar, f'{module}.tla', self.tla, cfg, self.logs / f'{label}.log', limit)


def graph_body(size: int, seed: int) -> tuple[str, tuple[tuple[str, str], ...]]:
    """TLA+ definitions of one generated campaign."""
    edges = edges_of(generate(size, seed))
    if not is_acyclic(ecu_names(size), edges):
        raise ValueError(f'Generated graph n={size} seed={seed} has a cycle')
    return (f'EXTENDS OTACampaign\nGenECUs == {tla_set(ecu_names(size))}\nGenDeps == {tla_edges(edges)}', edges)


def full_config(design: str, faults: int, checks: str, extra: str = '') -> str:
    """Config for the full model."""
    return (f'SPECIFICATION Spec\nCONSTANTS\n  ECUs <- GenECUs\n  Deps <- GenDeps\n{extra}'
            f'  MaxFaults = {faults}\n  Flaw = "{design}"\n{checks}\nCHECK_DEADLOCK FALSE\n')


def invariants(*names: str) -> str:
    """Config lines checking TypeOK and the given invariants."""
    return '\n'.join(f'INVARIANT {name}' for name in ('TypeOK', *names))


def pair_config(design: str, name: str) -> str:
    """Config for one property of a pair model."""
    return ('SPECIFICATION Safe\nCONSTANTS\n  ECUs <- PairECUs\n  Deps <- PairDeps\n'
            f'  Flaw = "{design}"\n  EnvEnabled = TRUE\nINVARIANT {name}\nCHECK_DEADLOCK FALSE\n')


def pair_body(shape: str) -> str:
    """TLA+ definitions of a pair model."""
    return f'EXTENDS OTAPair\nPairECUs == {{"a", "b"}}\nPairDeps == {SHAPES[shape]}'


def run_pair(space: Workspace) -> tuple[list[dict[str, Any]], dict[tuple[str, str, str], str]]:
    """Check each safety property of each design on both pair shapes."""
    rows, verdicts = [], {}
    for design in DESIGNS:
        for shape in SHAPES:
            for prop, name in SAFETY.items():
                label = f'pair__{design}__{shape}__{prop}'
                result = space.check(f'Pair_{shape}', pair_body(shape), label, pair_config(design, name), SMALL_LIMIT_SECONDS)
                verdicts[design, shape, prop] = result.verdict
                rows.append({'design': design, 'shape': shape, 'property': prop, **measured(result)})
    return rows, verdicts


def refine_body(size: int, seed: int) -> tuple[str, int]:
    """A module with one refinement property per ECU pair."""
    body, edges = graph_body(size, seed)
    lines = [body, 'CONSTANT EnvOn']
    pairs = list(combinations(ecu_names(size), 2))
    for index, pair in enumerate(pairs):
        inner = tuple(edge for edge in edges if set(edge) <= set(pair))
        names = tla_set(pair)
        lines += [f'P{index} == INSTANCE OTAPair WITH ECUs <- {names}, Deps <- {tla_edges(inner)}, Flaw <- Flaw,',
                  '    EnvEnabled <- EnvOn,',
                  *(f'    {variable} <- [e \\in {names} |-> {variable}[e]],' for variable in ('active', 'inactive', 'stage', 'corrupt')),
                  f'    campaign <- campaign, culprit <- culprit \\cap {names}',
                  f'R{index} == P{index}!Safe']
    return '\n'.join(lines), len(pairs)


def run_refinement(space: Workspace) -> list[dict[str, Any]]:
    """Have TLC check every full-model step maps to a pair-model step or a stutter."""
    rows = []
    cases = [(size, seed, design, True) for size in SMALL_SIZES for seed in SEEDS for design in DESIGNS]
    cases.append((3, 1, 'none', False))  # Negative control: without EnvFail the check must fail.
    for size, seed, design, environment in cases:
        body, pairs = refine_body(size, seed)
        checks = '\n'.join(f'PROPERTY R{index}' for index in range(pairs))
        config = full_config(design, FAULT_BUDGET, checks, f'  EnvOn = {str(environment).upper()}\n')
        label = f'refine__n{size}_s{seed}__{design}__env{int(environment)}'
        result = space.check(f'Refine_n{size}_s{seed}', body, label, config, LIMIT_SECONDS)
        rows.append({'n': size, 'seed': seed, 'design': design, 'env_fail_enabled': environment, 'pairs': pairs,
                     **measured(result)})
    return rows


def applicable_shapes(size: int, edges: tuple[tuple[str, str], ...]) -> set[str]:
    """Which pair shapes occur in a graph."""
    joined = {frozenset(edge) for edge in edges}
    shapes = {'edge'} if joined else set()
    if len(joined) < size * (size - 1) // 2:
        shapes.add('none')
    return shapes


def run_agreement(space: Workspace, verdicts: dict[tuple[str, str, str], str]) -> list[dict[str, Any]]:
    """Compare pair predictions with monolithic verdicts."""
    rows = []
    for size in SMALL_SIZES:
        for seed in SEEDS:
            body, edges = graph_body(size, seed)
            for design in DESIGNS:
                for prop, name in SAFETY.items():
                    predicted = 'violated' if any(verdicts[design, shape, prop] == 'violated'
                                                  for shape in applicable_shapes(size, edges)) else 'holds'
                    label = f'agree__n{size}_s{seed}__{design}__{prop}'
                    config = full_config(design, AGREEMENT_FAULTS, invariants(name))
                    result = space.check(f'Gen_n{size}_s{seed}', body, label, config, SMALL_LIMIT_SECONDS)
                    rows.append({'n': size, 'seed': seed, 'design': design, 'property': prop, 'pair_prediction': predicted,
                                 'monolithic': result.verdict, 'status': result.status})
    return rows


def scaling_row(method: str, properties: str, size: Any, seed: Any, edges: Any, digest: str, faults: Any,
                result: TlcResult, limit: int, label: str) -> dict[str, Any]:
    """One row of scaling.csv."""
    return {'method': method, 'properties': properties, 'n': size, 'seed': seed, 'edges': edges, 'graph_sha256': digest,
            'fault_budget': faults, **measured(result), 'limit_seconds': limit, 'heap': HEAP, 'workers': 1,
            'log': f'logs/{label}.log'}


def limit_for(properties: str, size: int) -> int:
    """Wall-clock limit for one monolithic run."""
    return LONG_LIMIT_SECONDS if properties == 'S1-S4' and size <= LONG_LIMIT_MAX_SIZE else LIMIT_SECONDS


def run_monolithic(space: Workspace, run_dir: Path) -> list[dict[str, Any]]:
    """Check the correct design on every generated campaign, saving each campaign."""
    folder = run_dir / 'campaigns'
    folder.mkdir()
    rows = []
    series = [('S1-S4', size, invariants(*SAFETY.values())) for size in SIZES]
    series += [('L1', size, 'PROPERTY CampaignFinishes') for size in LIVENESS_SIZES]
    for properties, size, checks in series:
        for seed in SEEDS:
            body, edges = graph_body(size, seed)
            text = generate(size, seed).model_dump_json(indent=2)
            (folder / f'n{size}_s{seed}.json').write_text(text + '\n', encoding='utf-8')
            digest = hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]
            label = f'mono__{properties}__n{size}_s{seed}'
            limit = limit_for(properties, size)
            result = space.check(f'Gen_n{size}_s{seed}', body, label, full_config('none', FAULT_BUDGET, checks), limit)
            rows.append(scaling_row('monolithic', properties, size, seed, len(edges), digest, FAULT_BUDGET, result,
                                    limit, label))
            (run_dir / 'progress.json').write_text(json.dumps(rows[-1]) + '\n', encoding='utf-8')
    return rows


def run_pair_cost(space: Workspace) -> list[dict[str, Any]]:
    """Cost of the correct design's pair models, with all properties in one run."""
    rows = []
    for shape in SHAPES:
        label = f'paircost__{shape}'
        config = pair_config('none', 'CompatAlways').replace(
            'INVARIANT CompatAlways', '\n'.join(f'INVARIANT {name}' for name in SAFETY.values()))
        result = space.check(f'Pair_{shape}', pair_body(shape), label, config, SMALL_LIMIT_SECONDS)
        rows.append(scaling_row('pair', 'S1-S4', 'any', shape, '', '', 'any', result, SMALL_LIMIT_SECONDS, label))
    return rows


def problems(pair: list[dict[str, Any]], refinement: list[dict[str, Any]], agreement: list[dict[str, Any]],
             scaling: list[dict[str, Any]]) -> list[str]:
    """List anything that must not pass silently. A monolithic DNF is a result, not a problem."""
    found = []
    for row in pair:
        if row['status'] != 'completed':
            found.append(f'pair {row["design"]} {row["shape"]} {row["property"]}: {row["status"]}')
        if row['design'] == 'none' and row['verdict'] != 'holds':
            found.append(f'correct pair model violates {row["property"]} on shape {row["shape"]}')
    for row in refinement:
        expected = 'holds' if row['env_fail_enabled'] else 'violated'
        if row['verdict'] != expected:
            found.append(f'refinement n={row["n"]} s={row["seed"]} {row["design"]}: expected {expected}, got {row["verdict"]}')
    for row in agreement:
        if row['status'] != 'completed':
            found.append(f'agreement n={row["n"]} s={row["seed"]} {row["design"]} {row["property"]}: {row["status"]}')
        if row['pair_prediction'] == 'holds' and row['monolithic'] == 'violated':
            found.append(f'UNSOUND: n={row["n"]} s={row["seed"]} {row["design"]} {row["property"]}')
    for row in scaling:
        if row['status'] == 'error' or row['verdict'] == 'violated':
            found.append(f'scaling {row["method"]} {row["properties"]} n={row["n"]} s={row["seed"]}: {row["status"]} {row["verdict"]}')
    return found


def run(run_dir: Path, jar: Path, root: Path) -> list[str]:
    """Run all four parts; results land in the run folder and results/scaling.csv."""
    space = Workspace(run_dir, jar, root)
    pair, verdicts = run_pair(space)
    write_csv(run_dir / 'pair_checks.csv', pair)
    refinement = run_refinement(space)
    write_csv(run_dir / 'refinement.csv', refinement)
    agreement = run_agreement(space, verdicts)
    write_csv(run_dir / 'agreement.csv', agreement)
    scaling = run_pair_cost(space) + run_monolithic(space, run_dir)
    write_csv(run_dir / 'scaling.csv', scaling, SCALING_FIELDS)
    shutil.copy(run_dir / 'scaling.csv', root / 'results' / 'scaling.csv')
    return problems(pair, refinement, agreement, scaling)
