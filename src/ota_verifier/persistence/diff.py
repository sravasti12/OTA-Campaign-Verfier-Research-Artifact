"""Literal revision differences for human review; no LLM or solver calls."""
import json
from typing import Any
from ..llm.evidence import canonical_json
from ..workflow_models import ReviewBundle
from .models import RevisionChange, RevisionDiff


def _projection(bundle: ReviewBundle) -> dict[str, Any]:
    artifacts = bundle.snapshot.artifacts
    request = artifacts.input.request
    campaign = request.campaign
    findings = set()
    if artifacts.simulation:
        for case in artifacts.simulation.cases:
            for finding in case.findings:
                findings.add(canonical_json({'invariant': finding.invariant, 'violation': finding.violation.model_dump(mode='json')}))
    return {
        'documents': {document.id: document.text for document in request.documents},
        'inventory': campaign.model_dump(mode='json', exclude={'constraints', 'downgrade_authorizations'}),
        'permissions': [permission.model_dump(mode='json') for permission in campaign.downgrade_authorizations],
        'constraints': {entry.constraint.id: entry.constraint.model_dump(mode='json')
                        for entry in artifacts.extraction.draft.constraints} if artifacts.extraction.draft else {},
        'options': artifacts.input.model_dump(mode='json', exclude={'request'}),
        'plan': artifacts.planning.plan.model_dump(mode='json', exclude={'states'}) if artifacts.planning and artifacts.planning.status == 'feasible' else None,
        'findings': [json.loads(value) for value in sorted(findings)],
        'outcome': artifacts.status,
        'comparison': {'baseline': artifacts.comparison.baseline.assessment, 'guarded': artifacts.comparison.guarded.assessment,
                       'improved': artifacts.comparison.improved_cases, 'regressed': artifacts.comparison.regressed_cases}
                      if artifacts.comparison else None,
    }


def compare_revisions(before: ReviewBundle, after: ReviewBundle) -> RevisionDiff:
    """Show literal changes in reviewed material without treating equality as a proof."""
    if before.run_id != after.run_id:
        raise ValueError('Revision comparison requires the same run')
    changes: list[RevisionChange] = []
    old, new = _projection(before), _projection(after)
    def walk(section: str, path: str, left: Any, right: Any) -> None:
        if left == right:
            return
        if isinstance(left, dict) and isinstance(right, dict):
            for key in sorted(set(left) | set(right)):
                walk(section, f'{path}.{key}' if path else key, left.get(key), right.get(key))
        else:
            changes.append(RevisionChange(section=section, path=path, before_json=canonical_json(left), after_json=canonical_json(right)))
    for section in old:
        walk(section, section, old[section], new[section])
    return RevisionDiff(run_id=before.run_id, before_revision=before.revision,
                        after_revision=after.revision, changes=tuple(changes))
