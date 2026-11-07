# Phase 2C — final bounded Groq retest comparison v2

7 November 2026 (Asia/Calcutta). **All five approved development cases executed; four achieved their expected draft/gate outcomes. One false faithfulness rejection persists.** Eight real Groq requests returned HTTP200, without retries or provider completion failures. No further repair or evaluation was started.

## Scope, approval and immutable inputs

The owner approved one final retest, not independent automotive-domain expert validation. [Final authorization](../eval/live_extraction/real-retest-v2/approval.json) binds the same five labels and dataset as the original real-document pilot. Canonical dataset SHA256: `2800892519dddf8ccbe7291db6109a7e41acfbde1cd5ed638d2b529eb57e9004`. Dataset bytes are identical between both real-document runs; source documents, labels and original synthetic/real predictions remain unchanged.

[New frozen manifest](../eval/live_extraction/real-retest-v2/manifest.json): Groq `openai/gpt-oss-20b`, extract-v3 / verify-v3, existing JSON Object Mode and strict local validation; 4,096 maximum completion tokens; 60-second timeout; at most ten HTTP requests; no retries, connectivity probes, explanations or fallback providers. Actual serial pacing was at least90 seconds, with quota-reset waits. The new runner honors the latest authorization to stop on repeated provider/schema errors or exhausted budget, and immediately on authentication/rate-limit errors. A first other error would only allow an independent remaining case, never a retry. No errors occurred, so that changed stop rule was not exercised live.

The final runner's offline preflight found and corrected a token-reservation variable-scope defect before any live request. Mock HTTP controls then verified the ten-request path, repeated-error stop and refusal to restart. Mock/fixture checks are separate from the actual provider evidence. No production source or prompt changed during execution.

## Complete five-case comparison

| Case | Approved expectation and exact evidence span | Original real-pilot outcome | Final retest outcome | Actual Z3 result |
| --- | --- | --- | --- | --- |
| real-v2-01: Flysky NB4+ | transmitter before receiver; [0:85); ready after faithful review | Correct extraction; false verifier rejection; blocked | Correct extraction; false rejection persists; blocked | NOT_RUN |
| real-v2-02: ExpressLRS exclusion | receiver@==3.2.0 requires tx@!=2.4.0; [0:106); ready | Omitted rule, false unsupported issue; blocked | Correct exact rule and evidence; faithful:true; ready | Feasible, zero steps, makespan0ms |
| real-v2-03: ExpressLRS general major matching | Zero rules plus unsupported_requirement at [227:315); blocked | HTTP400 json_validate_failed; no usable output | Correct unsupported issue and span; blocked without verifier call | NOT_RUN, expected |
| real-v2-04: MCUboot scratch memory | Zero rules plus unsupported_requirement at [0:160); blocked | NOT_RUN | Correct unsupported issue and span; blocked without verifier call | NOT_RUN, expected |
| real-v2-05: MCUboot SMP description | Empty constraints/issues; descriptive text [0:61); ready | NOT_RUN | Empty draft; faithful:true; ready | Feasible, zero steps, makespan0ms |

Raw [outcomes](../eval/live_extraction/real-retest-v2/outcomes.json) preserve every extraction, finding, verdict, exact source input, gate and actual planner response. [Machine-readable comparison](../eval/live_extraction/real-retest-v2/comparison.json) independently recomputes saved-case scores and retains original NOT_RUN/failure records.

**Planning qualification:** all approved inventory scaffolds have current_version=target_version=1. Therefore both feasible Z3 results are no-update plans; the ExpressLRS ==3.2.0 antecedent is not triggered in that scaffold. This proves the live extraction-to-verification-to-planner handoff, not a nonempty transmitter/receiver update schedule or meaningful operational compatibility coverage. Inventory values and approved labels were not changed to manufacture a stronger demonstration.

## Measurements with explicit denominators

