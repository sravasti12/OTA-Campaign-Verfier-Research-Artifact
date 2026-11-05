"""Z3 parallel scheduling with ordered activation and traceable conflicts.

This module models nominal execution only. It never calls an LLM.
"""
from dataclasses import dataclass, field
from itertools import combinations
from math import ceil
from time import monotonic
from collections.abc import Sequence
import logging
import z3
from .compat import requirement_holds
from .models import (
    Campaign, ConflictItem, ConflictReport, ECU, FeasibleResult, InfeasibleResult,
    Mutex, Order, Plan, PlanningOptions, PlanningResult, PlanStep, Precondition,
    Requires, UnknownResult,
)
from .scheduling import (
    activate_target, constraint_ecus, downgrade_allowed, duration_ms, validate_plan,
)
from .versions import matches, parse_version

logger = logging.getLogger(__name__)


@dataclass
class _Problem:
    campaign: Campaign
    options: PlanningOptions
    changed: dict[str, ECU]
    solver: z3.Solver = field(default_factory=z3.Solver)
    starts: dict[str, z3.ArithRef] = field(default_factory=dict)
    ends: dict[str, z3.ArithRef] = field(default_factory=dict)
    ranks: dict[str, z3.ArithRef] = field(default_factory=dict)
    labels: list[z3.BoolRef] = field(default_factory=list)
    evidence: dict[str, ConflictItem] = field(default_factory=dict)
    makespan: z3.ArithRef = field(default_factory=lambda: z3.Int('makespan'))

    def track(self, expression: z3.BoolRef | bool, evidence: ConflictItem) -> None:
        """Guard a semantic group with an opaque, collision-free assumption."""
        label = z3.Bool(f'group_{len(self.labels)}')
        self.labels.append(label)
        self.evidence[str(label)] = evidence
        self.solver.add(z3.Implies(label, expression))


@dataclass
class _Budget:
    deadline: float
    reason: str = 'Planning timeout budget exhausted'

    def check(self, problem: _Problem, assumptions: Sequence[z3.BoolRef],
              extra: Sequence[z3.BoolRef] = ()) -> z3.CheckSatResult:
        """Bound each check by the remaining total planning budget."""
        remaining = self.deadline - monotonic()
        if remaining <= 0:
            return z3.unknown
        problem.solver.set(timeout=max(1, ceil(remaining * 1000)))
        result = problem.solver.check(*assumptions, *extra)
        if result == z3.unknown:
            self.reason = problem.solver.reason_unknown()
        return result


def _add_schedule_structure(problem: _Problem) -> None:
    count = len(problem.changed)
    horizon = sum(duration_ms(ecu) for ecu in problem.changed.values())
    for index, (key, ecu) in enumerate(problem.changed.items()):
        problem.starts[key] = z3.Int(f'start_{index}')
        problem.ends[key] = z3.Int(f'end_{index}')
        problem.ranks[key] = z3.Int(f'rank_{index}')
        problem.solver.add(
            problem.starts[key] >= 0,
            problem.ends[key] == problem.starts[key] + duration_ms(ecu),
            problem.ends[key] <= horizon,
            problem.ranks[key] >= 1, problem.ranks[key] <= count,
        )
    if count:
        problem.solver.add(z3.Distinct(*problem.ranks.values()))
        for a, b in combinations(problem.changed, 2):
            problem.solver.add(
                z3.Implies(problem.ranks[a] < problem.ranks[b], problem.ends[a] <= problem.ends[b]),
                z3.Implies(problem.ranks[b] < problem.ranks[a], problem.ends[b] <= problem.ends[a]),
            )
        problem.solver.add(*(problem.makespan >= end for end in problem.ends.values()))
        problem.solver.add(z3.Or(*(problem.makespan == end for end in problem.ends.values())))
    else:
        problem.solver.add(problem.makespan == 0)


def _symbolic_match(problem: _Problem, stage: int, ecu: str, spec: str) -> z3.BoolRef:
    config = next(config for config in problem.campaign.ecus if config.id == ecu)
    current = z3.BoolVal(matches(config.current_version, spec))
    if ecu not in problem.changed:
        return current
    return z3.If(problem.ranks[ecu] <= stage, z3.BoolVal(matches(config.target_version, spec)), current)


