"""Evidence-export integrity contracts; no live inference or changed safety criteria."""
import json
from pathlib import Path
from typing import Any

import pytest

from ota_verifier.engineering_evidence import EngineeringPackage, build_package, verify_package, write_package
from ota_verifier.graph import WorkflowService
from ota_verifier.llm.evidence import canonical_json, content_hash
from ota_verifier.workflow_examples import example_input, fixture_dependencies
from ota_verifier.workflow_models import ReviewBundle, WorkflowInput


@pytest.fixture(scope='module')
def bundle() -> ReviewBundle:
    """Exercise an actual offline fixture workflow with authorized original-image recovery."""
    request,case = example_input('authorized_rollback')
    return WorkflowService().start(WorkflowInput(request=request),fixture_dependencies(case),run_id='export-test')


def reseal(raw: dict[str, Any]) -> str:
    """Rehash mutated content to test semantic checks independently of byte-integrity checks."""
    raw['package_sha256'] = content_hash(canonical_json({k:v for k,v in raw.items() if k!='package_sha256'}))
    return canonical_json(raw)


def test_deterministic_export_retains_findings_and_bound_review(bundle: ReviewBundle, tmp_path: Path) -> None:
    """Same inputs produce identical files and preserve all baseline fault findings."""
    package = build_package(bundle.snapshot,'2026-11-06T00:00:00Z',review=bundle)
    assert package.human_review_status == 'awaiting_review'
    assert package.traceability['finding_occurrences']['invalid_active_image'] > 0
    assert package.snapshot == bundle.snapshot
    assert len(package.traceability['constraints_and_spans']) == 3
    for name in ('first','second'):
        write_package(package,tmp_path/name)
        assert verify_package(tmp_path/name) == package
    assert (tmp_path/'first/package.json').read_bytes() == (tmp_path/'second/package.json').read_bytes()
    with pytest.raises(FileExistsError):
        write_package(package,tmp_path/'first')


@pytest.mark.parametrize('mutation',['finding','review','gap','span','claim','scope','hash'])
def test_tampered_or_unsupported_claims_rejected_even_if_rehashed(bundle: ReviewBundle, mutation: str) -> None:
    """Resealing cannot hide altered findings, missing evidence, fabricated approval or claims."""
    raw = build_package(bundle.snapshot,'2026-11-06T00:00:00Z').model_dump(mode='json')
    if mutation == 'finding':
        raw['traceability']['finding_occurrences'] = {}
    elif mutation == 'review':
        raw['human_review_status'] = 'approved'
    elif mutation == 'gap':
        raw['gaps'] = []
    elif mutation == 'span':
        raw['traceability']['constraints_and_spans'][0]['evidence']['end_char'] += 1
    elif mutation == 'claim':
        raw['assertion'] = 'Certified compliant'
    elif mutation == 'scope':
        raw['scope'] = 'HARDWARE_VALIDATED'
    else:
        raw['recorded_at'] = '2026-11-07T00:00:00Z'
        with pytest.raises(ValueError,match='hash'):
            EngineeringPackage.model_validate_json(canonical_json(raw))
        return
    with pytest.raises(ValueError):
        EngineeringPackage.model_validate_json(reseal(raw))


def test_missing_planning_simulation_are_explicit_gaps() -> None:
    """A blocked extraction can be exported honestly without fabricated downstream coverage."""
    request,case = example_input('unsupported')
    snapshot = WorkflowService().start(WorkflowInput(request=request),fixture_dependencies(case)).snapshot
    package = build_package(snapshot,'2026-11-06T00:00:00+00:00')
    assert package.traceability['compatibility'] == []
    assert 'Planning result unavailable.' in package.gaps
    assert 'Fault simulation unavailable.' in package.gaps
    assert package.human_review_status == 'NOT_RECORDED'


def test_modified_artifact_and_missing_manifest_entry_rejected(bundle: ReviewBundle, tmp_path: Path) -> None:
    """A modified document or an incomplete hash index cannot verify."""
    package = build_package(bundle.snapshot,'2026-11-06T00:00:00Z')
    write_package(package,tmp_path/'changed')
    (tmp_path/'changed/report.md').write_text('changed',encoding='utf-8')
    with pytest.raises(ValueError,match='hash'):
        verify_package(tmp_path/'changed')
    write_package(package,tmp_path/'missing')
    (tmp_path/'missing/SHA256SUMS.json').write_text(json.dumps({}),encoding='utf-8')
    with pytest.raises(ValueError,match='manifest'):
        verify_package(tmp_path/'missing')


def test_false_live_explanation_claim_rejected(bundle: ReviewBundle) -> None:
    """Do not accept unsupported assurance prose even when enclosing hashes are recomputed."""
    raw = build_package(bundle.snapshot,'2026-11-06T00:00:00Z').model_dump(mode='json')
    raw['snapshot']['explanation']['draft']['statements'][0]['text'] = 'Certified compliant'
    with pytest.raises(ValueError,match='unsupported claims'):
        EngineeringPackage.model_validate_json(reseal(raw))
