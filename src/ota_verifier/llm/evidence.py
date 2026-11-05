"""Exact provenance, canonical hashes, and strict JSON decoding without repairs."""
import hashlib
import json
import re
from typing import Any, TypeVar
from pydantic import BaseModel
from .models import DocumentHash, DocumentRequest, EvidenceSpan, SourceDocument, SourceSegment

Model = TypeVar('Model', bound=BaseModel)


def canonical_json(value: Any) -> str:
    """Encode stable JSON with no nonfinite values or implicit string conversion."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def content_hash(value: str) -> str:
    """Hash exact UTF-8 text without changing Unicode or whitespace."""
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def request_hash(request: DocumentRequest) -> str:
    """Bind source text, inventory, environment, and authorizations to a run."""
    return content_hash(canonical_json(request.model_dump(mode='json')))


def document_hashes(request: DocumentRequest) -> tuple[DocumentHash, ...]:
    """Record one hash per source document in input order."""
    return tuple(DocumentHash(document_id=document.id, sha256=content_hash(document.text))
                 for document in request.documents)


def source_segments(document: SourceDocument) -> tuple[SourceSegment, ...]:
    """Split at newlines or sentence-ending whitespace, preserving exact offsets.

    Numeric dots are preserved (4.2). This is a citation segmentation convention,
    not a linguistic parser; abbreviations can produce separate short segments.
    """
    boundaries = list(re.finditer(r'(?<=[.!?])\s+|\n+', document.text))
    ranges = [(0 if index == 0 else boundaries[index - 1].end(), boundary.start())
              for index, boundary in enumerate(boundaries)]
    ranges.append((boundaries[-1].end() if boundaries else 0, len(document.text)))
    segments: list[SourceSegment] = []
    for start, end in ranges:
        raw = document.text[start:end]
        start += len(raw) - len(raw.lstrip())
        end -= len(raw) - len(raw.rstrip())
        if end > start:
            segments.append(SourceSegment(evidence=EvidenceSpan(document_id=document.id,
                start_char=start, end_char=end), text=document.text[start:end]))
    return tuple(segments)


def evidence_error(request: DocumentRequest, evidence: EvidenceSpan, text: str) -> str | None:
    """Reject invented, truncated, out-of-range, or incorrectly attributed quotes."""
    document = next((doc for doc in request.documents if doc.id == evidence.document_id), None)
    if document is None:
        return 'Unknown source document'
    if evidence.end_char > len(document.text):
        return 'Source span exceeds document length'
    if document.text[evidence.start_char:evidence.end_char] != text:
        return 'Source quote does not exactly match its character span'
    if not any(segment.evidence == evidence and segment.text == text for segment in source_segments(document)):
        return 'Quote must cover one full code-generated source segment'
    return None


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON object key')
        result[key] = value
    return result


def _nonfinite(value: str) -> None:
    raise ValueError('Nonfinite JSON numbers are not allowed')


def validate_json(model: type[Model], raw: str) -> Model:
    """Validate raw strict JSON, rejecting duplicate keys, fences, and NaN/Infinity."""
    parsed = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_nonfinite)
    return model.model_validate_json(canonical_json(parsed))
