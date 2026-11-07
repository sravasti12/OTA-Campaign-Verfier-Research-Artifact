"""Prepare a versioned, unapproved corpus revision from existing local evidence."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from ota_verifier.llm.evidence import canonical_json, source_segments
from ota_verifier.llm.models import SourceDocument

PARENT = ROOT / 'eval/live_extraction/real-review-v2'
OUTPUT = ROOT / 'eval/live_extraction/real-review-v3'


def sha(path: Path) -> str:
    """Hash exact file bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare() -> dict[str, Any]:
    """Revise context and provenance without modifying labels in the parent packet."""
    if (OUTPUT / 'candidates.json').exists():
        raise FileExistsError('Create another revision instead of overwriting this packet')
    old = json.loads((PARENT / 'candidates.json').read_text(encoding='utf-8'))
    index = json.loads((PARENT / 'SHA256SUMS.json').read_text())
    assert all(sha(PARENT / name) == digest for name, digest in index.items())
    rows = old['cases']  # JSON-loaded copies only; no parent file is written.
    (OUTPUT / 'sources').mkdir(parents=True, exist_ok=True)
    for source in (PARENT / 'sources').iterdir():
        if source.is_file():
            (OUTPUT / 'sources' / source.name).write_bytes(source.read_bytes())
    full = (OUTPUT / 'sources/expresslrs-firmware-version.md').read_text(encoding='utf-8')
    row = rows[2]
    old_issue = row['proposed_draft']['issues'][0]
    end = full.index(row['raw_source_excerpt']) + len(row['raw_source_excerpt'])
    start = full.index('A Version is defined or formatted as "Major.Minor.Patch"')
    text = full[start:end]
    document = SourceDocument(id=row['id'], text=text)
    segments = source_segments(document)
    requirement = next(segment for segment in segments if segment.text == old_issue['source_text'])
    row.update({'raw_source_excerpt': text, 'source_character_span': [start, end],
                'ingested_document': document.model_dump(mode='json'),
                'segments': [segment.model_dump(mode='json') for segment in segments],
                'ambiguities': 'The version-format definition and major/minor/patch explanations are now included in the input. '
                              'General equality between two variable major versions is not expressible by one fixed-constant version comparison. '
                              'Do not enumerate unstated versions. Shares the same source as real-v2-02; not independent coverage.'})
    row['request_scaffold']['documents'] = [document.model_dump(mode='json')]
    old_issue['evidence'] = requirement.evidence.model_dump(mode='json')
    old_issue['message'] = 'Matching the variable major-version components of two nodes is outside the fixed-constant comparison schema.'
    rows[0]['transcription'] = 'Visually verified by assistant against locally rendered exact saved PDF pages 7 and 67; not human label approval'
    rows[0]['automated_checks']['source_substring'] = 'PDF_VISUALLY_VERIFIED_ASSISTANT'
    rows[0]['visual_evidence'] = ['rendered-pages/flysky-page-7.png', 'rendered-pages/flysky-page-67.png']
    rows[0]['ambiguities'] = ('NB4+ model and FGr4B receiver verified on PDF page7; section7.16 and explicit order statement verified on '
        'PDF page67 / printed p62. One physical newline becomes one space. Interpreting update-before as completion/activation '
        'before the next flash starts is a conservative scheduling interpretation requiring owner approval. '
        'The manual does not explicitly use activation terminology or provide firmware versions/durations. Public manufacturer documentation, not open-source firmware.')
    for row in rows:
        row['recommendation'] = 'ADMIT'
        row['recommendation_meaning'] = 'Assistant recommendation only; not an admission or human approval'
        assert row['review_status'] == 'UNREVIEWED' and row['admitted'] is False
        assert sha(OUTPUT / row['source_file']) == row['source_sha256']
    dataset = {'format': 'real-review-v3', 'review_status': 'UNREVIEWED', 'admitted_cases': 0,
               'live_requests': 0, 'proposed_positive_cases': 2, 'cases': rows}
    encoded = json.dumps(dataset, indent=2, ensure_ascii=False)
    (OUTPUT / 'candidates.json').write_text(encoded, encoding='utf-8')
    provenance = json.loads((PARENT / 'provenance.json').read_text())
    provenance['revision_recorded_at_utc'] = datetime.now(timezone.utc).isoformat()
    provenance['flysky']['text_verification'] = 'ASSISTANT_VISUAL_VERIFICATION of actual local PDF rasterization; no human label approval'
    provenance['flysky']['visual_pages'] = {'7': 'NB4+ transmitter and FGr4B receiver identity, printed p2',
                                          '67': 'NB4+ header, section7.16, exact order note, printed p62'}
    provenance['flysky']['renderer'] = 'Built-in Windows.Data.Pdf API; render_flysky.ps1; no dependency installation'
    provenance['flysky']['failed_methods'] = ['WSL rendering tools absent', 'web PDF access failed', 'initial WinRT AsTask overload error corrected before successful rendering']
    provenance['flysky']['unresolved_transcription_uncertainty'] = None
    provenance['flysky']['human_interpretation_approval'] = False
    provenance['revision_changes'] = ['Flysky visual evidence and transcription verification',
                                      'ExpressLRS case03 extended by exact adjacent version-format definition; recalculated offsets',
                                      'All labels remain UNREVIEWED and all original IDs retained for lineage']
    (OUTPUT / 'provenance.json').write_text(json.dumps(provenance, indent=2), encoding='utf-8')
    manifest = {'dataset_version': 'real-review-v3', 'parent_dataset_file_sha256': sha(PARENT / 'candidates.json'),
                'parent_package_hash_entries_verified': len(index),
                'dataset_canonical_sha256': hashlib.sha256(canonical_json(dataset).encode('utf-8')).hexdigest(),
                'dataset_file_sha256': sha(OUTPUT / 'candidates.json'), 'human_approval': False,
                'live_inference_requests': 0, 'original_ids_retained': True}
    (OUTPUT / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest


if __name__ == '__main__':
    sys.stdout.write(json.dumps(prepare(), indent=2) + '\n')
