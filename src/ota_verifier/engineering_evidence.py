"""Deterministic simulation evidence exports; no regulatory verdicts or safety decisions."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import Field, model_validator

from .compat import check_compatibility
from .evidence import evidence_catalog
from .llm.evidence import canonical_json, content_hash
from .llm.pipeline import verified_campaign
from .llm.explainer import validate_explanation
from .models import FeasibleResult, Record
from .workflow_models import ReviewBundle, ReviewSnapshot

ASSERTION = 'Simulated engineering evidence only; no regulatory approval or certification asserted.'


def digest_file(path: Path) -> str:
    """Hash a file without interpreting its provenance as execution evidence."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def trace_summary(snapshot: ReviewSnapshot) -> dict[str, Any]:
    """Derive traceability, compatibility, violations and rollback from existing artifacts."""
    artifacts = snapshot.artifacts
    extraction = artifacts.extraction
    constraints = []
    if extraction.draft is not None:
        constraints = [entry.model_dump(mode='json') for entry in extraction.draft.constraints]
    compatibility = []
    if isinstance(artifacts.planning, FeasibleResult):
        campaign = verified_campaign(extraction)
        compatibility = [{'state_index':index, 'findings':[v.model_dump(mode='json')
            for v in check_compatibility(campaign,state)]}
            for index,state in enumerate(artifacts.planning.plan.states)]
    simulation = artifacts.simulation
    findings: Counter[str] = Counter()
    faults: list[dict[str, Any]] = []
    if simulation is not None:
        for result in (simulation.nominal,*simulation.cases):
            findings.update(item.violation.code for item in result.findings)
        faults = [{'case_index':index,'fault':case.fault.model_dump(mode='json'),
                   'assessment':case.assessment,'findings':[item.model_dump(mode='json') for item in case.findings],
                   'recovery_status':case.recovery.status if case.recovery is not None else None,
                   'recovery_steps':[step.model_dump(mode='json') for step in case.recovery.steps]
                       if case.recovery is not None else []}
                  for index,case in enumerate(simulation.cases)]
    return {'source_documents':[{'id':doc.id,'sha256':content_hash(doc.text)} for doc in extraction.request.documents],
        'constraints_and_spans':constraints,'compatibility':compatibility,
        'analysis_status':artifacts.status,'fault_cases':faults,
        'finding_occurrences':dict(sorted(findings.items())),
        'nominal_assessment':simulation.nominal.assessment if simulation is not None else None,
        'expected_fault_cases':simulation.expected_fault_cases if simulation is not None else None}


class ArtifactReference(Record):
    """An explicit existing-artifact hash, not proof of fresh execution or authenticity."""
    label: str
    path: str
    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    origin: Literal['HASHED_EXISTING_ARTIFACT'] = 'HASHED_EXISTING_ARTIFACT'


class EngineeringPackage(Record):
    """Self-consistent, versioned evidence containing the complete original snapshot."""
    format_version: Literal['engineering-evidence-v1'] = 'engineering-evidence-v1'
    scope: Literal['SIMULATION'] = 'SIMULATION'
    assertion: Literal['Simulated engineering evidence only; no regulatory approval or certification asserted.'] = ASSERTION
    campaign_id: str
    recorded_at: str
    snapshot: ReviewSnapshot
    review_bundle: ReviewBundle | None = None
    human_review_status: str
    traceability: dict[str, Any]
    gaps: tuple[str, ...]
    tool_versions: dict[str, str]
    references: tuple[ArtifactReference, ...] = ()
    package_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')

    @model_validator(mode='after')
    def consistent_evidence(self) -> Self:
        """Reject altered trace summaries, invalid handoffs, stale approvals and content hashes."""
        if datetime.fromisoformat(self.recorded_at.replace('Z','+00:00')).utcoffset() is None:
            raise ValueError('recorded_at must have a timezone')
        if self.campaign_id != self.snapshot.artifacts.input.request.campaign.id:
            raise ValueError('Campaign identity mismatch')
        if self.snapshot.facts != evidence_catalog(self.snapshot.artifacts):
            raise ValueError('Evidence catalog differs from authoritative artifacts')
        if self.snapshot.artifacts.extraction.status == 'ready':
            verified_campaign(self.snapshot.artifacts.extraction)
        explanation = self.snapshot.explanation
        if explanation.draft is not None and validate_explanation(
                self.snapshot.artifacts.status,self.snapshot.facts,explanation.draft):
            raise ValueError('Explanation contains unsupported claims or invalid evidence')
        if self.traceability != trace_summary(self.snapshot):
            raise ValueError('Traceability differs from authoritative artifacts')
        expected_review = 'NOT_RECORDED' if self.review_bundle is None else self.review_bundle.review_state
        if self.human_review_status != expected_review:
            raise ValueError('Human review status is unsupported by a bound review record')
        if self.review_bundle is not None and self.review_bundle.snapshot != self.snapshot:
            raise ValueError('Review record covers a different snapshot')
        if self.gaps != evidence_gaps(self.snapshot,self.review_bundle):
            raise ValueError('Missing evidence must remain explicitly reported')
        payload = self.model_dump(mode='json',exclude={'package_sha256'})
        if content_hash(canonical_json(payload)) != self.package_sha256:
            raise ValueError('Package content hash mismatch')
        return self


def evidence_gaps(snapshot: ReviewSnapshot, review: ReviewBundle | None) -> tuple[str, ...]:
    """Expose missing evidence without equating gaps with a compliance determination."""
    gaps = ['Hardware/vehicle execution not established by this package.',
            'Organizational processes and regulator/assessor review are outside this package.',
            'Independent LLM accuracy evaluation is not established by a campaign snapshot.']
    if review is None:
        gaps.append('No revision-bound human review bundle supplied; no approval inferred.')
    if snapshot.artifacts.planning is None:
        gaps.append('Planning result unavailable.')
    if snapshot.artifacts.simulation is None:
        gaps.append('Fault simulation unavailable.')
    if snapshot.artifacts.extraction.status != 'ready':
        gaps.append('Extraction handoff is blocked.')
    return tuple(gaps)


