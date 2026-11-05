"""Deterministic JSON-in/JSON-out planning, stress testing, and boot-policy comparison."""
import argparse
from collections.abc import Sequence
import logging
from pathlib import Path
import sys
from pydantic import ValidationError
from .models import Campaign, FeasibleResult, PlanningOptions
from .simulation_models import SimulationOptions
from .simulator import stress_test
from .boot_models import GuardedOptions
from .boot_comparison import compare_boot_policies
from .planner import plan_campaign

logger = logging.getLogger(__name__)


def main(argv: Sequence[str] | None = None) -> int:
    """Emit plan or stress JSON; exits 0 success, 1 input, 2 unsat, 3 unknown.

    Stress mode additionally exits 4 for observed violations and 5 when recovery
    is inconclusive. Fault-induced campaign aborts are expected stress cases.
    """
    parser = argparse.ArgumentParser(description='Plan a simulated OTA campaign without an LLM.')
    parser.add_argument('campaign', type=Path, help='Validated campaign JSON file')
    parser.add_argument('--max-parallel', type=int, default=None)
    parser.add_argument('--deadline-ms', type=int, default=None)
    parser.add_argument('--timeout-ms', type=int, default=10_000)
    parser.add_argument('--stress-test', action='store_true', help='Run nominal and every defined single-fault case')
    parser.add_argument('--max-recovery-states', type=int, default=10_000)
    parser.add_argument('--compare-boot-policies', action='store_true', help='Compare baseline and guarded trial boot on the same plan')
    parser.add_argument('--trial-attempts', type=int, default=2)
    arguments = parser.parse_args(None if argv is None else list(argv))
    try:
        campaign = Campaign.model_validate_json(arguments.campaign.read_text(encoding='utf-8-sig'))
        options = PlanningOptions(max_parallel=arguments.max_parallel,
            deadline_ms=arguments.deadline_ms, timeout_ms=arguments.timeout_ms)
        simulation_options = SimulationOptions(max_recovery_states=arguments.max_recovery_states)
        guarded_options = GuardedOptions(max_trial_attempts=arguments.trial_attempts)
    except (OSError, ValidationError) as error:
        logger.error('Cannot load planning input: %s', error)
        return 1
    result = plan_campaign(campaign, options)
    if arguments.compare_boot_policies and isinstance(result, FeasibleResult):
        comparison = compare_boot_policies(campaign, result.plan, simulation_options, guarded_options)
        sys.stdout.write(comparison.model_dump_json(indent=2) + '\n')
        assessments = (comparison.baseline.assessment, comparison.guarded.assessment)
        return 4 if 'violations' in assessments else 5 if 'inconclusive' in assessments else 0
    if arguments.stress_test and isinstance(result, FeasibleResult):
        report = stress_test(campaign, result.plan, simulation_options)
        sys.stdout.write(report.model_dump_json(indent=2) + '\n')
        return {'passed': 0, 'violations': 4, 'inconclusive': 5}[report.assessment]
    sys.stdout.write(result.model_dump_json(indent=2) + '\n')
    return {'feasible': 0, 'infeasible': 2, 'unknown': 3}[result.status]


if __name__ == '__main__':
    raise SystemExit(main())