def _constraint_expression(problem: _Problem, constraint: Requires | Mutex | Order | Precondition) -> z3.BoolRef:
    if isinstance(constraint, Requires):
        return z3.And(*(requirement_holds(
            constraint, lambda ecu, spec, stage=stage: _symbolic_match(problem, stage, ecu, spec),
            z3.Implies,
        ) for stage in range(len(problem.changed) + 1)))
    if isinstance(constraint, Mutex):
        members = [ecu for ecu in constraint.ecus if ecu in problem.changed]
        return z3.And(*(z3.Or(problem.ends[a] <= problem.starts[b],
                              problem.ends[b] <= problem.starts[a])
                        for a, b in combinations(members, 2)))
    if isinstance(constraint, Order):
        if constraint.before not in problem.changed or constraint.after not in problem.changed:
            return z3.BoolVal(True)
        return problem.ends[constraint.before] <= problem.starts[constraint.after]
    if constraint.ecu not in problem.changed:
        return z3.BoolVal(True)
    state = problem.campaign.initial_state
    return z3.BoolVal(state.ignition == constraint.ignition
                      and state.battery_percent >= constraint.minimum_battery_percent)


def _add_requirements(problem: _Problem) -> None:
    for constraint in problem.campaign.constraints:
        problem.track(_constraint_expression(problem, constraint), ConflictItem(
            kind='constraint', id=constraint.id, ecu_ids=constraint_ecus(constraint),
            message=f'{constraint.type} requirement', source_document_id=constraint.source_document_id,
            source_text=constraint.source_text,
        ))
    for state in sorted(problem.campaign.initial_state.ecus, key=lambda state: state.ecu_id):
        problem.track(state.active_image.valid, ConflictItem(
            kind='policy', id=f'bootable:{state.ecu_id}', ecu_ids=(state.ecu_id,),
            message='Initial active image must be valid',
        ))
    for key, ecu in problem.changed.items():
        problem.track(downgrade_allowed(problem.campaign, ecu), ConflictItem(
            kind='policy', id=f'downgrade:{key}', ecu_ids=(key,),
            message=f'Downgrade to {ecu.target_version} requires exact ECU/version authorization',
        ))
    if problem.options.max_parallel is not None:
        limit = problem.options.max_parallel
        expressions = [z3.Sum(*(z3.If(z3.And(problem.starts[other] <= start,
                                            start < problem.ends[other]), 1, 0)
                               for other in problem.changed)) <= limit
                       for start in problem.starts.values()]
        problem.track(z3.And(*expressions), ConflictItem(
            kind='resource', id='max_parallel', message=f'At most {limit} overlapping writes',
        ))
    if problem.options.deadline_ms is not None:
        deadline = problem.options.deadline_ms
        problem.track(problem.makespan <= deadline, ConflictItem(
            kind='resource', id='deadline', message=f'Campaign must finish within {deadline} ms',
        ))


def _build_problem(campaign: Campaign, options: PlanningOptions) -> _Problem:
    changed = {ecu.id: ecu for ecu in sorted(campaign.ecus, key=lambda ecu: ecu.id)
               if parse_version(ecu.current_version) != parse_version(ecu.target_version)}
    problem = _Problem(campaign, options, changed)
    problem.solver.set(random_seed=0)
    _add_schedule_structure(problem)
    _add_requirements(problem)
    return problem


def _conflict(problem: _Problem, budget: _Budget) -> InfeasibleResult:
    core_names = {str(label) for label in problem.solver.unsat_core()}
    core = [label for label in problem.labels if str(label) in core_names]
    minimal = True
    for label in tuple(core):
        candidate = [other for other in core if str(other) != str(label)]
        result = budget.check(problem, candidate)
        if result == z3.unsat:
            core = candidate
        elif result == z3.unknown:
            minimal = False
            break
    if not core:
        raise RuntimeError('Internal scheduling structure unexpectedly infeasible')
    return InfeasibleResult(conflict=ConflictReport(
        items=tuple(problem.evidence[str(label)] for label in core), subset_minimal=minimal,
    ), note=None if minimal else f'Conflict proven; minimization incomplete: {budget.reason}')


