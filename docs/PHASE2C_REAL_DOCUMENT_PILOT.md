# Phase 2C — real-document Groq development pilot

7 November 2026 (Asia/Calcutta). **INCOMPLETE: stopped on provider JSON-generation failure.** Five cases were approved and scheduled; three were attempted, two produced usable extraction JSON, and two remain NOT_RUN. Four real Groq requests were sent: three HTTP 200 and one HTTP 400. No retries, fixture fallback, explanation calls, label changes or production changes occurred.

## Approval, provenance and execution freeze

The project owner explicitly approved the five cases and expected outcomes for a bounded real-document development evaluation. [Approval](../eval/live_extraction/real-pilot-v1/approval.json) was recorded at `2026-11-07T07:04:36.544230+00:00` (12:34:36.544230 IST). This records a chat instruction, not an authenticated signature timestamp or independent automotive-domain expert validation.

Approved dataset: `real-review-v3`, canonical SHA-256 `2800892519dddf8ccbe7291db6109a7e41acfbde1cd5ed638d2b529eb57e9004`. [The pre-inference manifest](../eval/live_extraction/real-pilot-v1/manifest.json) binds the exact dataset bytes, approval, production-source hashes, prompts, scoring and request controls. The historical admission packet remains unchanged with its original pre-approval status; the separate approval record adds the later scoped authorization. [Source/evidence packet](../eval/live_extraction/real-review-v3/REVIEW.md).

Provider/model: **Groq / openai/gpt-oss-20b**. Existing `LLMClient` and real `http_transport` were used with the existing truthful User-Agent. Frozen prompt versions: extract-v2 / verify-v2, JSON Object Mode plus strict application validation. Both roles were checked against private environment configuration; .env remained Git-ignored and untracked. No credentials were printed or stored in request headers.

Runtime controls: at most 10 HTTP requests, no automatic retries, serial starts at least 70 seconds apart, 45-second request timeout, 1,200-second experiment wall budget, **2,048 maximum completion tokens per request**. The completion allowance includes model reasoning. Expected nominal path: 8 requests; worst-case ceiling: 10. Pre-inference character-based estimate at that ceiling was 40,873 total tokens, maximum single-request reservation 4,799. These were scheduling estimates, not tokenizer measurements or billing guarantees.

Fresh response headers reported 8,000 tokens/minute and 1,000 request limit, with remaining request counts 999, 998, 997, 996. Remaining token values were 5,995; 6,507; 5,549; 5,825. Token reset metadata was honored along with the conservative serial pacing. There was **no HTTP 429 or quota exhaustion observed**. First-response quota was unknown before the first request; historical headers were not treated as current entitlement.

## Every scheduled case

| Case | Approved expectation | Actual extraction | Verification / gate | Z3 |
| --- | --- | --- | --- | --- |
| real-v2-01, Flysky order | transmitter before receiver; ready | Correct order and exact [0:85) support; no draft issue | Live verifier falsely claimed direction mismatch; blocked | NOT_RUN |
| real-v2-02, ExpressLRS exclusion | receiver@==3.2.0 requires tx@!=2.4.0; ready | Zero constraints; incorrectly classified as unsupported_requirement at [0:106) | Verifier skipped; blocked | NOT_RUN |
| real-v2-03, ExpressLRS major relation | Zero constraints and cited unsupported_requirement at [227:315); blocked | HTTP400; no usable draft | Blocked on provider failure, not successful unsupported classification | NOT_RUN |
| real-v2-04, MCUboot scratch memory | Zero constraints and unsupported_requirement; blocked | NOT_RUN after stop condition | Not evaluated | NOT_RUN |
| real-v2-05, MCUboot SMP description | Zero constraints, zero issues; ready | NOT_RUN after stop condition | Not evaluated | NOT_RUN |

Actual saved predictions and source inputs: [case01](../eval/live_extraction/real-pilot-v1/real-v2-01.json), [case02](../eval/live_extraction/real-pilot-v1/real-v2-02.json), [case03](../eval/live_extraction/real-pilot-v1/real-v2-03.json), [all outcomes including NOT_RUN](../eval/live_extraction/real-pilot-v1/outcomes.json). All attempted-case gates blocked; no verified campaign reached the planner. Offline admission controls had demonstrated that the precise != exclusion is supported, but those controls are not substituted for live extraction or a live-pilot plan.

