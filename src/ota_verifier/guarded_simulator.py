"""Guarded trial boot with atomic confirmation and deterministic one-fault sweeps."""
from dataclasses import dataclass, field
from .ab import get_ecu
from .boot import (boot_metadata, change_boot, check_guarded_state, confirm_current,
                   guarded_boot, initial_boot_state, power_loss, set_image)
from .boot_models import (GuardedEvent, GuardedFaultSpec, GuardedOptions, GuardedResult,
                          GuardedSnapshot, GuardedStage, GuardedStressReport)
from .boot_recovery import check_guarded_recovery, find_guarded_recovery
from .invariants import check_transition
from .models import Campaign, Image, Plan, PlanStep, Violation
from .scheduling import validate_plan
from .simulation_models import Assessment, FaultSpec, Invariant, InvariantFinding, SimulationOptions
from .simulator import enumerate_faults

STAGES: tuple[GuardedStage, ...] = ('erase', 'write', 'verify', 'activate', 'boot', 'confirm')


@dataclass(frozen=True)
class _Event:
    time_ms: int
    step: PlanStep
    stage: GuardedStage


def _timeline(plan: Plan) -> tuple[_Event, ...]:
    events = []
    for step in plan.steps:
        midpoint = step.start_ms + (step.end_ms - step.start_ms) // 2
        for stage in STAGES:
            time = step.start_ms if stage == 'erase' else midpoint if stage == 'write' else step.end_ms
            events.append(_Event(time, step, stage))
    return tuple(sorted(events, key=lambda event: (
        event.time_ms, 0 if event.stage in ('verify', 'activate', 'boot', 'confirm') else 1,
        event.step.activation_index, STAGES.index(event.stage))))


def enumerate_guarded_faults(plan: Plan) -> tuple[GuardedFaultSpec, ...]:
    """Keep all 14 baseline cases and add before/after confirmation power loss."""
    shared = tuple(GuardedFaultSpec(**fault.model_dump()) for fault in enumerate_faults(plan))
    extra = tuple(GuardedFaultSpec(ecu_id=step.ecu_id, kind='power_loss', stage='confirm', when=when)
                  for step in plan.steps for when in ('before', 'after'))
    return shared + extra


def _invariant(violation: Violation) -> Invariant:
    if violation.code in ('invalid_running_image', 'unhealthy_running_image'):
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
    options: GuardedOptions
    snapshot: GuardedSnapshot
    writing: set[str] = field(default_factory=set)
    corrupted: set[str] = field(default_factory=set)
    trace: list[GuardedEvent] = field(default_factory=list)
    findings: list[InvariantFinding] = field(default_factory=list)
    blockers: list[Violation] = field(default_factory=list)

    def record(self, time: int, ecu_id: str | None, stage: str, message: str = '') -> None:
        """Check the unchanged invariant meanings at every actual observed state."""
        checks = check_guarded_state(self.campaign, self.snapshot)
        if self.trace:
            checks += check_transition(self.campaign, self.trace[-1].snapshot.state, self.snapshot.state)
        self.trace.append(GuardedEvent(time_ms=time, ecu_id=ecu_id, stage=stage,
            snapshot=self.snapshot, writing_ecus=tuple(sorted(self.writing)), message=message))
        self.findings.extend(InvariantFinding(invariant=_invariant(violation), trace_index=len(self.trace) - 1,
                                             violation=violation) for violation in checks)

    def reject(self, time: int, ecu_id: str, blockers: tuple[Violation, ...]) -> None:
        """Keep rejected proposals separate from actual invariant violations."""
        self.blockers.extend(blockers)
        self.record(time, ecu_id, 'guard_blocked', '; '.join(blocker.code for blocker in blockers))

    def cancel_writes(self) -> None:
        """Abort every concurrent write without corrupting already verified images."""
        for ecu_id in sorted(self.writing):
            step = next(step for step in self.plan.steps if step.ecu_id == ecu_id)
            self.snapshot = set_image(self.snapshot, ecu_id, step.write_slot, Image(version=step.to_version, valid=False))
        self.writing.clear()


