"""Deterministic evidence catalog shared by the review UI and explanation boundary."""
from .llm.evidence import canonical_json
from .llm.explanation_models import EvidenceFact
from .workflow_models import AnalysisArtifacts


def evidence_catalog(artifacts: AnalysisArtifacts) -> tuple[EvidenceFact, ...]:
    """Build stable facts from actual results without a model-generated verdict."""
    extraction = artifacts.extraction
    facts: list[EvidenceFact] = [EvidenceFact(id='extraction', kind='extraction',
        outcome='passed' if extraction.status == 'ready' else 'blocked',
        message=f'Extraction gate: {extraction.status}; {len(extraction.issues)} unresolved findings.',
        detail_json=canonical_json({'status': extraction.status, 'issues': len(extraction.issues)}),
        required_in_explanation=True)]
    selection = artifacts.input.selected_policy
    if selection is not None:
        facts.append(EvidenceFact(id='selected-policy', kind='simulation', outcome='information',
            message=f'Selected simulation policy: {selection.id}. Overall status applies only to this policy; '
                    'comparison results retain their own assessments. Approval binds this selection and options.',
            detail_json=selection.model_dump_json(), required_in_explanation=True))
    for index, issue in enumerate(extraction.issues):
        facts.append(EvidenceFact(id=f'extraction-issue:{index}', kind='extraction', outcome='blocked',
            message=issue.message, detail_json=issue.model_dump_json(), constraint_id=issue.constraint_id,
            source_document_id=issue.evidence.document_id if issue.evidence else None))
    if extraction.draft:
        for entry in extraction.draft.constraints:
            rule = entry.constraint
            facts.append(EvidenceFact(id=f'constraint:{rule.id}', kind='constraint', outcome='information',
                message=rule.source_text, detail_json=entry.model_dump_json(), constraint_id=rule.id,
                source_document_id=rule.source_document_id, source_text=rule.source_text))
    planning = artifacts.planning
    if planning is not None:
        if planning.status == 'feasible':
            message = f'Nominal plan is feasible: {len(planning.plan.steps)} updates, {planning.plan.makespan_ms} ms; optimal={planning.plan.optimal}.'
        elif planning.status == 'infeasible':
            message = f'No nominal plan under the model; {len(planning.conflict.items)} conflict groups; subset_minimal={planning.conflict.subset_minimal}.'
        else:
            message = f'Planning feasibility is unknown: {planning.reason}'
        facts.append(EvidenceFact(id='plan', kind='plan', outcome=planning.status,
            message=message, detail_json=planning.model_dump_json(exclude={'plan'}), required_in_explanation=True))
        if planning.status == 'feasible':
            for step in planning.plan.steps:
                facts.append(EvidenceFact(id=f'step:{step.activation_index}', kind='step', outcome='information',
                    message=f'{step.ecu_id}: write {step.start_ms}..{step.end_ms} ms, activate #{step.activation_index}, {step.from_version} -> {step.to_version}.',
                    detail_json=step.model_dump_json()))
        elif planning.status == 'infeasible':
            for index, item in enumerate(planning.conflict.items):
                facts.append(EvidenceFact(id=f'conflict:{index}', kind='conflict', outcome='infeasible',
                    message=f'{item.id}: {item.message}', detail_json=item.model_dump_json(),
                    constraint_id=item.id if item.kind == 'constraint' else None,
                    source_document_id=item.source_document_id, source_text=item.source_text))
    report = artifacts.simulation
    if report is not None:
        counts = {key: sum(case.assessment == key for case in report.cases)
                  for key in ('passed', 'violations', 'inconclusive')}
        outcome = {'passed': 'passed', 'violations': 'violation', 'inconclusive': 'unknown'}[report.assessment]
        facts.append(EvidenceFact(id='simulation', kind='simulation', outcome=outcome,
            message=f'{"Baseline stress" if selection is not None else "Stress"} assessment: {report.assessment}; nominal={report.nominal.assessment}; {len(report.cases)}/{report.expected_fault_cases} fault cases; {counts}.',
            detail_json=canonical_json({'assessment': report.assessment, 'nominal': report.nominal.assessment,
                'expected_fault_cases': report.expected_fault_cases, 'executed_fault_cases': len(report.cases), 'counts': counts}),
            required_in_explanation=True))
        for index, case in enumerate(report.cases):
            fault = case.fault
            assert fault is not None
            case_outcome = {'passed': 'passed', 'violations': 'violation', 'inconclusive': 'unknown'}[case.assessment]
            facts.append(EvidenceFact(id=f'fault:{index}', kind='fault', outcome=case_outcome,
                message=f'{fault.ecu_id}: {fault.kind} {fault.when} {fault.stage}; assessment={case.assessment}; recovery={case.recovery.status if case.recovery else "none"}.',
                detail_json=canonical_json({'fault': fault.model_dump(mode='json'), 'assessment': case.assessment,
                    'recovery': case.recovery.status if case.recovery else None}), case_index=index))
            for finding_index, finding in enumerate(case.findings):
                event = case.trace[finding.trace_index]
                violation = finding.violation
                facts.append(EvidenceFact(id=f'finding:{index}:{finding_index}', kind='finding', outcome='violation',
                    message=f'{finding.invariant}: {violation.message}', case_index=index, trace_index=finding.trace_index,
                    constraint_id=violation.constraint_id, source_document_id=violation.source_document_id,
                    source_text=violation.source_text, detail_json=canonical_json({
                        'finding': finding.model_dump(mode='json'), 'stage': event.stage, 'time_ms': event.time_ms,
                        'active_images': {ecu.ecu_id: {'version': ecu.active_image.version, 'valid': ecu.active_image.valid}
                                          for ecu in event.state.ecus}})))
    comparison = artifacts.comparison
    if comparison is not None:
        facts.append(EvidenceFact(id='boot-comparison', kind='simulation', outcome='information',
            message=f'Boot policy comparison: {len(comparison.shared_cases)} common cases, '
                    f'{len(comparison.guarded_only_indices)} guarded-only confirmation cases; '
                    f'improved={comparison.improved_cases}, regressed={comparison.regressed_cases}, '
                    f'inconclusive={comparison.inconclusive_cases}. ' +
                    (f'Approval evaluates the explicitly selected policy {selection.id}.' if selection is not None
                     else 'Baseline remains the primary decision gate.'),
            detail_json=canonical_json({'improved': comparison.improved_cases, 'regressed': comparison.regressed_cases,
                'inconclusive': comparison.inconclusive_cases, 'changed_findings': comparison.changed_finding_cases}),
            required_in_explanation=True))
        facts.append(EvidenceFact(id='guarded-simulation', kind='simulation',
            outcome={'passed': 'passed', 'violations': 'violation', 'inconclusive': 'unknown'}[comparison.guarded.assessment],
            message=f'Guarded policy assessment: {comparison.guarded.assessment}; '
                    f'{len(comparison.guarded.cases)}/{comparison.guarded.expected_fault_cases} cases. ' +
                    (f'Baseline assessment remains {comparison.baseline.assessment}; selected policy is {selection.id}.'
                     if selection is not None else f'This does not replace baseline assessment {comparison.baseline.assessment}.'),
            detail_json=comparison.guarded.guarded_options.model_dump_json(), required_in_explanation=True))
        facts.append(EvidenceFact(id='boot-policy-assumptions', kind='simulation', outcome='information',
            message='Policy assumptions: ' + ' '.join(comparison.assumptions),
            detail_json=canonical_json(comparison.assumptions), required_in_explanation=True))
        for case_index, case in enumerate(comparison.guarded.cases):
            for finding_index, finding in enumerate(case.findings):
                event = case.trace[finding.trace_index]
                violation = finding.violation
                facts.append(EvidenceFact(id=f'guarded-finding:{case_index}:{finding_index}', kind='finding',
                    outcome='violation', message=f'Guarded {finding.invariant}: {violation.message}',
                    case_index=case_index, trace_index=finding.trace_index, constraint_id=violation.constraint_id,
                    source_document_id=violation.source_document_id, source_text=violation.source_text,
                    detail_json=canonical_json({'policy': 'guarded-trial-v1', 'finding': finding.model_dump(mode='json'),
                        'stage': event.stage, 'time_ms': event.time_ms})))
    if len({fact.id for fact in facts}) != len(facts):
        raise RuntimeError('Evidence catalog has duplicate IDs')
    return tuple(facts)
