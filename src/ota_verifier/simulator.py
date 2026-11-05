"""Deterministic event-driven A/B simulation with one injected fault per run."""
from dataclasses import dataclass, field
from .ab import get_ecu, select_slot, slot_image, with_image
from .invariants import check_recovery_path, check_state, check_transition
from .models import Campaign, Image, Plan, PlanStep, VehicleState, Violation
from .recovery import find_recovery
from .scheduling import validate_plan
from .simulation_models import (
    Assessment, FaultSpec, FlashStage, Invariant, InvariantFinding, SimulationEvent,
    SimulationOptions, SimulationResult, StressReport,
)

STAGES: tuple[FlashStage, ...] = ('erase', 'write', 'verify', 'activate', 'boot')


@dataclass(frozen=True)
class _Scheduled:
    time_ms: int
    step: PlanStep
    stage: FlashStage


def _timeline(plan: Plan) -> tuple[_Scheduled, ...]:
    events: list[_Scheduled] = []
    for step in plan.steps:
        midpoint = step.start_ms + (step.end_ms - step.start_ms) // 2
        for stage, time in (('erase', step.start_ms), ('write', midpoint),
                            ('verify', step.end_ms), ('activate', step.end_ms), ('boot', step.end_ms)):
            events.append(_Scheduled(time, step, stage))
    # Finishing ECUs verify/activate/boot in plan order before new writes start.
    return tuple(sorted(events, key=lambda event: (
        event.time_ms, 0 if event.stage in ('verify', 'activate', 'boot') else 1,
        event.step.activation_index, STAGES.index(event.stage),
    )))


def enumerate_faults(plan: Plan) -> tuple[FaultSpec, ...]:
    """Enumerate 14 single-fault cases per changed ECU, without random sampling.

    Power loss is injected before and after every stage. Other faults occur at
    the defined corruption/detection/switch/boot boundary for that ECU.
    """
    faults: list[FaultSpec] = []
    for step in plan.steps:
        for stage in STAGES:
            for when in ('before', 'after'):
                faults.append(FaultSpec(ecu_id=step.ecu_id, stage=stage, kind='power_loss', when=when))
        for kind, stage, when in (
            ('write_corruption', 'write', 'after'), ('verification_failure', 'verify', 'before'),
            ('activation_failure', 'activate', 'before'), ('boot_failure', 'boot', 'before'),
        ):
            faults.append(FaultSpec(ecu_id=step.ecu_id, stage=stage, kind=kind, when=when))
    return tuple(faults)


def _invariant(violation: Violation) -> Invariant:
    if violation.code == 'invalid_active_image':
        return 'bootable_image'
    if violation.code == 'incompatible_versions':
        return 'compatible_versions'
    if violation.code == 'unauthorized_downgrade':
        return 'authorized_downgrade'
    return 'rollback_path'


@dataclass
class _Run:
    campaign: Campaign
    plan: Plan
    state: VehicleState
    writing: set[str] = field(default_factory=set)
    corrupted: set[str] = field(default_factory=set)
    trace: list[SimulationEvent] = field(default_factory=list)
    findings: list[InvariantFinding] = field(default_factory=list)

    def record(self, time: int, ecu_id: str | None, stage: str, message: str = '') -> None:
        """Observe state and transition invariants at each logical event."""
        checks = check_state(self.campaign, self.state)
        if self.trace:
            checks += check_transition(self.campaign, self.trace[-1].state, self.state)
        self.trace.append(SimulationEvent(time_ms=time, ecu_id=ecu_id, stage=stage,
            state=self.state, writing_ecus=tuple(sorted(self.writing)), message=message))
        self.findings.extend(InvariantFinding(invariant=_invariant(v), trace_index=len(self.trace) - 1,
                                             violation=v) for v in checks)

    def invalidate_writes(self) -> None:
        """Cancel every in-progress write; committed active pointers are retained."""
        for key in sorted(self.writing):
            step = next(step for step in self.plan.steps if step.ecu_id == key)
            self.state = with_image(self.state, key, step.write_slot, Image(version=step.to_version, valid=False))
        self.writing.clear()


def _execute(run: _Run, event: _Scheduled) -> str | None:
    step, stage = event.step, event.stage
    if stage == 'erase':
        run.state = with_image(run.state, step.ecu_id, step.write_slot, Image(version=step.to_version, valid=False))
        run.writing.add(step.ecu_id)
    elif stage == 'write':
        pass  # Written bytes remain untrusted until the verify stage.
    elif stage == 'verify':
        if step.ecu_id in run.corrupted:
            run.record(event.time_ms, step.ecu_id, stage, 'Corrupted write detected; activation blocked')
            return 'Write verification detected injected corruption'
        run.state = with_image(run.state, step.ecu_id, step.write_slot, Image(version=step.to_version, valid=True))
        run.writing.remove(step.ecu_id)
    elif stage == 'activate':
        image = slot_image(get_ecu(run.state, step.ecu_id), step.write_slot)
        if image is None or not image.valid:
            raise RuntimeError('Internal simulation error: activation attempted without a verified image')
        run.state = select_slot(run.state, step.ecu_id, step.write_slot)
    run.record(event.time_ms, step.ecu_id, stage)
    return None


