"""Offline corpus admission checks; never call a live provider or approve labels."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_reference_assets import check_asset
from ota_verifier.compat import check_compatibility
from ota_verifier.llm.client import FixtureClient
from ota_verifier.llm.evidence import canonical_json, evidence_error, source_segments
from ota_verifier.llm.models import DocumentRequest, ExtractionDraft, FaithfulnessVerdict
from ota_verifier.llm.pipeline import extract_and_verify, verified_campaign
from ota_verifier.llm.verifier import validate_draft
from ota_verifier.models import Campaign, FeasibleResult, InfeasibleResult
from ota_verifier.planner import plan_campaign
from ota_verifier.versions import matches, parse_spec

PACKET = ROOT / 'eval/live_extraction/real-review-v3'


def sha(path: Path) -> str:
    """Hash exact bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exclusion_campaign(receiver_current: str, receiver_target: str, tx_target: str) -> Campaign:
    """Build synthetic transition controls using the exact proposed source exclusion."""
    row = json.loads((PACKET / 'candidates.json').read_text(encoding='utf-8'))['cases'][1]
    raw = row['request_scaffold']['campaign']
    current = {'receiver': receiver_current, 'tx': '2.3.0'}
    target = {'receiver': receiver_target, 'tx': tx_target}
    for ecu in raw['ecus']:
        ecu['current_version'], ecu['target_version'] = current[ecu['id']], target[ecu['id']]
    for state in raw['initial_state']['ecus']:
        state['slot_a']['version'] = current[state['ecu_id']]
    raw['constraints'] = [row['proposed_draft']['constraints'][0]['constraint']]
    return Campaign.model_validate_json(json.dumps(raw))


def validate() -> dict[str, Any]:
    """Validate exact sources, schemas, offsets, fixture gates and actual Z3 behavior."""
    dataset = json.loads((PACKET / 'candidates.json').read_text(encoding='utf-8'))
    manifest = json.loads((PACKET / 'manifest.json').read_text())
    assert sha(PACKET / 'candidates.json') == manifest['dataset_file_sha256']
    assert hashlib.sha256(canonical_json(dataset).encode('utf-8')).hexdigest() == manifest['dataset_canonical_sha256']
    assert dataset['review_status'] == 'UNREVIEWED' and dataset['admitted_cases'] == 0
    cases = []
    for row in dataset['cases']:
        assert row['review_status'] == 'UNREVIEWED' and row['admitted'] is False
        source = PACKET / row['source_file']
        source_status = check_asset(ROOT, source, row['source_sha256'])
        if row['source_character_span'] is not None:
            start, end = row['source_character_span']
            assert source.read_text(encoding='utf-8')[start:end] == row['raw_source_excerpt']
        else:
            hashes = json.loads((PACKET / 'SHA256SUMS.json').read_text(encoding='utf-8'))
            visual_status = [check_asset(ROOT, PACKET / page,
                            hashes[next(key for key in hashes if key.replace('\\', '/') == page.replace('\\', '/'))])
                             for page in row['visual_evidence']]
            if 'UNAVAILABLE_EXTERNAL_REFERENCE' in visual_status:
                source_status = 'UNAVAILABLE_EXTERNAL_REFERENCE'
        request = DocumentRequest.model_validate_json(json.dumps(row['request_scaffold']))
        draft = ExtractionDraft.model_validate_json(json.dumps(row['proposed_draft']))
        assert request.documents[0].model_dump(mode='json') == row['ingested_document']
        assert [segment.model_dump(mode='json') for segment in source_segments(request.documents[0])] == row['segments']
        for entry in draft.constraints:
            assert evidence_error(request, entry.evidence, entry.constraint.source_text) is None
        for issue in draft.issues:
            assert evidence_error(request, issue.evidence, issue.source_text) is None
        blocked = row['expected_gate'] == 'blocked'
        assert {issue.code for issue in validate_draft(request, draft)} == ({'unsupported_requirement'} if blocked else set())
        verdict = FaithfulnessVerdict(faithful=True,
            reviewed_constraint_ids=tuple(entry.constraint.id for entry in draft.constraints),
            reviewed_document_ids=tuple(doc.id for doc in request.documents), issues=())
        responses = (draft.model_dump_json(),) if blocked else (draft.model_dump_json(), verdict.model_dump_json())
        run = extract_and_verify(request, FixtureClient(responses))
        assert run.status == ('blocked' if blocked else 'ready')
        assert all(call.origin == 'fixture' for call in run.calls)
        if not blocked:
            assert len(verified_campaign(run).constraints) == len(draft.constraints)
        cases.append({'id': row['id'], 'schema': 'PASS', 'source_hash': source_status,
                      'exact_evidence_offsets': 'PASS',
                      'expected_gate': row['expected_gate'], 'fixture_gate': run.status, 'gate_check': 'PASS',
                      'fixture_calls': len(run.calls), 'live_calls': 0, 'human_approved': False})
    assert parse_spec('!=2.4.0') == ('!=', (2, 4))
    assert not matches('2.4.0', '!=2.4.0') and not matches('2.4.0.0', '!=2.4.0')
    assert matches('3.0.1', '!=2.4.0')
    controls = []
    for version, expected in [('2.4.0', 'infeasible'), ('2.4.0.0', 'infeasible'), ('3.0.1', 'feasible')]:
        campaign = exclusion_campaign('3.1.2', '3.2.0', version)
        result = plan_campaign(campaign)
        assert result.status == expected
        if isinstance(result, InfeasibleResult):
            assert 'real-v2-02-rule' in {item.id for item in result.conflict.items}
        if isinstance(result, FeasibleResult):
            assert all(not check_compatibility(campaign, state) for state in result.plan.states)
        controls.append({'tx_target': version, 'actual_z3_status': result.status, 'result': result.model_dump(mode='json')})
    campaign = exclusion_campaign('3.2.0', '3.2.1', '2.4.0')
    result = plan_campaign(campaign)
    assert isinstance(result, FeasibleResult)
    assert [step.ecu_id for step in result.plan.steps] == ['receiver', 'tx']
    assert all(not check_compatibility(campaign, state) for state in result.plan.states)
    return {'mode': 'OFFLINE_SCHEMA_PROVENANCE_AND_FIXTURE_GATE_VALIDATION', 'new_provider_requests': 0,
            'dataset_canonical_sha256': manifest['dataset_canonical_sha256'], 'cases': cases,
            'precise_exclusion_supported': True, 'exclusion_controls': controls,
            'intermediate_state_control': {'actual_z3_status': result.status, 'activation_order': ['receiver', 'tx'],
                                           'result': result.model_dump(mode='json')},
            'limitations': ['Fixture gates are constructed contract checks, not live extraction/faithfulness accuracy',
                           'Synthetic transition controls validate implementation support, not vendor firmware behavior',
                           'No case is human approved or admitted by this command']}


if __name__ == '__main__':
    result = validate()
    # The packet's validation.json is immutable historical evidence.
    sys.stdout.write(json.dumps(result, indent=2) + '\n')
