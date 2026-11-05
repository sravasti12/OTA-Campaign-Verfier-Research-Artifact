"""Document extraction CLI, with explicit fixture mode and gated planning."""
import argparse
import logging
from pathlib import Path
import sys
from pydantic import ValidationError
from .data.generate import SyntheticCase
from .evaluation import fixture_client
from .llm.client import ClientSettings, LLMClient, LLMError
from .llm.models import DocumentRequest
from .llm.pipeline import extract_and_verify, verified_campaign
from .models import PlanningOptions
from .planner import plan_campaign

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    """Emit extraction audit JSON; optional planning runs only after the gate passes.

    Exit 0 ready, 1 invalid input/configuration, 6 blocked extraction. With --plan,
    planner infeasibility/unknown use exits 2/3. Execution approval is out of scope.
    """
    parser = argparse.ArgumentParser(description='Extract and verify constraints from simulated OTA documents')
    parser.add_argument('input', type=Path)
    parser.add_argument('--fixture', action='store_true', help='Input is a labeled SyntheticCase; use canned responses, no LLM')
    parser.add_argument('--profile', choices=('reference', 'omission', 'reversed', 'false_approval', 'malformed'), default='reference')
    parser.add_argument('--plan', action='store_true', help='Plan only after extraction and verification pass')
    parser.add_argument('--max-parallel', type=int)
    parser.add_argument('--deadline-ms', type=int)
    parser.add_argument('--output', type=Path, help='Create a new audit record; existing files are never overwritten')
    args = parser.parse_args(argv)
    if not args.fixture and args.profile != 'reference':
        parser.error('Perturbation profiles require --fixture')
    try:
        raw = args.input.read_text(encoding='utf-8-sig')
        options = PlanningOptions(max_parallel=args.max_parallel, deadline_ms=args.deadline_ms)
        if args.fixture:
            case = SyntheticCase.model_validate_json(raw)
            request = case.request
            client = fixture_client(case, args.profile)
            verifier = None
        else:
            request = DocumentRequest.model_validate_json(raw)
            client = LLMClient(ClientSettings.from_env())
            verifier = LLMClient(ClientSettings.from_env('verification'))
    except (OSError, UnicodeError, ValidationError, LLMError) as error:
        logger.error('Cannot load extraction input: %s', error)
        return 1
    run = extract_and_verify(request, client, verifier)
    if args.output:
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open('x', encoding='utf-8') as stream:
                stream.write(run.model_dump_json(indent=2) + '\n')
        except OSError as error:
            logger.error('Cannot create extraction audit file: %s', error)
            return 1
    if args.plan and run.status == 'ready':
        result = plan_campaign(verified_campaign(run), options)
        sys.stdout.write('{"extraction":' + run.model_dump_json() + ',"planning":' + result.model_dump_json() + '}\n')
        return {'feasible': 0, 'infeasible': 2, 'unknown': 3}[result.status]
    sys.stdout.write(run.model_dump_json(indent=2) + '\n')
    return 0 if run.status == 'ready' else 6


if __name__ == '__main__':
    raise SystemExit(main())
