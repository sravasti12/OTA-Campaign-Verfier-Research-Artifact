"""Build five UNREVIEWED real-document candidates from pinned local sources only."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src')]
from ota_verifier.llm.evidence import evidence_error, source_segments
from ota_verifier.llm.models import DocumentRequest, ExtractionDraft, SourceDocument

PACKET = ROOT / 'eval/live_extraction/real-review-v2'
SOURCES = PACKET / 'sources'


def sha(path: Path) -> str:
    """Hash the exact stored source bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_cases() -> list[dict[str, Any]]:
    """Create proposals without inference, adjudication, or inferred firmware metadata."""
    revision = json.loads((SOURCES / 'expresslrs-revision.json').read_text())['commit']
    elrs = (SOURCES / 'expresslrs-firmware-version.md').read_text(encoding='utf-8')
    flysky_quote = 'Note: You must update the transmitter firmware before\nupdating the receiver firmware.'
    flysky = flysky_quote.replace('\n', ' ')
    pair = 'a Receiver with version string of 3.2.0 will NOT sync or bind with a TX Module with firmware version 2.4.0'
    major = 'That first number in the Version string should match between a TX Module and a Receiver.'
    assert pair in elrs and major in elrs
    mcuboot_revision = '6d3b3d2c38ab20c242e5b9abb04d050086383eb2'
    design = (SOURCES / 'mcuboot-design.md').read_text(encoding='utf-8')
    serial = (SOURCES / 'mcuboot-serial_recovery.md').read_text(encoding='utf-8')
    scratch = 'When swap-using-scratch algorithm is used, in addition to the slots of\nimage areas, the bootloader requires a scratch area to allow for reliable\nimage swapping.'
    descriptive = 'MCUboot implements a Simple Management Protocol (SMP) server.'
    assert scratch in design and descriptive in serial
    definitions = [
        ('real-v2-01', 'Flysky NB4+ update order', flysky, flysky_quote,
         'https://www.flysky-cn.com/s/Noble-NB4-User-manual-20231219-EN.pdf',
         'Manual filename 20231219; NB4+; section 7.16, printed p62, PDF page67 (1-based)',
         'flysky-nb4-manual.pdf', ('transmitter', 'receiver'),
         {'type': 'order', 'before': 'transmitter', 'after': 'receiver'}, None,
         'Public manufacturer documentation, not open-source firmware. Map transmitter to NB4+ and receiver to FGr4B. '
         'Complete update before the next update starts is a conservative interpretation of before; no download-only interpretation is used. '
         'Firmware versions/durations are not stated; do not invent them as source requirements. PDF soft-wrap is joined explicitly for ingestion.'),
        ('real-v2-02', 'ExpressLRS explicit incompatible pair', pair, pair,
         f'https://github.com/ExpressLRS/Docs/blob/{revision}/docs/quick-start/receivers/firmware-version.md',
         revision, 'expresslrs-firmware-version.md', ('receiver', 'tx'),
         {'type': 'requires', 'ecu': 'receiver', 'version_spec': '==3.2.0', 'needs': 'tx', 'needs_version_spec': '!=2.4.0'}, None,
         'Receiver and TX Module are separate embedded radio nodes, not automotive ECUs. '
         'This encodes ONLY the stated incompatible pair, not sufficient conditions for binding or every major-version combination. '
         'The negated-pair translation requires human approval; do not extrapolate a >=3 rule or create a flash order. '
         'The source bullet has no terminal period; the exact text is retained.'),
        ('real-v2-03', 'ExpressLRS major-version relation outside schema', major, major,
         f'https://github.com/ExpressLRS/Docs/blob/{revision}/docs/quick-start/receivers/firmware-version.md',
         revision, 'expresslrs-firmware-version.md', ('receiver', 'tx'), None, 'unsupported_requirement',
         'The surrounding pinned document defines the first number as the major version. '
         'The schema supports one comparison against a constant, not equality of two variable major components. '
         'Do not fabricate numeric thresholds or expand to unlisted versions. The excerpt and positive pair share one source: not independent samples.'),
        ('real-v2-04', 'MCUboot scratch-memory requirement', scratch.replace('\n', ' '), scratch,
         f'https://github.com/mcu-tools/mcuboot/blob/{mcuboot_revision}/docs/design.md',
         mcuboot_revision, 'mcuboot-design.md', ('bootloader',), None, 'unsupported_requirement',
         'Memory-layout prerequisite is outside requires/mutex/order/ignition+battery. '
         'Bootloader is an inventory placeholder on one device, not a new cross-ECU peer. '
         'Source newline wraps are joined for ingestion; original text is retained.'),
        ('real-v2-05', 'MCUboot descriptive negative control', descriptive, descriptive,
         f'https://github.com/mcu-tools/mcuboot/blob/{mcuboot_revision}/docs/serial_recovery.md',
         mcuboot_revision, 'mcuboot-serial_recovery.md', ('bootloader',), None, None,
         'Descriptive capability, not a requirement. Empty constraints AND empty issues expected; ready means extraction handoff only. '
         'Does not validate a complete real campaign, hardware or a real update schedule.'),
    ]
    rows = []
    for identifier, title, text, raw, url, version, source_file, ids, rule, issue_kind, ambiguity in definitions:
        document = SourceDocument(id=identifier, text=text)
        segments = source_segments(document)
        assert len(segments) == 1
        evidence = segments[0].evidence.model_dump(mode='json')
        constraint = dict(rule, id=identifier + '-rule', source_document_id=identifier, source_text=text) if rule else None
        draft_data = {'constraints': [{'constraint': constraint, 'evidence': evidence}] if constraint else [],
                      'issues': [{'kind': issue_kind, 'evidence': evidence, 'source_text': text,
                                  'message': ambiguity}] if issue_kind else []}
        draft = ExtractionDraft.model_validate_json(json.dumps(draft_data))
        # Explicitly synthetic inventory scaffolding, never asserted as vendor firmware data.
        campaign = {'id': identifier, 'ecus': [{'id': name, 'current_version': '1', 'target_version': '1', 'flash_minutes': 1.0} for name in ids],
                    'initial_state': {'ecus': [{'ecu_id': name, 'slot_a': {'version': '1', 'valid': True}, 'slot_b': None, 'active_slot': 'A'} for name in ids],
                                      'battery_percent': 100.0, 'ignition': 'off'}, 'constraints': [], 'downgrade_authorizations': []}
        request = DocumentRequest.model_validate_json(json.dumps({'campaign': campaign, 'documents': [document.model_dump(mode='json')]}))
        for entry in draft.constraints:
            assert evidence_error(request, entry.evidence, entry.constraint.source_text) is None
        for issue in draft.issues:
            assert evidence_error(request, issue.evidence, issue.source_text) is None
        full = {'expresslrs-firmware-version.md': elrs, 'mcuboot-design.md': design,
                'mcuboot-serial_recovery.md': serial}.get(source_file)
        offset = full.index(raw) if full is not None else None
        rows.append({'id': identifier, 'title': title, 'review_status': 'UNREVIEWED', 'admitted': False,
                     'source_url': url, 'version': version, 'source_file': 'sources/' + source_file,
                     'source_sha256': sha(SOURCES / source_file), 'raw_source_excerpt': raw,
                     'source_character_span': [offset, offset + len(raw)] if offset is not None else None,
                     'transcription': 'Flysky PDF page67 text transcription from official PDF parser; layout wrap retained above, joined below' if full is None else 'Exact substring of pinned UTF-8 source',
                     'ingestion_transform': 'Join explicit newline wraps with one space' if raw != text else 'None',
                     'ingested_document': document.model_dump(mode='json'), 'segments': [segment.model_dump(mode='json') for segment in segments],
                     'proposed_draft': draft.model_dump(mode='json'), 'expected_gate': 'blocked' if issue_kind else 'ready_after_faithfulness',
                     'ambiguities': ambiguity, 'inventory_roles': list(ids), 'request_scaffold': request.model_dump(mode='json'),
                     'inventory_note': 'All numeric inventory values (version 1, one minute, battery 100%, ignition off) are synthetic schema scaffolding, not vendor facts. Extraction-only proposal; no real planning/simulation conclusions.',
                     'automated_checks': {'schema': 'PASS', 'exact_ingested_segments': 'PASS', 'source_substring': 'PASS' if full else 'PDF_TRANSCRIPTION_REQUIRES_HUMAN_VISUAL_REVIEW'}})
    return rows