def _minimize(problem: _Problem, budget: _Budget, expression: z3.ArithRef,
              model: z3.ModelRef) -> tuple[z3.ModelRef, bool]:
    lower, upper = 0, model.eval(expression).as_long()
    while lower < upper:
        midpoint = (lower + upper) // 2
        result = budget.check(problem, problem.labels, (expression <= midpoint,))
        if result == z3.sat:
            model = problem.solver.model()
            upper = model.eval(expression).as_long()
        elif result == z3.unsat:
            lower = midpoint + 1
        else:
            return model, False
    return model, True


def _optimize(problem: _Problem, budget: _Budget,
              model: z3.ModelRef) -> tuple[z3.ModelRef, bool, str | None]:
    model, optimal = _minimize(problem, budget, problem.makespan, model)
    if not optimal:
        return model, False, f'Feasible schedule; optimality not established: {budget.reason}'
    problem.solver.add(problem.makespan == model.eval(problem.makespan))
    # Stable tie-breaking: earliest starts, then activation ranks, in ECU ID order.
    for expression in (*problem.starts.values(), *problem.ranks.values()):
        model, complete = _minimize(problem, budget, expression, model)
        if not complete:
            return model, True, f'Makespan optimal; tie-breaking incomplete: {budget.reason}'
        problem.solver.add(expression == model.eval(expression))
    return model, True, None


def _make_plan(problem: _Problem, model: z3.ModelRef, optimal: bool) -> Plan:
    steps: list[PlanStep] = []
    states = [problem.campaign.initial_state]
    for key in sorted(problem.changed, key=lambda key: model.eval(problem.ranks[key]).as_long()):
        ecu = problem.changed[key]
        initial = next(state for state in problem.campaign.initial_state.ecus if state.ecu_id == key)
        steps.append(PlanStep(
            ecu_id=key, from_version=ecu.current_version, to_version=ecu.target_version,
            write_slot='B' if initial.active_slot == 'A' else 'A',
            start_ms=model.eval(problem.starts[key]).as_long(), end_ms=model.eval(problem.ends[key]).as_long(),
            activation_index=model.eval(problem.ranks[key]).as_long(),
            constraint_ids=tuple(c.id for c in problem.campaign.constraints if key in constraint_ecus(c)),
        ))
        states.append(activate_target(states[-1], ecu))
    plan = Plan(campaign_id=problem.campaign.id, steps=tuple(steps), states=tuple(states),
                makespan_ms=model.eval(problem.makespan).as_long(), optimal=optimal, options=problem.options)
    findings = validate_plan(problem.campaign, plan)
    if findings:
        logger.error('Planner replay failed for campaign %s: %s', problem.campaign.id, findings)
        raise RuntimeError('Internal planner error: nominal plan failed independent validation')
    return plan


def plan_campaign(campaign: Campaign, options: PlanningOptions | None = None) -> PlanningResult:
    """Find a minimum-makespan parallel schedule or explain a contradiction.

    Writes use half-open millisecond intervals, rounded-up durations, and optional
    capacity/deadline limits. Activations are ordered even at equal timestamps.
    The environment is fixed; no bridge images or fault recovery are assumed.
    Unknown solver results never become infeasibility claims. A previously
    established feasible plan may be returned without an optimality guarantee.
    """
    options = options or PlanningOptions()
    budget = _Budget(monotonic() + options.timeout_ms / 1000)
    problem = _build_problem(campaign, options)
    result = budget.check(problem, problem.labels)
    if result == z3.unknown:
        return UnknownResult(reason=budget.reason)
    if result == z3.unsat:
        return _conflict(problem, budget)
    model, optimal, note = _optimize(problem, budget, problem.solver.model())
    return FeasibleResult(plan=_make_plan(problem, model, optimal), note=note)