def build_package(snapshot: ReviewSnapshot, recorded_at: str, *, review: ReviewBundle | None = None,
                  references: tuple[ArtifactReference, ...] = ()) -> EngineeringPackage:
    """Export existing results reproducibly for fixed inputs, timestamp and tool environment."""
    payload = {'campaign_id':snapshot.artifacts.input.request.campaign.id,'recorded_at':recorded_at,
        'snapshot':snapshot,'review_bundle':review,
        'human_review_status':'NOT_RECORDED' if review is None else review.review_state,
        'traceability':trace_summary(snapshot),'gaps':evidence_gaps(snapshot,review),
        'tool_versions':{name:version(name) for name in ('ota-verifier','pydantic','z3-solver','langgraph')},
        'references':references,'package_sha256':'0'*64}
    # JSON mode gives the same canonical representation as final model validation.
    raw = {'format_version':'engineering-evidence-v1','scope':'SIMULATION','assertion':ASSERTION,**payload}
    raw['snapshot'] = snapshot.model_dump(mode='json')
    raw['review_bundle'] = review.model_dump(mode='json') if review else None
    raw['gaps'] = list(raw['gaps'])
    raw['references'] = [ref.model_dump(mode='json') for ref in references]
    raw['package_sha256'] = content_hash(canonical_json({k:v for k,v in raw.items() if k!='package_sha256'}))
    return EngineeringPackage.model_validate_json(canonical_json(raw))


def render_markdown(package: EngineeringPackage) -> str:
    """Render human-readable summaries without replacing complete JSON evidence."""
    trace = package.traceability
    lines = ['# Simulated engineering evidence', '', ASSERTION, '',
        f'Campaign: `{package.campaign_id}`',f'Recorded: {package.recorded_at}',
        f'Analysis status: **{trace["analysis_status"]}**',
        f'Human review: **{package.human_review_status}**',
        f'Package SHA-256: `{package.package_sha256}`','',
        f'Constraints with evidence spans: {len(trace["constraints_and_spans"])}',
        f'Observed compatibility states: {len(trace["compatibility"])}',
        f'Fault cases: {len(trace["fault_cases"])}','', '## Retained findings','']
    lines += [f'- `{code}`: {count} trace occurrence(s).' for code,count in trace['finding_occurrences'].items()]
    if not trace['finding_occurrences']:
        lines.append('No finding occurrences recorded; coverage and missing evidence must still be reviewed.')
    lines += ['', '## Evidence gaps','', *[f'- {gap}' for gap in package.gaps], '',
              'Complete source text, spans, versions, fault traces, rollback actions and LLM call provenance are in package.json.',
              'Hashes detect changed bytes; they are not digital signatures or proof of artifact origin.', '']
    return '\n'.join(lines)


def write_package(package: EngineeringPackage, output: Path) -> None:
    """Write a new package directory without overwriting historical evidence."""
    output.mkdir(parents=True,exist_ok=False)
    (output/'package.json').write_text(canonical_json(package.model_dump(mode='json'))+'\n',encoding='utf-8',newline='\n')
    (output/'report.md').write_text(render_markdown(package),encoding='utf-8',newline='\n')
    (output/'schema.json').write_text(canonical_json(EngineeringPackage.model_json_schema())+'\n',encoding='utf-8',newline='\n')
    manifest = {name:digest_file(output/name) for name in ('package.json','report.md','schema.json')}
    (output/'SHA256SUMS.json').write_text(canonical_json(manifest)+'\n',encoding='utf-8',newline='\n')


def verify_package(directory: Path) -> EngineeringPackage:
    """Verify fixed required artifacts and semantic consistency without executing LLMs."""
    manifest = json.loads((directory/'SHA256SUMS.json').read_text(encoding='utf-8'))
    if set(manifest) != {'package.json','report.md','schema.json'}:
        raise ValueError('Incomplete or unexpected package manifest')
    for name,expected in manifest.items():
        if digest_file(directory/name) != expected:
            raise ValueError(f'Artifact hash mismatch: {name}')
    package = EngineeringPackage.model_validate_json((directory/'package.json').read_text(encoding='utf-8'))
    if (directory/'report.md').read_text(encoding='utf-8') != render_markdown(package):
        raise ValueError('Human-readable report differs from package')
    if json.loads((directory/'schema.json').read_text(encoding='utf-8')) != EngineeringPackage.model_json_schema():
        raise ValueError('Export schema differs from this format implementation')
    return package


def main() -> int:
    """Export a saved snapshot/bundle or verify an existing package, entirely offline."""
    parser = argparse.ArgumentParser(description=__doc__)
    sources = parser.add_mutually_exclusive_group(required=True)
    sources.add_argument('--snapshot',type=Path)
    sources.add_argument('--bundle',type=Path)
    sources.add_argument('--verify',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--recorded-at')
    args = parser.parse_args()
    if args.verify:
        verify_package(args.verify)
        return 0
    if args.output is None or args.recorded_at is None:
        parser.error('--output and --recorded-at are required for export')
    review = ReviewBundle.model_validate_json(args.bundle.read_text(encoding='utf-8')) if args.bundle else None
    snapshot = review.snapshot if review else ReviewSnapshot.model_validate_json(args.snapshot.read_text(encoding='utf-8'))
    package = build_package(snapshot,args.recorded_at,review=review)
    write_package(package,args.output)
    verify_package(args.output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