## Preserved failure evidence

**Flysky false faithfulness rejection:** extraction produced order-1 with `before:transmitter`, `after:receiver` and the exact approved sentence. The real verifier returned faithful:false, kind incorrect_constraint, existing constraint_id order-1, and message **"Constraint direction does not match source text."** That finding contradicts the owner-approved label. Coverage/reference validation passed; this is a semantic false rejection, not an invalid-ID failure. The gate correctly honored the rejection rather than repairing or overriding it.

**ExpressLRS false unsupported abstention:** the extractor returned no constraints and the issue message **"Requirement about sync/bind between specific ECU versions cannot be represented in current schema"**. The approved narrow exclusion is expressible and previously checked through schema, parser, validation and Z3. Therefore this is an extraction omission/wrong unsupported classification against frozen gold, not proof of an implementation limitation. The finding is exactly cited but semantically wrong under the approved scope.

**Provider JSON-generation failure:** case03 returned HTTP400, error type invalid_request_error, code **json_validate_failed**. The provider's failed_generation field states **"max completion tokens reached before generating a valid document"**. No partial valid structured output or token usage was supplied. The chosen 2,048-completion-token allowance was exhausted before a valid response; this is not demonstrated to be a context-window, rate-limit, authentication or billing error. The model may have consumed reasoning tokens, but their count is unknown for this request. The runner stopped under its predeclared stop-on-failure policy. It did not increase limits, alter prompts, retry case03 or spend the remaining six-request allowance.

## Measurements and denominators

These are **partial real-document development measurements**, separate from the synthetic pilot. They are not automotive ECU accuracy or generalization estimates.

| Measurement | Actual result |
| --- | --- |
| Coverage | 3/5 cases attempted; 2 usable extraction drafts; 2 NOT_RUN |
| Semantic constraint counts | TP=1, FP=0, FN=1; both expected positive rules were attempted |
| Semantic precision / recall / F1 | 100% / 50% / 66.7% |
| Semantic case exact match | 1/2 usable extraction cases; 1/3 attempted cases |
| Joint rule-to-evidence grounding | Precision 1/1 (100%); recall 1/2 (50%) |
| Literal citation validity | 1/1 emitted constraint |
| Extraction JSON/schema validity | 2/2 received usable extraction JSON; valid-response coverage 2/3 attempted extraction requests |
| Complete draft exact match | 1/3 attempted cases |
| Live faithfulness correctness | 0/1 reviewed draft; false rejection 1/1 correct reviewed draft |
| Verifier false acceptance | Undefined: no incorrect draft was reviewed |
| Gate agreement on usable extraction cases | 0/2 |
| Mechanical ready/blocked agreement on all attempts | 1/3; includes case03 blocking on HTTP failure, which is not a validated semantic pass |
| Complete expected case outcome | 0/3 attempted cases; zero successful complete cases among five scheduled |
| False unsupported abstention on usable positive cases | 1/2 |
| Correct unsupported classification | Not estimable: zero approved unsupported cases produced usable output |
| Descriptive-versus-unsupported discrimination | NOT EVALUATED; descriptive case NOT_RUN |
| Extra-semantic-rule hallucination proxy | 0/1 emitted constraint; does not capture the false verifier claim or omission |
| Provider HTTP success | 3/4 (75%); one retained HTTP400 failure |
| Eligible verified cases reaching Z3 | 0 |

The original [execution summary](../eval/live_extraction/real-pilot-v1/summary.json) is preserved. Its raw gate_correctness=1/3 measures only ready/blocked agreement. [Supplementary recovery analysis](../eval/live_extraction/real-pilot-v1/analysis.json) explicitly prevents that provider-error block from being described as a correct unsupported classification. Empty denominators remain null, not perfect scores. Failed and NOT_RUN cases are retained; no five-case accuracy is extrapolated from two usable drafts.

## Request evidence, latency and usage

