"""Fail-closed extraction handoff; planning itself remains deterministic."""
import json
from ..models import Campaign
from .client import JsonClient, LLMError
from .evidence import content_hash, document_hashes, request_hash, validate_json
from .extractor import extract_constraints, extraction_prompt
from .models import CallRecord, DocumentRequest, ExtractionDraft, ExtractionRun, FaithfulnessVerdict, GateIssue
from .verifier import validate_draft, validate_verdict, verification_prompt, verify_faithfulness

MAX_DOCUMENT_CHARS = 100_000


def _campaign(request: DocumentRequest, draft: ExtractionDraft) -> Campaign:
    inventory = request.campaign
    return Campaign(id=inventory.id, ecus=inventory.ecus, initial_state=inventory.initial_state,
                    constraints=tuple(entry.constraint for entry in draft.constraints),
                    downgrade_authorizations=inventory.downgrade_authorizations)


def extract_and_verify(request: DocumentRequest, client: JsonClient,
                       verifier_client: JsonClient | None = None) -> ExtractionRun:
    """Extract, validate evidence, and independently review before exposing a campaign.

    The second client can select a different model. Using the same client still
    creates a separate call and prompt, but does not remove correlated errors.
    Unresolved review issues block progression; explicitly witnessed opposite
    orders remain in the draft for solver review. No model output is repaired.
    """
    calls: list[CallRecord] = []
    draft: ExtractionDraft | None = None
    verdict: FaithfulnessVerdict | None = None
    issues: tuple[GateIssue, ...] = ()
    campaign: Campaign | None = None
    if sum(len(document.text) for document in request.documents) > MAX_DOCUMENT_CHARS:
        issues = (GateIssue(code='input_too_large', message='Source text exceeds the explicit character limit; input was not truncated'),)
    else:
        try:
            draft, record = extract_constraints(request, client)
            calls.append(record)
            issues = validate_draft(request, draft)
            if not issues:
                verdict, record = verify_faithfulness(request, draft, verifier_client or client)
                calls.append(record)
                issues = validate_verdict(request, draft, verdict)
                if not issues:
                    campaign = _campaign(request, draft)
        except LLMError as error:
            if error.record is not None:
                calls.append(error.record)
            issues = (GateIssue(code='llm_boundary_error', message=str(error)),)
    return ExtractionRun(status='ready' if campaign is not None else 'blocked', request=request,
        input_hash=request_hash(request), document_hashes=document_hashes(request), draft=draft,
        verification=verdict, issues=issues, calls=tuple(calls), campaign=campaign)


def _record_intact(record: CallRecord) -> bool:
    if content_hash(record.request_json) != record.request_hash:
        return False
    try:
        body = json.loads(record.request_json)
        if record.provider == 'fixture':
            return body['user'] == record.user_prompt and body['system'] == record.system_prompt
        if record.provider == 'gemini':
            return (body['contents'][0]['parts'][0]['text'] == record.user_prompt
                    and body['systemInstruction']['parts'][0]['text'] == record.system_prompt)
        return body['messages'] == [{'role': 'system', 'content': record.system_prompt},
                                    {'role': 'user', 'content': record.user_prompt}]
    except (ValueError, KeyError, IndexError, TypeError):
        return False


def verified_campaign(run: ExtractionRun) -> Campaign:
    """Recheck saved run integrity, raw responses, and evidence before planning.

    Hashes detect accidental changes, not malicious forgery or model correctness.
    This is an extraction gate, not execution authorization or human approval.
    """
    if run.status != 'ready' or run.draft is None or run.verification is None or run.campaign is None:
        raise ValueError('Extraction is blocked; resolve review findings before planning')
    if run.input_hash != request_hash(run.request) or run.document_hashes != document_hashes(run.request):
        raise ValueError('Saved extraction input hashes do not match')
    if (len(run.calls) != 2 or not all(_record_intact(call) for call in run.calls)
            or run.calls[0].user_prompt != extraction_prompt(run.request)
            or run.calls[1].user_prompt != verification_prompt(run.request, run.draft)):
        raise ValueError('Saved extraction call evidence does not match this input')
    if (validate_json(ExtractionDraft, run.calls[0].response_text) != run.draft
            or validate_json(FaithfulnessVerdict, run.calls[1].response_text) != run.verification):
        raise ValueError('Saved parsed responses do not match raw model output')
    if validate_draft(run.request, run.draft) or validate_verdict(run.request, run.draft, run.verification):
        raise ValueError('Extraction has unresolved verification findings')
    campaign = _campaign(run.request, run.draft)
    if campaign != run.campaign:
        raise ValueError('Extracted campaign differs from authoritative inventory or verified draft')
    return campaign