| Metric | Original partial real pilot | Final retest |
| --- | --- | --- |
| Scheduled / attempted / usable extraction cases | 5 / 3 / 2 | 5 / 5 / 5 |
| Semantic TP / FP / FN | 1 / 0 / 1 | 2 / 0 / 0 |
| Semantic precision | 1/1 =100% | 2/2 =100% |
| Semantic recall | 1/2 =50% | 2/2 =100% |
| Semantic F1 | 66.7% | 100% |
| Joint rule/evidence precision | 1/1 =100% | 2/2 =100% |
| Joint rule/evidence recall | 1/2 =50% | 2/2 =100% |
| Semantic case exact match on usable drafts | 1/2 | 5/5; includes three zero-rule controls |
| Complete draft exact match on attempts | 1/3 | 5/5 |
| Gate correctness on usable drafts | 0/2 | 4/5 |
| Complete expected outcome on attempts | 0/3 | 4/5 |
| Complete expected outcome across scheduled cases | 0/5; retains missing coverage | 4/5 |
| Verifier decisions correct | 0/1 | 2/3 |
| False rejection on correct reviewed drafts | 1/1 | 1/3; same Flysky failure remains |
| False acceptance on incorrect reviewed drafts | Undefined, no such drafts reviewed | Undefined, no such drafts reviewed |
| Correct unsupported abstention on usable approved unsupported cases | Undefined, no usable output | 2/2 |
| Descriptive control correct | NOT_RUN | 1/1 |
| Provider HTTP success | 3/4 | 8/8 |
| Provider JSON completion failures | One HTTP400 | Zero |
| Actual eligible planner handoffs | Zero | Two, both feasible zero-step plans |

The original raw mechanical gate agreement was1/3 because case03 blocked on HTTP failure; that was **not** a correct unsupported classification. It is not used as a successful semantic outcome here. Received extraction JSON was schema-valid in2/2 original usable responses and5/5 final responses; usable extraction response coverage changed from2/3 attempts to5/5. There were no fabricated extra formal rules in the final run (0/2 over-extraction proxy), but this does not mean the verifier was hallucination-free.

The directly comparable usable-extraction cases are01 and02: semantic recall and exact grounding improved on the omitted exclusion, while Flysky's complete outcome remained wrong. Complete outcome on this paired subset changed from0/2 to1/2. Cases04/05 add previously missing coverage; they are not improvements over measured old errors. Aggregate false-rejection fraction fell only because additional correct drafts were reviewed: the one previously observed false rejection was **not fixed**.

## Remaining false judgment

Final Flysky extraction: order-1, before=transmitter, after=receiver, exactly citing the approved source. The live verifier nevertheless wrote:

> Constraint direction does not match source text; the text indicates transmitter before receiver, but constraint states receiver before transmitter.

The saved constraint does not state the reverse direction. Its ID and coverage are valid; the failure is semantic judgment. The deterministic gate retains incorrect_constraint and verification_disagreement and blocks planning. It does not replace or override the verdict because citations are valid. This observed failure remains evidence against claiming reliable autonomous faithfulness verification. No new repair cycle was initiated.

## Completion behavior and attribution limits

The original case03 HTTP400 and error body remain intact. The retest case03 completed successfully with **975 completion tokens**, including891 reasoning tokens. This is below the old2,048 cap, so the observation does **not** prove that increasing the allowance alone fixed the old failure. Prompts, run stochasticity, token cap and pacing changed together; no causal isolation is claimed. No provider-side JSON generation failure was observed in this run, but future failures remain possible.

This is a five-case, owner-reviewed development retest on known excerpts from embedded firmware documentation, not a held-out study, independent domain review, or automotive ECU accuracy benchmark. There are only two expected positive formal rules. Do not combine these scores with the frozen synthetic pilot or call 100% semantic F1 overall system reliability. Flysky's scheduling interpretation and the narrow necessary exclusion remain the approved scope; they do not establish sufficient real-device compatibility.

## Actual requests, latency and tokens

All times below are7 November2026 IST. Full UTC timestamps, exact response-model identifiers, HTTP status, usage and allowlisted rate headers are retained in [calls.json](../eval/live_extraction/real-retest-v2/calls.json). Every returned model identifier was openai/gpt-oss-20b, every HTTP status200, and every LLM-dependent stage used the existing client with real HTTP transport. No fixture transport supplied evaluation predictions.