Times are 7 November 2026 IST. [calls.json](../eval/live_extraction/real-pilot-v1/calls.json) retains UTC timestamps, actual HTTP status, live-origin records, request hashes, raw structured responses, sanitized error body and allowlisted rate headers. The transport was the real existing Groq endpoint, not a fixture or mocked HTTP transport.

| Case / role | Start IST | HTTP | Latency ms | Prompt tokens | Completion tokens | Total |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| 01 extraction | 12:36:02.201646 | 200 | 1296.955 | 1813 | 464 | 2277 |
| 01 verification | 12:37:12.204832 | 200 | 1374.933 | 1029 | 607 | 1636 |
| 02 extraction | 12:38:22.207697 | 200 | 1363.646 | 1844 | 580 | 2424 |
| 03 extraction | 12:39:32.210650 | 400 | 2832.575 | Unknown | Unknown | Unknown |
| **Reported subtotal** | | | | **4686** | **1651** | **6337** |

**6,337 tokens cover only the three usage-reported successful requests. Total consumption/billing across all four requests is unknown.** Reasoning tokens on successful requests totaled 1,364, already included in completion tokens. Per-call latency excludes quota waits; case03 latency is failure latency, not successful inference latency. Overall elapsed time was 212.907 seconds. Tiny sample sizes do not support tail-latency claims.

## Regression, integrity and reproduction

Post-run relevant regression suite: **260 passed, 0 failures, 0 errors, 13 warnings in 20.28 seconds**. Warnings concern LangSmith dependency uses of deprecated asyncio.iscoroutinefunction under Python3.14.4. pip check: **No broken requirements found.** [Exact command](../eval/live_extraction/real-pilot-v1/post-run-regression-command.json), [complete output](../eval/live_extraction/real-pilot-v1/post-run-regression.log). These are selected checks, not a replacement full-suite claim.

All **14 original execution hash entries** verify. The approved source packet's 16 hashes and frozen synthetic pilot recovery package's 20 hashes remain intact. All production-source hashes match the pre-inference freeze; extraction/verification prompts and labels were unchanged throughout. Final integrity/credential-scan metadata and additive package hashes are saved alongside the evidence. Hashes establish local consistency, not independent attestation of provider execution.

Offline recovery only, with no API requests:

```powershell
.\.venv\Scripts\python.exe eval/live_extraction/analyze_real_pilot.py
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.ota_state/real-pilot-report-check tests/test_real_pilot_metrics.py tests/test_real_review_v3.py tests/test_pilot_reliability.py tests/test_llm_pipeline.py tests/test_llm_client.py
```

**Do not rerun the execute command:** the runner refuses an already-started directory. Any resumed/live experiment requires a separately approved new run/version with an explicit request budget and treatment of the token allowance. The executed runner snapshot, original calls and outcomes remain unchanged. Added offline recovery code only recomputes stored predictions; it does not invoke the pipeline or provider again.

## Remaining publication blockers

1. Review the false faithfulness rejection and false unsupported abstention. No live reliability improvement has been established.
2. Review why the fixed completion allowance failed, and design a separately authorized bounded run. Raising allowance would change the evaluation configuration and token reservations; do not silently retry this baseline.
3. Complete the unobserved unsupported/descriptive controls only with new authorization. The approved five-case evaluation is incomplete.
4. Broaden provenance-reviewed evidence beyond two embedded projects and tiny development excerpts before making broader accuracy claims. Owner approval is not independent domain-expert validation. Synthetic inventory values are scaffolding, not vendor versions/durations or vehicle data.
5. Reconcile README/readiness claims with these results and perform final full-suite/package/publication checks separately. Retain previous **26/28 fault-case passes and two genuine bootability-invariant violations**, and MCUboot **6 MATCH / 2 policy MISMATCH / 4 UNSUPPORTED**.

No automotive ECU accuracy, hardware/real-vehicle validation, production safety or regulatory compliance is claimed. The original synthetic pilot remains unchanged: semantic F1 100% on five rules, grounding 3/5, gates1/3, four requests and 12,170 reported tokens. Do not combine synthetic and real-document scores. Nothing was committed, pushed or deployed.
