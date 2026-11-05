"""Like-for-like logical fault comparison, with policy-specific coverage explicit."""
from collections import Counter
from typing import Literal, Self
from pydantic import model_validator
from .boot_models import GuardedOptions, GuardedResult, GuardedStressReport
from .guarded_simulator import stress_guarded
from .models import Campaign, Plan, Record
from .simulation_models import Assessment, FaultSpec, SimulationOptions, SimulationResult, StressReport
from .simulator import stress_test

Change = Literal['improved', 'regressed', 'changed_findings', 'unchanged', 'inconclusive']
ASSUMPTIONS = (
    'Same campaign, supplied nominal plan, rounded write durations, and recovery-search limit.',
    'Common faults match ECU, kind, stage, and before/after boundary; effects follow each boot policy.',
    'Guarded health succeeds before exposure; trials, reboot, and confirmation have no modeled elapsed duration.',
    'Confirmed slot, attempt counter, and observed slot health survive power loss; runtime and trial selection do not.',
    'Confirmation is atomic; torn metadata, watchdog timing, and multiple independent faults are outside this model.',
    'Outages retain last effective versions for compatibility but provide no running image or availability guarantee.',
    'Recovery must restore original running confirmed images using known healthy stored slots and explicit downgrade permissions.',
    'Availability gating is an extra operational guard; baseline results do not establish cold-start availability.',
)


def fault_key(fault: FaultSpec) -> tuple[str, str, str, str]:
    """Match shared causes across baseline and guarded fault model classes."""
    return fault.ecu_id, fault.kind, fault.stage, fault.when


class CaseComparison(Record):
    """One shared logical cause, with navigable indices into both complete reports."""
    fault: FaultSpec
    baseline_index: int
    guarded_index: int
    baseline_assessment: Assessment
    guarded_assessment: Assessment
    baseline_recovery: str
    guarded_recovery: str
    baseline_codes: tuple[str, ...]
    guarded_codes: tuple[str, ...]
    removed_invariants: tuple[str, ...]
    added_invariants: tuple[str, ...]
    change: Change


def _signature(result: SimulationResult | GuardedResult) -> set[tuple[object, ...]]:
    return {(finding.invariant, finding.violation.code, finding.violation.ecu_ids,
             finding.violation.constraint_id) for finding in result.findings}


def _row(baseline: SimulationResult, guarded: GuardedResult, base_index: int, guard_index: int) -> CaseComparison:
    assert baseline.fault is not None and guarded.fault is not None
    old, new = baseline.assessment, guarded.assessment
    old_recovery = baseline.recovery.status if baseline.recovery else 'none'
    new_recovery = guarded.recovery.status if guarded.recovery else 'none'
    if 'inconclusive' in (old, new):
        change = 'inconclusive'
    elif old == 'violations' and new == 'passed':
        change = 'improved'
    elif old == 'passed' and new == 'violations':
        change = 'regressed'
    elif _signature(baseline) != _signature(guarded) or old_recovery != new_recovery:
        change = 'changed_findings'
    else:
        change = 'unchanged'
    old_invariants = {finding.invariant for finding in baseline.findings}
    new_invariants = {finding.invariant for finding in guarded.findings}
    return CaseComparison(fault=baseline.fault, baseline_index=base_index, guarded_index=guard_index,
        baseline_assessment=old, guarded_assessment=new, baseline_recovery=old_recovery,
        guarded_recovery=new_recovery, baseline_codes=tuple(sorted({f.violation.code for f in baseline.findings})),
        guarded_codes=tuple(sorted({f.violation.code for f in guarded.findings})),
        removed_invariants=tuple(sorted(old_invariants - new_invariants)),
        added_invariants=tuple(sorted(new_invariants - old_invariants)), change=change)


def paired_rows(baseline: StressReport, guarded: GuardedStressReport) -> tuple[CaseComparison, ...]:
    """Pair every baseline cause without omitting failures or unknown results."""
    lookup = {fault_key(case.fault): (index, case) for index, case in enumerate(guarded.cases) if case.fault}
    rows: list[CaseComparison] = []
    for index, case in enumerate(baseline.cases):
        assert case.fault is not None
        if fault_key(case.fault) not in lookup:
            raise ValueError('Guarded report omitted a shared fault scenario')
        guarded_index, result = lookup[fault_key(case.fault)]
        rows.append(_row(case, result, index, guarded_index))
    return tuple(rows)


class PolicyComparison(Record):
    """Complete raw evidence and derived comparisons; no cross-policy approval label."""
    campaign: Campaign
    baseline: StressReport
    guarded: GuardedStressReport
    assumptions: tuple[str, ...] = ASSUMPTIONS
    shared_cases: tuple[CaseComparison, ...]
    guarded_only_indices: tuple[int, ...]
    improved_cases: int
    regressed_cases: int
    changed_finding_cases: int
    unchanged_cases: int
    inconclusive_cases: int

    @model_validator(mode='after')
    def full_pairing(self) -> Self:
        """Bind plans/options/coverage and recompute every claimed comparison and count."""
        if (self.baseline.plan != self.guarded.plan or self.baseline.options != self.guarded.options
                or self.baseline.campaign_id != self.campaign.id or self.guarded.campaign_id != self.campaign.id):
            raise ValueError('Policies must compare the same campaign, nominal plan, and recovery options')
        if self.assumptions != ASSUMPTIONS or self.shared_cases != paired_rows(self.baseline, self.guarded):
            raise ValueError('Comparison assumptions or paired results were altered')
        common = {fault_key(case.fault) for case in self.baseline.cases if case.fault}
        extra = tuple(index for index, case in enumerate(self.guarded.cases) if case.fault and fault_key(case.fault) not in common)
        if self.guarded_only_indices != extra or len(extra) != 2 * len(self.baseline.plan.steps):
            raise ValueError('Guarded-only confirmation coverage must be reported separately')
        counts = Counter(row.change for row in self.shared_cases)
        if (self.improved_cases, self.regressed_cases, self.changed_finding_cases, self.unchanged_cases, self.inconclusive_cases) != (
            counts['improved'], counts['regressed'], counts['changed_findings'], counts['unchanged'], counts['inconclusive']):
            raise ValueError('Comparison summary counts disagree with paired evidence')
        return self


def compare_boot_policies(campaign: Campaign, plan: Plan, options: SimulationOptions | None = None,
                          guarded_options: GuardedOptions | None = None,
                          baseline_report: StressReport | None = None) -> PolicyComparison:
    """Compare deterministic boot policies; never plan, call a model, or discard faults.

    A supplied baseline report is trusted analysis evidence from the current
    workflow, not an authenticated external simulation proof.
    """
    options = options or SimulationOptions()
    baseline = baseline_report or stress_test(campaign, plan, options)
    if baseline.plan != plan or baseline.options != options or baseline.campaign_id != campaign.id:
        raise ValueError('Supplied baseline evidence differs from comparison inputs')
    guarded = stress_guarded(campaign, plan, options, guarded_options)
    rows = paired_rows(baseline, guarded)
    common = {fault_key(case.fault) for case in baseline.cases if case.fault}
    extra = tuple(index for index, case in enumerate(guarded.cases) if case.fault and fault_key(case.fault) not in common)
    counts = Counter(row.change for row in rows)
    return PolicyComparison(campaign=campaign, baseline=baseline, guarded=guarded, shared_cases=rows,
        guarded_only_indices=extra, improved_cases=counts['improved'], regressed_cases=counts['regressed'],
        changed_finding_cases=counts['changed_findings'], unchanged_cases=counts['unchanged'],
        inconclusive_cases=counts['inconclusive'])
