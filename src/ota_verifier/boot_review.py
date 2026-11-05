"""Local comparison views with explicit policy, health, and availability context."""
from typing import Any
import streamlit as st
from .boot import boot_metadata
from .boot_models import GuardedResult, GuardedSnapshot
from .review_views import vehicle_rows
from .workflow_models import ReviewBundle


def guarded_vehicle_rows(snapshot: GuardedSnapshot) -> list[dict[str, Any]]:
    """Never present a last-effective version as currently running during an outage."""
    rows = []
    for row in vehicle_rows(snapshot.state):
        metadata = boot_metadata(snapshot, row['ECU'])
        row['Effective slot'] = row.pop('Active slot')
        row['Last effective version'] = row.pop('Active version')
        row['Effective image integrity'] = row.pop('Active image valid')
        row['A integrity'] = row.pop('A valid')
        row['B integrity'] = row.pop('B valid')
        row.update({'Available': metadata.available,
            'Running version': row['Last effective version'] if metadata.available else 'unavailable',
            'Confirmed slot': metadata.confirmed_slot, 'Trial candidate': metadata.candidate_slot or 'none',
            'A boot health': metadata.health_a, 'B boot health': metadata.health_b,
            'Trial attempts used': metadata.attempts_used})
        rows.append(row)
    return rows


def _guarded_trace(case: GuardedResult, key: str) -> None:
    default = next((index for index, event in enumerate(case.trace) if event.stage == 'fault'), 0)
    event_index = st.select_slider('Guarded trace event', options=list(range(len(case.trace))), value=default, key=key)
    event = case.trace[event_index]
    st.caption(f'{event.time_ms} ms / {event.stage} / {event.ecu_id or "vehicle"}')
    if event.message:
        st.text(event.message)
    st.dataframe(guarded_vehicle_rows(event.snapshot), hide_index=True, width='stretch')
    if case.findings:
        st.dataframe([{'Invariant': finding.invariant, 'Trace': finding.trace_index,
            'Code': finding.violation.code, 'Message': finding.violation.message} for finding in case.findings],
            hide_index=True, width='stretch')
    if case.recovery:
        st.caption(f'Guarded rollback: {case.recovery.status}; search examined {case.recovery.examined_states} states.')
    blockers = case.guard_blockers + (case.recovery.blockers if case.recovery else ())
    if blockers:
        with st.expander('Guarded boot/recovery choices rejected (not executed)'):
            st.dataframe([blocker.model_dump() for blocker in blockers], hide_index=True, width='stretch')


def render_boot_comparison(bundle: ReviewBundle) -> None:
    """Show complete paired coverage, including regressions and guarded-only scenarios."""
    comparison = bundle.snapshot.artifacts.comparison
    if comparison is None:
        return
    st.subheader('Boot policy comparison')
    left, right = st.columns(2)
    left.metric('Baseline policy', comparison.baseline.assessment)
    right.metric('Guarded policy', comparison.guarded.assessment)
    st.caption(f'{len(comparison.shared_cases)} paired cases / '
        f'{len(comparison.guarded.cases)} total guarded cases / '
        f'{len(comparison.guarded_only_indices)} guarded-only confirmation cases. ' +
        (f'Explicit review target: {bundle.snapshot.artifacts.input.selected_policy.id}. Baseline findings remain retained.'
         if bundle.snapshot.artifacts.input.selected_policy is not None else 'Comparison does not overwrite the baseline decision gate.'))
    counts = st.columns(4)
    for column, label, value in zip(counts, ('Improved', 'Regressed', 'Inconclusive pairs', 'Changed findings'),
        (comparison.improved_cases, comparison.regressed_cases, comparison.inconclusive_cases, comparison.changed_finding_cases), strict=True):
        column.metric(label, value)
    with st.expander('Model assumptions and limits'):
        for assumption in comparison.assumptions:
            st.text(assumption)
    if not comparison.shared_cases:
        st.info('No updates: both policies have zero injected-fault cases. No recovery improvement is demonstrated.')
        return
    st.dataframe([{'ECU': row.fault.ecu_id, 'Fault': row.fault.kind, 'Stage': row.fault.stage,
        'Boundary': row.fault.when, 'Baseline': row.baseline_assessment, 'Guarded': row.guarded_assessment,
        'Change': row.change, 'Removed invariant findings': ', '.join(row.removed_invariants),
        'Added invariant findings': ', '.join(row.added_invariants)} for row in comparison.shared_cases], hide_index=True, width='stretch')
    def label(index: int) -> str:
        row = comparison.shared_cases[index]
        return f'{index + 1}. {row.fault.ecu_id}: {row.fault.kind} {row.fault.when} {row.fault.stage} / {row.change}'
    index = st.selectbox('Paired fault scenario', list(range(len(comparison.shared_cases))), format_func=label,
                         key=f'paired_case_{bundle.revision}')
    row = comparison.shared_cases[index]
    baseline = comparison.baseline.cases[row.baseline_index]
    guarded = comparison.guarded.cases[row.guarded_index]
    left, right = st.columns(2)
    with left:
        st.write(f'Baseline: **{baseline.assessment}**')
        default = next((index for index, event in enumerate(baseline.trace) if event.stage == 'fault'), 0)
        event_index = st.select_slider('Baseline paired trace event', options=list(range(len(baseline.trace))),
            value=default, key=f'baseline_paired_trace_{bundle.revision}_{index}')
        event = baseline.trace[event_index]
        st.caption(f'{event.time_ms} ms / {event.stage} / {event.ecu_id or "vehicle"}')
        st.dataframe(vehicle_rows(event.state), hide_index=True, width='stretch')
    with right:
        st.write(f'Guarded: **{guarded.assessment}**')
        _guarded_trace(guarded, f'guarded_paired_trace_{bundle.revision}_{index}')
    if comparison.guarded_only_indices:
        st.write('Guarded-only confirmation coverage')
        extra = st.selectbox('Confirmation power-loss scenario', list(comparison.guarded_only_indices),
            format_func=lambda index: f'{comparison.guarded.cases[index].fault.ecu_id}: '
            f'{comparison.guarded.cases[index].fault.when} confirm', key=f'confirmation_case_{bundle.revision}')
        _guarded_trace(comparison.guarded.cases[extra], f'guarded_extra_trace_{bundle.revision}_{extra}')
    st.divider()