def _execute(run: _Run, event: _Event) -> str | None:
    step = event.step
    if event.stage == 'erase':
        run.snapshot = set_image(run.snapshot, step.ecu_id, step.write_slot, Image(version=step.to_version, valid=False))
        run.writing.add(step.ecu_id)
    elif event.stage == 'verify':
        if step.ecu_id in run.corrupted:
            run.record(event.time_ms, step.ecu_id, 'verify', 'Corrupted image rejected before trial boot')
            return 'Injected write corruption detected'
        run.snapshot = set_image(run.snapshot, step.ecu_id, step.write_slot, Image(version=step.to_version, valid=True))
        run.writing.remove(step.ecu_id)
    elif event.stage == 'activate':
        run.snapshot = change_boot(run.snapshot, step.ecu_id, available=False, running_slot=None,
                                   candidate_slot=step.write_slot, attempts_used=0)
    elif event.stage == 'boot':
        metadata = boot_metadata(run.snapshot, step.ecu_id)
        if metadata.attempts_used >= run.options.max_trial_attempts:
            return 'Trial attempt budget exhausted'
        run.snapshot = change_boot(run.snapshot, step.ecu_id, attempts_used=metadata.attempts_used + 1,
                                   **{'health_a' if step.write_slot == 'A' else 'health_b': 'passed'})
        candidate, blockers = guarded_boot(run.campaign, run.snapshot, step.ecu_id, step.write_slot)
        if candidate is None:
            run.reject(event.time_ms, step.ecu_id, blockers)
            return 'Trial exposure refused by compatibility, health, availability, or authorization guard'
        run.snapshot = candidate
    elif event.stage == 'confirm':
        run.snapshot = confirm_current(run.snapshot, step.ecu_id)
    run.record(event.time_ms, step.ecu_id, event.stage)
    return None


def _inject(run: _Run, event: _Event, fault: GuardedFaultSpec) -> str | None:
    if fault.kind == 'write_corruption':
        run.corrupted.add(fault.ecu_id)
        run.record(event.time_ms, fault.ecu_id, 'fault', 'Write corrupted; verification will detect it')
        return None
    if fault.kind == 'power_loss':
        run.cancel_writes()
        run.snapshot = power_loss(run.snapshot)
    elif fault.kind == 'boot_failure':
        # One persistent unhealthy-candidate cause, not a new injected fault per retry.
        field_name = 'health_a' if event.step.write_slot == 'A' else 'health_b'
        run.snapshot = change_boot(run.snapshot, fault.ecu_id, **{field_name: 'failed'})
        while boot_metadata(run.snapshot, fault.ecu_id).attempts_used < run.options.max_trial_attempts:
            attempts = boot_metadata(run.snapshot, fault.ecu_id).attempts_used + 1
            run.snapshot = change_boot(run.snapshot, fault.ecu_id, attempts_used=attempts)
            run.record(event.time_ms, fault.ecu_id, 'boot_attempt',
                       f'Persistent candidate boot-health failure; attempt {attempts}; candidate never effective')
    run.record(event.time_ms, fault.ecu_id, 'fault', f'{fault.kind} {fault.when} {fault.stage}')
    return f'Campaign aborted after {fault.kind}'


def _restore_confirmed(run: _Run, time: int) -> None:
    """Try persisted selections first; unsafe automatic fallback is never executed."""
    pending = {metadata.ecu_id for metadata in run.snapshot.boot if not metadata.available}
    while pending:
        progress = False
        for ecu_id in sorted(tuple(pending)):
            slot = boot_metadata(run.snapshot, ecu_id).confirmed_slot
            candidate, blockers = guarded_boot(run.campaign, run.snapshot, ecu_id, slot, confirm=True)
            if candidate is None:
                run.reject(time, ecu_id, blockers)
                continue
            run.snapshot = candidate
            run.record(time, ecu_id, 'reboot', f'Restarted persisted confirmed slot {slot}')
            pending.remove(ecu_id)
            progress = True
        if not progress:
            break


