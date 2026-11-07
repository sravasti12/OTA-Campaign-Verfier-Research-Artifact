# Phase 2C — final offline reliability repair

7 November 2026 (Asia/Calcutta). **Offline repairs complete; no live accuracy improvement demonstrated.** No Groq inference, connectivity probe, rerun, label change or historical evidence rewrite occurred. The existing real pilot remains incomplete: four requests, three HTTP200 and one HTTP400; two usable extractions, two NOT_RUN cases, no case reached Z3.

## Root-cause findings

| Failure | Evidence-based cause | Minimal correction | Remaining status |
| --- | --- | --- | --- |
| Flysky false faithfulness rejection | Correct transmitter-before-receiver extraction and exact citation; live verifier falsely claimed direction mismatch. Its order-1 reference and coverage were valid. No schema or ID-validator failure caused this case. | verify-v3 clarifies endpoint direction and asks for the actual wrong field/source meaning. Generic source wording recognition now covers unqualified update-before sentences. A matching-source order rejected by the verifier gets verification_disagreement diagnostics. | Saved rejection still blocks. No override, citation-only approval or proof of live correction. |
| ExpressLRS narrow exclusion labeled unsupported | Existing schema/parser/validator/Z3 already support !=. Model failed to represent the approved fixed-version exclusion. extract-v2 did not explicitly distinguish pair exclusions from general variable-version matching. | extract-v3 and verify-v3 describe necessary fixed-pair exclusions generically, without product names, concrete corpus versions or gold answers. General matching between variable components stays unsupported. | Saved zero-rule unsupported prediction remains blocked and unchanged. Future interpretation remains model-dependent. |
| HTTP400 json_validate_failed | Saved provider body says maximum completion tokens reached before valid JSON. The evaluation runner explicitly overrode the configured limit to 2,048. Current environment-derived limit is 8,192 for extraction and verification; timeout60s, JSON mode, Groq/openai/gpt-oss-20b. No HTTP429 or context-limit failure was observed. Failed request supplied no usage. | Prepare a finite 4,096-completion-token/60-second continuation profile using the existing adapter. Test wire serialization and one-attempt failure propagation offline. No adapter, .env, provider switch, schema mode or reasoning setting change. | Supported configuration/headroom, not a guarantee of valid live JSON. Original HTTP400 remains intact; no retry performed. |

The older synthetic missing_requirement/non-null-ID error and nonexistent-ID checks remain enforced. A valid ID is necessary but not sufficient for a faithful judgment. An unresolved rejection, wrong quote, unknown ID, genuine unsupported issue or source-direction mismatch still blocks planning.

## Production changes

- `src/ota_verifier/llm/extractor.py`: extract-v3 instructions for narrowly scoped necessary fixed-pair exclusions, no guessed minima or flash ordering, and distinct unsupported variable-component matching.
- `src/ota_verifier/llm/verifier.py`: verify-v3 instructions and non-authorizing verification_disagreement diagnostics. Original findings are retained. Known-ID, issue-type/reference, evidence and coverage checks remain fail-closed.
- `src/ota_verifier/llm/source_support.py`: bounded generic recognition of optional Note: followed by You must update the X firmware before updating the Y firmware. Full-string matching excludes qualified/negated/unknown wording. No device-specific parser or universal entailment claim.

No planner, compatibility, simulator, invariants, LangGraph, Streamlit, model schema or provider adapter behavior changed. The generic update-before check verifies direction only; it does not prove activation semantics or every other part of a requirement. Its disagreement diagnostic requests review and never creates an accepted campaign. Prompt clarification is a hypothesis requiring a new live evaluation.

## Offline regression and deterministic replay

`tests/test_final_reliability_repair.py` replays the actual saved Flysky and ExpressLRS responses with explicit FixtureClient transports. Flysky retains its original draft/verdict and blocks with both the original incorrect_constraint issue and new disagreement diagnostic. ExpressLRS retains zero constraints and the original unsupported issue; nothing synthesizes a replacement answer.

Additional controls reject a genuinely reversed update order before verification, unknown verifier IDs, invented finding text, conditional update statements and unrecognized wording. Generic alpha/beta endpoints verify that the recognizer is not tied to corpus device names. Existing admitted-case tests retain supported != parsing/Z3 behavior and blocked general-major matching.

The HTTP400 test reads the exact saved error body, then injects a failing mocked transport into the existing LLMClient at the proposed 4,096 cap. It still raises an error after exactly one call. A separate mocked-success transport verifies that 4,096 serializes as max_completion_tokens with JSON Object Mode and no provider fallback. **Mocked HTTP tests and fixture replays are not real-provider evidence.** They establish local wire/control behavior only; they do not demonstrate that extra tokens would have fixed the historical request.

