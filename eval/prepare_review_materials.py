"""Offline review packets from frozen synthetic labels and pinned public source material."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator

from ota_verifier.benchmark.corpus import corpus_hash, load_corpus
from ota_verifier.llm.evidence import source_segments
from ota_verifier.llm.models import SourceDocument
from ota_verifier.llm.verifier import validate_draft, validate_verdict

ROOT = Path(__file__).resolve().parents[1]
PIN = '6d3b3d2c38ab20c242e5b9abb04d050086383eb2'
UPSTREAM = ROOT/'.mcuboot-reference/upstream'


class Candidate(BaseModel):
    """Unreviewed excerpts are not executable cases until inventory/mapping and gold are approved."""
    model_config = ConfigDict(extra='forbid')
    id: str
    origin: Literal['real_document'] = 'real_document'
    review_status: Literal['PROPOSED_UNREVIEWED'] = 'PROPOSED_UNREVIEWED'
    project: str
    url: str
    revision: str | None
    publication_date: str | None = None
    retrieved_at: str
    license_note: str
    source_path: str | None
    source_sha256: str | None
    excerpt: str
    excerpt_sha256: str
    source_start_char: int | None
    source_end_char: int | None
    context: str
    classification: str
    proposed_constraints: list[Any]
    proposed_label_reason: str
    evidence_segments: list[dict[str,Any]]
    inventory_mapping: Literal['UNRESOLVED_NOT_AN_EXECUTABLE_CASE'] = 'UNRESOLVED_NOT_AN_EXECUTABLE_CASE'
    admission_blockers: list[str]

    @model_validator(mode='after')
    def intact_excerpt(self) -> 'Candidate':
        """Reject altered text, invalid segments and unsupported synthetic origins."""
        if hashlib.sha256(self.excerpt.encode()).hexdigest() != self.excerpt_sha256:
            raise ValueError('Excerpt hash mismatch')
        expected = [s.model_dump(mode='json') for s in source_segments(SourceDocument(id=self.id,text=self.excerpt))]
        if expected != self.evidence_segments:
            raise ValueError('Evidence segments differ from exact ingested text')
        return self


def upstream_bytes(path: str) -> bytes:
    """Read an actual committed source blob, never a mutable working-tree approximation."""
    return subprocess.run(['git','show',f'{PIN}:{path}'],cwd=UPSTREAM,capture_output=True,check=True).stdout


def paragraph(text: str, marker: str) -> tuple[int,int]:
    """Select the full contiguous paragraph containing a literal source marker."""
    at = text.index(marker)
    start = text.rfind('\n\n',0,at)+2 if '\n\n' in text[:at] else 0
    end = text.find('\n\n',at)
    return start,len(text) if end == -1 else end


def synthetic_review(output: Path) -> None:
    """Expose all twelve unchanged cases and pending human sign-off with automated checks."""
    corpus = load_corpus()
    lines = ['# Synthetic label review — human approval pending','',
             'All cases are synthetic; no live accuracy scores are asserted. Frozen labels are unchanged.',
             f'Canonical corpus SHA-256: `{corpus_hash(corpus)}`','']
    checks = []
    for split,cases in (('development',corpus.development),('heldout',corpus.heldout)):
        for case in cases:
            draft = validate_draft(case.request,case.reference_draft)
            verdict = validate_verdict(case.request,case.reference_draft,case.reference_verdict)
            checks.append({'id':case.id,'split':split,'human_review':'PENDING',
                           'draft_gate_codes':[i.code for i in draft],'verdict_gate_codes':[i.code for i in verdict]})
            lines += [f'## {case.id} ({split})','', '**Review status: PENDING — automated checks are not human approval.**','',
                      f'Expected blocked: `{case.expected_blocked}`. Strict case schema loaded successfully.','']
            for doc in case.request.documents:
                lines += [f'Document `{doc.id}` — exact text:','', '```text',doc.text,'```','']
            lines += ['Expected extracted constraints and exact supporting spans:','', '```json',
                      json.dumps([e.model_dump(mode='json') for e in case.reference_draft.constraints],indent=2),'```','',
                      'Expected issues:','', '```json',json.dumps([i.model_dump(mode='json') for i in case.reference_draft.issues],indent=2),'```','',
                      f'Automated draft gate codes: `{[i.code for i in draft]}`; verdict codes: `{[i.code for i in verdict]}`.','']
            note = ('Hidden intended order is not source-supported and must NOT become an extraction FN; review only the cited ambiguity/abstention.'
                    if case.scenario=='ambiguous' else 'Wi-Fi is outside ignition/battery preconditions; do not invent supported conditions.'
                    if case.scenario=='unsupported' else 'Retain both explicit rules even if the planner later proves a conflict.'
                    if case.scenario in ('order_conflict','intermediate_trap') else 'Check operator direction, numeric versions and complete source context; do not infer extra order.')
            lines += [f'Potential labeling/interpretation risks: {note}','',
                      '- [ ] Inventory and named-component mapping reviewed against the frozen JSON.',
                      '- [ ] Every rule/operator/type and exact Unicode span checked.',
                      '- [ ] Ambiguity/unsupported assumptions and acceptable gate outcome adjudicated.',
                      '- [ ] No prior model output used to redefine this label.','']
    (output/'SYNTHETIC_REVIEW.md').write_text('\n'.join(lines),encoding='utf-8')
    (output/'synthetic-checks.json').write_text(json.dumps({'corpus_sha256':corpus_hash(corpus),'cases':checks},indent=2),encoding='utf-8')
    template = {'format':'human-label-signoff-v1','corpus_sha256':corpus_hash(corpus),
        'status':'PENDING','reviewer':None,'reviewed_at':None,'independent_review_limitations':None,
        'scope':'synthetic development pilot only; heldout cases require separate admission',
        'case_reviews':[{'id':case.id,'approved':False,'reviewer':None,'date':None,'adjudication':None}
                        for case in corpus.development],
        'methodology_approved':False,'request_budget_approved':False}
    (output/'review-signoff.template.json').write_text(json.dumps(template,indent=2),encoding='utf-8')


def real_candidates(output: Path) -> None:
    """Create twenty traceable candidate excerpts without inventing ECU-version mappings."""
    selections = [
        ('docs/imgtool.md','The `--slot-size` argument is required','flash-layout'),
        ('docs/imgtool.md','A dependency can be specified','image-minimum-version'),
        ('docs/readme-zephyr.md','Currently, the two image slots must be contiguous','flash-layout'),
        ('docs/readme-zephyr.md','These images can also be marked for upgrade','confirmation-order'),
        ('docs/design.md','Please note that the swap-using-scratch algorithm','ambiguous-future-guidance'),
        ('docs/design.md','When swap-using-scratch algorithm is used','scratch-capacity'),
        ('docs/design.md','For new swaps, MCUboot must inspect','bootloader-state-machine'),
        ('docs/design.md','Image must contain a SHA256 TLV.','image-integrity'),
        ('docs/design.md','Downgrade prevention is a feature','security-policy'),
        ('docs/design.md','During the software based downgrade prevention','conditional-build-feature'),
        ('docs/design.md','Each signed image can contain a security counter','security-counter'),
        ('docs/design.md','The dependencies between images can be described','multi-image-dependency'),
        ('docs/PORTING.md','requires a configuration file','build-prerequisite'),
        ('docs/PORTING.md','requires that the target provides','hardware-api-prerequisite'),
        ('docs/PORTING.md',"doesn't bundle a cryptographic library",'crypto-build-dependency'),
        ('docs/readme-espressif.md','Current compatible ESP-IDF version','toolchain-version'),
        ('docs/serial_recovery.md','MCUboot implements a Simple Management Protocol','no-supported-requirement'),
        ('docs/encrypted_images.md','It does not protect against the possibility','threat-model-limitation')]
    rows = []
    retrieved = datetime.now(timezone.utc).isoformat()
    for index,(path,marker,kind) in enumerate(selections,1):
        raw = upstream_bytes(path);text = raw.decode('utf-8')
        start,end = paragraph(text,marker);excerpt = text[start:end]
        identifier = f'real-candidate-{index:02}'
        reason = ('Image dependency metadata has no approved independently updatable ECU mapping; do not split one device into invented ECUs.'
                  if 'dependency' in kind or kind=='image-minimum-version' else
                  'Build, image-format, flash, security or application-health semantics are outside requires/mutex/order/ignition-and-battery constraints.'
                  if kind!='no-supported-requirement' else 'Descriptive implementation statement does not establish any supported campaign requirement.')
        rows.append(Candidate(id=identifier,project='MCUboot',url=f'https://github.com/mcu-tools/mcuboot/blob/{PIN}/{path}',
            revision=PIN,retrieved_at=retrieved,license_note='Apache-2.0; upstream LICENSE/NOTICE retained with this candidate packet.',
            source_path=path,source_sha256=hashlib.sha256(raw).hexdigest(),excerpt=excerpt,
            excerpt_sha256=hashlib.sha256(excerpt.encode()).hexdigest(),source_start_char=start,source_end_char=end,
            context=text[max(0,start-220):min(len(text),end+220)],classification=kind,proposed_constraints=[],proposed_label_reason=reason,
            evidence_segments=[s.model_dump(mode='json') for s in source_segments(SourceDocument(id=identifier,text=excerpt))],
            admission_blockers=['Independent human semantic review missing','No approved source-component/ECU inventory mapping']))
    external = [
        ('Zephyr','https://docs.zephyrproject.org/latest/services/device_mgmt/dfu.html',None,
         'You need to build and flash MCUboot itself on your device','build-prerequisite'),
        ('PX4','https://docs.px4.io/v1.18/en/advanced_config/bootloader_update','v1.18 documentation URL; immutable commit unresolved',
         'The PX4 Bootloader is used to load firmware for Pixhawk boards (PX4FMU, PX4IO).','no-supported-requirement')]
    for index,(project,url,revision,excerpt,kind) in enumerate(external,19):
        identifier = f'real-candidate-{index:02}'
        rows.append(Candidate(id=identifier,project=project,url=url,revision=revision,retrieved_at=retrieved,
            license_note='Short attributed quotation; full source/license and immutable revision must be reviewed before admission.',
            source_path=None,source_sha256=None,excerpt=excerpt,excerpt_sha256=hashlib.sha256(excerpt.encode()).hexdigest(),
            source_start_char=None,source_end_char=None,context='See linked DFU/bootloader documentation; no independently updatable ECU inventory supplied.',
            classification=kind,proposed_constraints=[],proposed_label_reason='No supported installed ECU-version requirement follows from this statement.',
            evidence_segments=[s.model_dump(mode='json') for s in source_segments(SourceDocument(id=identifier,text=excerpt))],
            admission_blockers=['Independent human review missing','Immutable source/context/license capture incomplete','No approved ECU mapping']))
    payload = {'format':'real-document-candidates-v1','status':'PROPOSED_UNREVIEWED_NOT_ADMITTED',
        'candidate_count':len(rows),'expressible_positive_cases':0,'live_inference_requests':0,
        'coverage_gaps':['No approved ECU-version positive','No genuine conflicting ECU requirements found','Project diversity limited; 18 MCUboot excerpts and 2 short external candidates'],
        'cases':[r.model_dump(mode='json') for r in rows]}
    (output/'real-candidates.json').write_text(json.dumps(payload,indent=2),encoding='utf-8')
    (output/'candidate.schema.json').write_text(json.dumps(Candidate.model_json_schema(),indent=2),encoding='utf-8')
    for filename in ('LICENSE','NOTICE'):
        (output/f'MCUBOOT_{filename}').write_bytes(upstream_bytes(filename))
    lines = ['# Real-document candidate review','', '**PROPOSED / UNREVIEWED. No inference or human approval.**','',
        '20 candidates; zero admitted schema-expressible positives. Most are unsupported/negative controls.',
        'Version minima concern tools or same-device image metadata; no ECU mappings are invented.',
        'Conflicting campaign requirements and broad positive coverage remain missing.','']
    for row in rows:
        lines += [f'## {row.id}: {row.project} / {row.classification}','',f'[Source]({row.url})',
                  f'Revision: {row.revision or "UNPINNED"}; publication date unknown; retrieved {row.retrieved_at}.','',
                  '```text',row.excerpt,'```','', 'Proposed formal constraints: **none**. '+row.proposed_label_reason,'',
                  'Exact ingested evidence segments:','```json',json.dumps(row.evidence_segments,indent=2),'```','',
                  'Admission blockers: '+ '; '.join(row.admission_blockers),
                  '- [ ] Source context, license and revision reviewed.', '- [ ] Mapping and unsupported/negative label reviewed.',
                  '- [ ] Reviewer/date/adjudication recorded; approval remains pending.','']
    (output/'REAL_DOCUMENT_REVIEW.md').write_text('\n'.join(lines),encoding='utf-8')


def main() -> int:
    """Generate new review materials without changing old labels or making model calls."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    synthetic_review(args.output)
    real_candidates(args.output)
    manifest = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in args.output.iterdir() if p.is_file()}
    (args.output/'SHA256SUMS.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