def main() -> None:
    """Write a new proposed packet without overwriting an existing review artifact."""
    target = PACKET / 'candidates.json'
    if target.exists():
        raise FileExistsError('Do not overwrite review material; use a new version')
    rows = build_cases()
    target.write_text(json.dumps({'format': 'real-review-v2', 'review_status': 'UNREVIEWED',
        'created_at_utc': datetime.now(timezone.utc).isoformat(), 'live_requests': 0,
        'proposed_positive_cases': 2, 'admitted_cases': 0, 'cases': rows}, indent=2), encoding='utf-8')
    lines = ['# Five real-document proposals — UNREVIEWED', '',
             'No labels are approved; no inference was run. These are embedded firmware examples, not automotive validation.', '',
             'Two proposed schema-expressible positives, two unsupported controls, one descriptive negative. Positive labels and ECU mappings require explicit human review.', '',
             'Character spans refer to the exact ingested document, not PDF bytes or the whole web page. Raw excerpts and source-file hashes are in candidates.json. PDF/newline transformations are explicit. Synthetic inventory scaffolding is never vendor evidence.', '']
    for row in rows:
        lines.extend([f"## {row['id']}: {row['title']}", '', '**UNREVIEWED / NOT ADMITTED**', '',
                      f"[Source]({row['source_url']}) — version: `{row['version']}`", '',
                      'Exact raw excerpt:', '', '```text', row['raw_source_excerpt'], '```', '',
                      'Proposed structured output (offsets in ingested text):', '', '```json',
                      json.dumps(row['proposed_draft'], indent=2), '```', '',
                      f"Expected gate: **{row['expected_gate']}**", '', f"Ambiguities: {row['ambiguities']}", '',
                      f"Ingestion: {row['ingestion_transform']}. Source character span: {row['source_character_span']}.", '',
                      f"Automated checks: {row['automated_checks']}", ''])
    (PACKET / 'REVIEW.md').write_text('\n'.join(lines), encoding='utf-8')


if __name__ == '__main__':
    main()