def _failed(run: _Run, event: _Event, fault: GuardedFaultSpec, reason: str,
            options: SimulationOptions) -> GuardedResult:
    run.cancel_writes()
    for metadata in tuple(run.snapshot.boot):
        run.snapshot = change_boot(run.snapshot, metadata.ecu_id, candidate_slot=None)
    run.record(event.time_ms, event.step.ecu_id, 'halt', reason)
    if fault.kind == 'power_loss':
        run.record(event.time_ms, None, 'power_restored', 'Power restored; all ECUs remain unavailable until an allowed boot')
    _restore_confirmed(run, event.time_ms)
    recovery = find_guarded_recovery(run.campaign, run.snapshot, options)
    checks = check_guarded_recovery(run.campaign, run.snapshot, recovery)
    run.findings.extend(InvariantFinding(invariant=_invariant(violation), trace_index=len(run.trace) - 1,
                                         violation=violation) for violation in checks)
    if recovery.status == 'available':
        for index, action in enumerate(recovery.steps, 1):
            run.snapshot = change_boot(run.snapshot, action.ecu_id, available=False,
                                       running_slot=None, candidate_slot=action.slot)
            run.record(event.time_ms, action.ecu_id, 'recover_begin', 'Explicit coordinated recovery boot')
            candidate, blockers = guarded_boot(run.campaign, run.snapshot, action.ecu_id, action.slot)
            if candidate is None:
                raise RuntimeError(f'Guarded recovery replay rejected a proven action: {blockers}')
            run.snapshot = candidate
            run.record(event.time_ms, action.ecu_id, 'recover_boot')
            run.snapshot = confirm_current(run.snapshot, action.ecu_id)
            run.record(event.time_ms, action.ecu_id, 'recover_confirm')
            if run.snapshot != recovery.states[index]:
                raise RuntimeError('Guarded recovery execution differs from proof')
    assessment: Assessment = ('violations' if run.findings else
                              'inconclusive' if recovery.status == 'unknown' else 'passed')
    return GuardedResult(campaign_id=run.campaign.id, fault=fault, status='failed', assessment=assessment,
        trace=tuple(run.trace), findings=tuple(run.findings), recovery=recovery, guard_blockers=tuple(run.blockers))


def simulate_guarded(campaign: Campaign, plan: Plan, fault: FaultSpec | GuardedFaultSpec | None = None,
                     options: SimulationOptions | None = None,
                     guarded_options: GuardedOptions | None = None) -> GuardedResult:
    """Simulate guarded trial boot without altering a plan or weakening invariants.

    Boot health is checked before exposure. A successful trial immediately
    changes the effective version and must be compatible before confirmation.
    Confirmation is an atomic durable pointer write. Outages, trials, and
    recovery are logical events at flash completion; no reboot latency is modeled.
    """
    options, guarded_options = options or SimulationOptions(), guarded_options or GuardedOptions()
    if validate_plan(campaign, plan):
        raise ValueError('Cannot simulate an invalid nominal plan')
    normalized = GuardedFaultSpec(**fault.model_dump()) if fault is not None else None
    if normalized is not None and normalized not in enumerate_guarded_faults(plan):
        raise ValueError('Fault must identify an applicable guarded stage on a scheduled ECU')
    run = _Run(campaign, plan, guarded_options, initial_boot_state(campaign))
    run.record(0, None, 'initial')
    injected = False
    for event in _timeline(plan):
        matching = normalized is not None and event.step.ecu_id == normalized.ecu_id and event.stage == normalized.stage
        if matching and normalized is not None and normalized.when == 'before':
            injected = True
            failure = _inject(run, event, normalized)
            if failure:
                return _failed(run, event, normalized, failure, options)
        failure = _execute(run, event)
        if failure:
            if normalized is None or not injected:
                raise RuntimeError(f'Nominal guarded execution unexpectedly failed: {failure}')
            return _failed(run, event, normalized, failure, options)
        if matching and normalized is not None and normalized.when == 'after':
            injected = True
            failure = _inject(run, event, normalized)
            if failure:
                return _failed(run, event, normalized, failure, options)
    if normalized is not None:
        raise RuntimeError('Requested guarded fault was not exercised')
    if run.snapshot.state != plan.states[-1] or any(not item.available or item.confirmed_slot != item.running_slot for item in run.snapshot.boot):
        raise RuntimeError('Guarded nominal final state differs from the plan or is unconfirmed')
    return GuardedResult(campaign_id=campaign.id, fault=None, status='completed',
        assessment='violations' if run.findings else 'passed', trace=tuple(run.trace), findings=tuple(run.findings))


def stress_guarded(campaign: Campaign, plan: Plan, options: SimulationOptions | None = None,
                   guarded_options: GuardedOptions | None = None) -> GuardedStressReport:
    """Execute every shared fault plus both atomic-confirmation boundaries per ECU."""
    options, guarded_options = options or SimulationOptions(), guarded_options or GuardedOptions()
    nominal = simulate_guarded(campaign, plan, options=options, guarded_options=guarded_options)
    cases = tuple(simulate_guarded(campaign, plan, fault, options, guarded_options) for fault in enumerate_guarded_faults(plan))
    assessments = (nominal.assessment, *(case.assessment for case in cases))
    assessment: Assessment = ('violations' if 'violations' in assessments else
                              'inconclusive' if 'inconclusive' in assessments else 'passed')
    return GuardedStressReport(campaign_id=campaign.id, plan=plan, options=options,
        guarded_options=guarded_options, nominal=nominal, cases=cases,
        expected_fault_cases=len(cases), assessment=assessment)