Relevant regression result: **271 passed, 0 failures, 0 errors, 13 warnings in 32.49 seconds**. The warnings are LangSmith dependency uses of deprecated asyncio.iscoroutinefunction on Python3.14.4. [Exact command](../eval/live_extraction/reliability-repair-v1/regression-command.json) and [complete output](../eval/live_extraction/reliability-repair-v1/regression.log) are retained. `pip check`: No broken requirements found. Previous broad-suite and live-pilot counts remain separate historical results.

Other files created: `eval/live_extraction/continuation_plan.py` (offline bounded profile/budget builder), `tests/test_final_reliability_repair.py` (saved-response and mocked-error regression tests), this report, and `eval/live_extraction/reliability-repair-v1/` (plan, regression output and integrity metadata). No .env changes or dependency installations.

## Bounded continuation proposal — not execution approval

[Machine-readable plan](../eval/live_extraction/reliability-repair-v1/continuation-plan.json), generated by `eval/live_extraction/continuation_plan.py`. The command performs offline budgeting only and exposes no live-execution action.

| Control | Proposed value |
| --- | --- |
| Dataset | Same five approved cases, canonical SHA256 2800892519dddf8ccbe7291db6109a7e41acfbde1cd5ed638d2b529eb57e9004 |
| Provider/model | Groq / openai/gpt-oss-20b |
| Prompts | New extract-v3 / verify-v3; new run identity required |
| Output format | Existing JSON Object Mode with strict local schema/source/reference validation |
| Completion hard cap | 4,096 per request; includes reasoning and visible output |
| Timeout / wall budget | 60 seconds per request / 1,200 seconds overall |
| Expected requests | 8: five extractions, three eligible verifications |
| Maximum new live requests | **10**, two per case at most; no connectivity or explanation request |
| Maximum generated tokens | **40,960** across ten calls; excludes input tokens |
| Rough nominal input+output estimate | **51,985**, including maximum completions |
| Rough worst-case input+output estimate | **63,997**, including maximum completions |
| Largest estimated single reservation | **7,639**, including a 512-token margin |
| Serial pacing | At least90 seconds between starts; honor longer provider resets |
| Retries / fallback | Zero automatic retries; no provider/model fallback |
| Failure policy | Stop on first provider/schema failure, retain NOT_RUN cases |

Prompt-token estimates use characters/3 and gold-shaped verifier drafts; they are **not tokenizer-certified bounds or predicted actual consumption**. Recalculate reservations against each actual outgoing verification draft. Do not truncate critical source/evidence to fit a budget. Fresh quota is unknown. If the observed per-request limit cannot cover the reservation, or remaining budget/reset metadata is inadequate, wait within the wall budget or stop. No paid-quota change is authorized.

The old real_pilot.py runner and its frozen snapshot retain their historical 2,048-token protocol. **Do not execute that runner as the new profile.** A separately versioned future runner must consume the new plan, freeze prompts/configuration/source hashes, bind the existing corpus approval, and obtain explicit new request/configuration approval before sending anything. This is a five-case development retest of known cases, not an independent or held-out study, and must not be merged into the original pilot results.

Groq's [official model documentation](https://console.groq.com/docs/model/openai/gpt-oss-20b) lists JSON Object Mode and a 65,536-token output ceiling; 4,096 is within that capability. The [API reference](https://console.groq.com/docs/api-reference) documents max_completion_tokens. These capabilities do not override organization-specific rate quotas or prove a particular request will complete. The proposed profile uses the existing adapter and leaves reasoning effort at the provider default; no new reasoning configuration is introduced.

## Reproduction and readiness

```powershell
# Offline planning only; no API request.
.\.venv\Scripts\python.exe eval/live_extraction/continuation_plan.py
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.ota_state/final-repair-review-new tests/test_final_reliability_repair.py tests/test_pilot_reliability.py tests/test_real_review_v3.py tests/test_real_review_v2.py tests/test_llm_pipeline.py tests/test_llm_evidence.py tests/test_llm_client.py
.\.venv\Scripts\python.exe -m pip check
```

Ready for a **separately approved bounded retest**, subject to current quota checks. Not ready to claim that false rejection, unsupported misclassification or completion exhaustion is fixed in live inference. Citation correctness is not semantic proof; a same-model verifier can still make correlated mistakes; a larger finite completion cap can still fail. The remaining two controls were never executed live in the old run.

Original approval/labels, raw predictions, source evidence and HTTP400 logs remain unchanged. Original real-pilot, synthetic-pilot and reviewed-corpus package hashes are verified separately from new repair artifacts. No independent automotive-domain expert validation, automotive accuracy, production safety, hardware validation or regulatory compliance is claimed. Historical two bootability violations and MCUboot mismatches/unsupported cases remain untouched. No commit, push or deployment.