| Case / stage | Start IST | Latency ms | Prompt tokens | Completion tokens | Total |
| --- | --- | ---: | ---: | ---: | ---: |
| 01 extraction | 13:00:47.599697 | 2305.008 | 1970 | 477 | 2447 |
| 01 verification | 13:02:17.601727 | 1236.848 | 1157 | 648 | 1805 |
| 02 extraction | 13:03:47.604664 | 1401.066 | 2001 | 792 | 2793 |
| 02 verification | 13:05:17.606753 | 1240.457 | 1224 | 637 | 1861 |
| 03 extraction | 13:06:49.962771 | 1974.452 | 2169 | 975 | 3144 |
| 04 extraction | 13:08:19.965551 | 1350.651 | 1987 | 554 | 2541 |
| 05 extraction | 13:09:49.968045 | 1232.235 | 1949 | 195 | 2144 |
| 05 verification | 13:11:19.970301 | 822.087 | 1064 | 223 | 1287 |
| **Total** | | | **13521** | **4501** | **18022** |

Reasoning tokens totaled3906, already included in completions. Usage is available for all8 retest requests; original reported6337 covered only three successful requests, with failed-request consumption unknown. No zero-cost or billing claim follows from token usage.

Successful extraction median latency:1401.066ms (n=5); verification:1236.848ms (n=3). Original successful extraction median:1330.3005ms (n=2); verification:1374.933ms (n=1). These tiny, different-coverage samples do not establish a speed improvement. Per-call latency excludes pacing. Overall elapsed time:633.271 seconds.

The runner reserved51,978 estimated combined tokens against the63,997 estimate ceiling; actual reported usage was18,022. At most10 requests were allowed;8 were used. Fresh headers reported8,000 tokens/minute; remaining tokens ranged5076-6581 and remaining request count999 at each response under the paced schedule. Reset metadata was honored. No HTTP429, quota increase, retry or hidden provider/model fallback occurred. Character-based reservation estimates are not tokenizer-certified bounds, and the headers are historical observations rather than current quota guarantees.

## Regression and integrity

Post-run relevant regression: **274 passed, 0 failures, 0 errors, 13 warnings in 26.71 seconds**. [Exact command](../eval/live_extraction/real-retest-v2/post-run-regression-command.json) and [complete output](../eval/live_extraction/real-retest-v2/post-run-regression.log) are retained. Warnings concern LangSmith dependency uses of deprecated asyncio.iscoroutinefunction on Python3.14.4. The new comparison regression checks immutable inputs/request hashes and preserves missing original coverage without asserting that any desired accuracy must be achieved. pip check found no broken requirements. This is targeted verification, not a new full-suite claim.

Integrity checks verify the original synthetic and real pilot packages, reviewed corpus, repaired-plan package, retest runner snapshot, dataset, approvals and request hashes. Production-source hashes and prompt hashes match the pre-execution freeze. No approved source, label or prompt changed during evaluation. Local hashes demonstrate consistency, not independent attestation of provider execution. Sanitized artifact scans check configured secret values without displaying credentials.

Offline reproduction only:

```powershell
.\.venv\Scripts\python.exe eval/live_extraction/compare_retest.py
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.ota_state/final-comparison-review tests/test_retest_comparison.py tests/test_final_retest_runner.py tests/test_final_reliability_repair.py tests/test_real_pilot_metrics.py
```

Do not restart the execute command; it refuses a started run. No further inference is authorized by this report. The new files are final_retest.py, compare_retest.py, two targeted test modules, real-retest-v2 evidence and this versioned report; production modules were unchanged.

## Publication limits and stopping point

Keep the persistent false rejection prominent. The final live workflow is not fully correct even though extraction/evidence matched all five approved drafts. Two planner handoffs are no-op scaffolds; meaningful nonempty real-document campaign planning remains unmeasured. The corpus is small, known and not automotive-domain representative. README/readiness wording and final full-suite/package publication checks remain separate work; no publication, commit, push or deployment was performed here.

Historical evidence remains **26/28 smoke fault cases passed with two genuine bootability-invariant violations**, MCUboot **6 MATCH / 2 policy MISMATCH / 4 UNSUPPORTED**, and the unchanged synthetic pilot with semantic F1=100% on five rules, grounding3/5 and gates1/3. No production safety, regulatory compliance, hardware or real-vehicle validation is claimed. Stop after this comparison; no automatic repair cycle or further evaluation.
