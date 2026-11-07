"""One isolated planning/baseline measurement; no model-service imports are allowed."""
from __future__ import annotations

import argparse
import gzip
import importlib.abc
import json
import logging
from pathlib import Path
import sys
from time import perf_counter_ns
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'eval')]


class NoLLM(importlib.abc.MetaPathFinder):
    """Reject any attempt to introduce LLM code into a deterministic trial."""
    def find_spec(self, fullname: str, path: Any = None, target: Any = None) -> None:
        if fullname == 'ota_verifier.llm' or fullname.startswith('ota_verifier.llm.'):
            raise ImportError('LLM imports forbidden in scalability worker')
        return None


from ota_verifier.models import Campaign, FeasibleResult, PlanningOptions
from ota_verifier.scheduling import validate_plan
from scalability.memory import memory_observation
from scalability.workloads import baseline, canonical, digest


def write_json(path: Path, value: Any) -> None:
    """Atomically publish complete UTF-8 JSON; retain partial-stage evidence separately."""
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(canonical(value), encoding='utf-8', newline='\n')
    temporary.replace(path)


def execute(input_path: Path, output: Path, algorithm: str) -> dict[str, Any]:
    """Measure the public planner or sequential baseline on identical frozen input."""
    raw = json.loads(input_path.read_text(encoding='utf-8'))
    started = perf_counter_ns()
    campaign = Campaign.model_validate_json(canonical(raw['campaign']))
    options = PlanningOptions.model_validate_json(canonical(raw['options']))
    schema_ms = (perf_counter_ns() - started) / 1e6
    if algorithm == 'z3':
        from ota_verifier.planner import plan_campaign
        call = lambda: plan_campaign(campaign, options)
    else:
        call = lambda: baseline(campaign, options)
    before = memory_observation()
    write_json(output.with_suffix('.progress.json'), {'phase': 'planning', 'schema_ms': schema_ms})
    started = perf_counter_ns()
    result = call()
    planning_ms = (perf_counter_ns() - started) / 1e6
    memory_after_api = memory_observation()
    plan = (result.plan if isinstance(result, FeasibleResult) else result.get('plan') if isinstance(result, dict) else None)
    status = result.status if not isinstance(result, dict) else result['status']
    record: dict[str, Any] = {'status': status, 'algorithm': algorithm, 'schema_ms': schema_ms,
        'planner_api_ms': planning_ms, 'memory_before_api': before, 'memory_after_api': memory_after_api,
        'makespan_ms': plan.makespan_ms if plan else None, 'optimal': plan.optimal if plan else None,
        'external_validation_ms': None, 'violations': [], 'serialization_ms': None,
        'note': getattr(result, 'note', None) if not isinstance(result, dict) else result['reason'],
        'reason_unknown': getattr(result, 'reason', None),
        'conflict': result.conflict.model_dump(mode='json') if hasattr(result, 'conflict') else None,
        'llm_imports_forbidden': any(isinstance(finder, NoLLM) for finder in sys.meta_path)}
    write_json(output.with_suffix('.progress.json'), record | {'phase': 'external_validation'})
    if plan is not None:
        started = perf_counter_ns()
        findings = validate_plan(campaign, plan)
        record['external_validation_ms'] = (perf_counter_ns() - started) / 1e6
        record['violations'] = [item.model_dump(mode='json') for item in findings]
        if findings:
            raise RuntimeError('Measured planner/baseline returned an invalid plan')
    started = perf_counter_ns()
    payload = (result.model_dump(mode='json') if not isinstance(result, dict) else
               {'status': status, 'reason': result['reason'], 'plan': plan.model_dump(mode='json') if plan else None})
    compressed = output.with_suffix('.result.json.gz')
    with gzip.GzipFile(filename=str(compressed), mode='wb', mtime=0) as stream:
        stream.write(canonical(payload).encode('utf-8'))
    record['serialization_ms'] = (perf_counter_ns() - started) / 1e6
    record['result_file'] = compressed.name
    record['result_semantic_sha256'] = digest(payload)
    record['memory_worker_lifetime'] = memory_observation()
    write_json(output, record)
    return record


def main() -> int:
    """Run one explicitly selected deterministic algorithm and preserve failures."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--algorithm', choices=('z3', 'sequential'), required=True)
    args = parser.parse_args()
    sys.meta_path.insert(0, NoLLM())
    try:
        execute(args.input, args.output, args.algorithm)
        return 0
    except Exception as error:
        logging.exception('Scalability worker failed')
        write_json(args.output, {'status': 'WORKER_ERROR', 'error': f'{type(error).__name__}: {error}'})
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
