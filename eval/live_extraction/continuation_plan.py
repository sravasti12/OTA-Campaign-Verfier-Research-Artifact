"""Offline-only continuation budgeting; no execution or provider connectivity command."""
from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src')]
from ota_verifier.llm.client import ClientSettings
from ota_verifier.llm.evidence import canonical_json, content_hash
from ota_verifier.llm.extractor import SYSTEM_PROMPT as EXTRACT, PROMPT_VERSION as EXTRACT_VERSION, extraction_prompt
from ota_verifier.llm.verifier import SYSTEM_PROMPT as VERIFY, PROMPT_VERSION as VERIFY_VERSION, verification_prompt
from ota_verifier.llm.models import DocumentRequest, ExtractionDraft, FaithfulnessVerdict, Purpose

OUTPUT = ROOT / 'eval/live_extraction/reliability-repair-v1'


def proposed_settings(purpose: Purpose) -> ClientSettings:
    """Build a bounded future profile without editing .env or making requests."""
    settings = ClientSettings.from_env(purpose)
    if settings.provider != 'groq' or settings.model != 'openai/gpt-oss-20b' or settings.schema_mode != 'json':
        raise ValueError('Continuation requires reviewed Groq/model/JSON-mode configuration')
    return settings.model_copy(update={'max_tokens': 4096, 'timeout_seconds': 60.0})


def budget() -> dict[str, Any]:
    """Estimate five cases at current prompts; preserve estimates versus hard limits."""
    data = json.loads((ROOT / 'eval/live_extraction/real-review-v3/candidates.json').read_text(encoding='utf-8'))
    digest = content_hash(canonical_json(data))
    assert digest == '2800892519dddf8ccbe7291db6109a7e41acfbde1cd5ed638d2b529eb57e9004'
    rows = []
    for case in data['cases']:
        request = DocumentRequest.model_validate_json(canonical_json(case['request_scaffold']))
        draft = ExtractionDraft.model_validate_json(canonical_json(case['proposed_draft']))
        for purpose, system, user, schema in (
            ('extraction', EXTRACT, extraction_prompt(request), ExtractionDraft.model_json_schema()),
            ('verification', VERIFY, verification_prompt(request, draft), FaithfulnessVerdict.model_json_schema())):
            chars = len(system + '\nReturn only JSON matching this schema:\n' + canonical_json(schema) + user)
            # A conservative character heuristic, not a tokenizer-certified bound.
            prompt_estimate = (chars + 2) // 3
            rows.append({'case_id': case['id'], 'purpose': purpose, 'prompt_characters': chars,
                         'prompt_token_estimate': prompt_estimate, 'completion_hard_cap': 4096,
                         'estimated_reservation_with_512_token_margin': prompt_estimate + 4096 + 512,
                         'nominal_call': purpose == 'extraction' or case['expected_gate'] != 'blocked'})
    configured = {role: ClientSettings.from_env(role) for role in ('extraction', 'verification')}
    profile = {role: proposed_settings(role) for role in configured}
    return {'status': 'OFFLINE_PREPARATION_ONLY_NOT_AUTHORIZED_TO_EXECUTE', 'new_api_requests': 0,
            'dataset_canonical_sha256': digest, 'case_ids': [case['id'] for case in data['cases']],
            'prompt_versions': {'extraction': EXTRACT_VERSION, 'verification': VERIFY_VERSION},
            'prompt_hashes': {'extraction': content_hash(EXTRACT), 'verification': content_hash(VERIFY)},
            'currently_configured': {role: {'provider': s.provider, 'model': s.model, 'max_tokens': s.max_tokens,
                                           'timeout_seconds': s.timeout_seconds, 'schema_mode': s.schema_mode} for role, s in configured.items()},
            'proposed_profile': {role: {'provider': s.provider, 'model': s.model, 'max_completion_tokens': s.max_tokens,
                                        'timeout_seconds': s.timeout_seconds, 'schema_mode': s.schema_mode} for role, s in profile.items()},
            'nominal_requests': sum(row['nominal_call'] for row in rows), 'maximum_live_requests': 10,
            'maximum_generated_tokens_all_calls': 40960, 'automatic_retries': 0, 'explanation_requests': 0,
            'rough_nominal_tokens_including_completion_caps': sum(row['prompt_token_estimate'] + 4096 for row in rows if row['nominal_call']),
            'rough_worst_case_tokens_including_completion_caps': sum(row['prompt_token_estimate'] + 4096 for row in rows),
            'minimum_start_interval_seconds': 90, 'wall_budget_seconds': 1200,
            'historical_tpm_not_current_quota': 8000, 'per_role_estimates': rows,
            'max_estimated_single_request_reservation': max(row['estimated_reservation_with_512_token_margin'] for row in rows),
            'limits': ['Actual current quota unknown; do not call a models/connectivity endpoint just to probe it',
                       'Re-estimate every actual request including a changed model draft before verification; do not truncate evidence',
                       'Wait for observed reset when remaining quota cannot cover next reservation; abort if limit is too small or metadata insufficient',
                       'Stop on first provider/schema failure; retain pending cases and do not retry',
                       'No permission to execute is granted by this file; require explicit new budget/configuration approval',
                       'Old real_pilot.py is historical 2048-token protocol; do not reuse its execute command for this profile',
                       'A separately versioned future runner must consume this profile and freeze its own evidence; never mutate the old run',
                       '4096 is finite and supported by existing adapter; live completion success not established',
                       'Model default reasoning remains unchanged; no new provider or reasoning-effort option added']}


if __name__ == '__main__':
    OUTPUT.mkdir(parents=True, exist_ok=True)
    result = budget()
    (OUTPUT / 'continuation-plan.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    sys.stdout.write(json.dumps({key: result[key] for key in ('nominal_requests', 'maximum_live_requests',
        'rough_nominal_tokens_including_completion_caps', 'rough_worst_case_tokens_including_completion_caps',
        'max_estimated_single_request_reservation', 'new_api_requests')}, indent=2) + '\n')