def _inject(run: _Run, event: _Scheduled, fault: FaultSpec) -> str | None:
    if fault.kind == 'write_corruption':
        run.corrupted.add(fault.ecu_id)
        run.record(event.time_ms, fault.ecu_id, 'fault', 'Write corrupted; detection deferred until verification')
        return None
    if fault.kind == 'power_loss':
        run.invalidate_writes()
    elif fault.kind == 'boot_failure':
        ecu = get_ecu(run.state, fault.ecu_id)
        run.state = with_image(run.state, ecu.ecu_id, ecu.active_slot,
                              Image(version=ecu.active_image.version, valid=False))
    run.record(event.time_ms, fault.ecu_id, 'fault', f'Injected {fault.kind} {fault.when} {fault.stage}')
    return f'Campaign stopped after {fault.kind}'


def _failed(run: _Run, event: _Scheduled, fault: FaultSpec, reason: str,
            options: SimulationOptions) -> SimulationResult:
    run.invalidate_writes()
    run.record(event.time_ms, event.step.ecu_id, 'halt', reason)
    recovery = find_recovery(run.campaign, run.state, options)
    checks = check_recovery_path(run.campaign, run.state, recovery)
    run.findings.extend(InvariantFinding(invariant=_invariant(v), trace_index=len(run.trace) - 1,
                                         violation=v) for v in checks)
    if recovery.status == 'available':
        for action in recovery.steps:
            run.state = select_slot(run.state, action.ecu_id, action.to_slot)
            run.record(event.time_ms, action.ecu_id, 'recover', 'Authorized compatible recovery slot switch')
        if run.state != recovery.states[-1]:
            raise RuntimeError('Recovery execution disagrees with recorded path')
    assessment: Assessment = ('violations' if run.findings else
                              'inconclusive' if recovery.status == 'unknown' else 'passed')
    return SimulationResult(campaign_id=run.campaign.id, fault=fault, status='failed',
        assessment=assessment, trace=tuple(run.trace), findings=tuple(run.findings), recovery=recovery)


def simulate_plan(campaign: Campaign, plan: Plan, fault: FaultSpec | None = None,
                  options: SimulationOptions | None = None) -> SimulationResult:
    """Execute a validated parallel plan, optionally injecting exactly one fault.

    Erase occurs at start, write at its integer midpoint, then verification,
    activation, and boot at completion. Tied completions follow activation order
    before any starts at that timestamp. One-millisecond writes still execute
    erase before write. A fault stops the campaign, cancels remaining writes,
    and attempts authorized recovery to original active images. No LLM or Z3
    calls are made by this simulator or the recovery search.
    """
    options = options or SimulationOptions()
    findings = validate_plan(campaign, plan)
    if findings:
        raise ValueError(f'Cannot simulate invalid plan: {[v.code for v in findings]}')
    if fault is not None and fault not in enumerate_faults(plan):
        raise ValueError('Fault must refer to an applicable stage of a scheduled ECU')
    run = _Run(campaign=campaign, plan=plan, state=campaign.initial_state)
    run.record(0, None, 'initial')
    injected = False
    for event in _timeline(plan):
        matching = fault is not None and event.step.ecu_id == fault.ecu_id and event.stage == fault.stage
        if matching and fault is not None and fault.when == 'before':
            injected = True
            failure = _inject(run, event, fault)
            if failure:
                return _failed(run, event, fault, failure, options)
        failure = _execute(run, event)
        if failure:
            if fault is None or not injected:
                raise RuntimeError('Simulation failed without an injected cause')
            return _failed(run, event, fault, failure, options)
        if matching and fault is not None and fault.when == 'after':
            injected = True
            failure = _inject(run, event, fault)
            if failure:
                return _failed(run, event, fault, failure, options)
    if fault is not None:
        raise RuntimeError('Requested fault did not produce a failed run')
    if run.state != plan.states[-1]:
        raise RuntimeError('Nominal simulation disagrees with planner final state')
    return SimulationResult(campaign_id=campaign.id, fault=None, status='completed',
        assessment='violations' if run.findings else 'passed', trace=tuple(run.trace), findings=tuple(run.findings))


def stress_test(campaign: Campaign, plan: Plan,
                options: SimulationOptions | None = None) -> StressReport:
    """Run nominal execution plus every defined single-fault boundary case.

    Coverage is finite: 14 faults per updated ECU, with no multi-fault runs,
    random timing samples, automatic rollback waivers, or claims beyond this
    simulation model. Every run starts from the unchanged campaign input.
    """
    options = options or SimulationOptions()
    nominal = simulate_plan(campaign, plan, options=options)
    faults = enumerate_faults(plan)
    cases = tuple(simulate_plan(campaign, plan, fault, options) for fault in faults)
    assessments = (nominal.assessment, *(case.assessment for case in cases))
    assessment: Assessment = ('violations' if 'violations' in assessments else
                              'inconclusive' if 'inconclusive' in assessments else 'passed')
    return StressReport(campaign_id=campaign.id, plan=plan, options=options, nominal=nominal,
                        cases=cases, expected_fault_cases=len(faults), assessment=assessment)
