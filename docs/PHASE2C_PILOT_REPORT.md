# Phase 2C — synthetic development pilot

Updated 7 November 2026 (Asia/Calcutta). **SYNTHETIC DEVELOPMENT PILOT**: three owner-reviewed cases, four historical live Groq requests, all HTTP 200, no retries. This recovery made **zero new API requests**. Significant grounding, verifier and gate failures prevent a claim of reliable end-to-end extraction.

## Approval and frozen evidence

The owner personally approved `clear-42`, `order_conflict-44`, and `unsupported-47` for this pilot only. This is **not independent automotive-domain expert validation**. Approval recording time was `2026-11-06T18:31:50.529649+00:00` (7 November 00:01:50.529649 IST); this is the time chat approval was recorded, not an authenticated signature timestamp.

- [Approval](../eval/live_extraction/synthetic-pilot-v1/approval.json), [dataset](../eval/live_extraction/synthetic-pilot-v1/dataset.json), version `synthetic-development-pilot-v1`.
- Approved canonical dataset SHA-256: `5908bf34ff185eaaa3a7000b889e4273e6f806b9619af3d71923aead4fd91c52`.
- Exact dataset-file SHA-256: `b4328939472d161b39204b59a5b0bdac75d704817ecd0541c83f1a57ad20d915`.
- Original corpus canonical SHA-256: `7a8a5008b3005a870f377b0bf7ea536c51b48dfc6a9a3419ed167f770d713ff1`.
- [Pre-inference manifest](../eval/live_extraction/synthetic-pilot-v1/manifest.json) freezes scoring, settings, prompt and production-source hashes.

Labels, source evidence, predictions, prompts and production logic remain unchanged. The [previous readiness report](../eval/live_extraction/synthetic-pilot-v1/readiness-report-before-pilot.md) retains its historical blocked status; the three cases now have the limited approval above. Other synthetic cases and real-document labels are not approved for inference.

## Complete case results

| Case | Extraction and evidence | Faithfulness | Final gate versus approved expectation | Z3 |
| --- | --- | --- | --- | --- |
| clear-42 | 3/3 correct semantic rules and exact supporting spans | False rejection and invalid reference usage | Blocked; expected ready | Not run |
| order_conflict-44 | Both opposite order rules present, but citations swapped; extra conflict issue | Not called | Prematurely blocked; expected solver handoff | Not run |
| unsupported-47 | Zero rules, correct cited unsupported_requirement | Not called, as expected | Correctly blocked | Not run |

Original predictions: [clear](../eval/live_extraction/synthetic-pilot-v1/clear-42.json), [order](../eval/live_extraction/synthetic-pilot-v1/order_conflict-44.json), [unsupported](../eval/live_extraction/synthetic-pilot-v1/unsupported-47.json). Both contradictory ordering rules are preserved. **The live pilot did not reach Z3**; it cannot claim observed planner infeasibility.

## Metrics from saved predictions

| Dimension | Actual measurement | Scope |
| --- | --- | --- |
| Semantic precision / recall / F1 | 100% / 100% / 100%; TP=5, FP=0, FN=0 | Five rules across two supported cases; ignores attribution and gate |
| Semantic-only case exact match | 2/2 (100%) | Rule multisets only |
| Joint semantic rule + exact gold span | 3/5 (60%) accuracy, precision and recall | Order-rule citations support the opposite directions |
| Literal citation validity | 5/5 (100%) | Quoted text/offsets exist; does not establish semantic support |
| Extraction schema validity | 3/3 (100%) | No malformed extraction JSON |
| Verifier false rejection | 1/1 fully correct reviewed draft | Only clear-42 reached verification |
| Verifier false acceptance | Undefined; zero reviewed incorrect drafts | Skipped verifications are not successes |
| Final gate correctness | 1/3 (33.3%) | Unsupported case alone had expected gate |
| Complete expected case outcome | 1/3 (33.3%) | Combined rule/evidence/issue/gate correctness |
| Supported cases allowed through | 0/2 (0%) | Both blocked |
| Correct cited unsupported abstention | 1/1 (100%) | Wi-Fi outside current formal schema |
| Semantic over-extraction proxy | 0/5 (0%) | Excludes misattribution and verifier hallucinations |
| Real-document accuracy | Not evaluated | No real-document calls |

Semantic multiset scoring has a blind spot: swapping citations between two opposing rules preserves the aggregate set. **100% semantic F1 is not overall extraction reliability.** Likewise, the over-extraction proxy does not mean the entire workflow was hallucination-free. Full draft exactness including evidence/issues was 2/3; adding the expected gate reduces correctness to 1/3.

## Preserved failure analysis

### clear-42: false rejection and invalid reference

Correct extracted rules: brake@>=2 requires gateway@>=2 (release-42 [75:117]), gateway/brake mutual exclusion (guide-42 [79:127]), and gateway ignition off with battery at least 30% (guide-42 [128:199]).

The verifier returned faithful:false and a missing_requirement issue: **"Missing requirement that brake runs >=2."** The cited text, **"When brake runs >=2, gateway must run >=2."**, expresses a conditional antecedent, not an unconditional brake-version requirement. The extraction already represented it correctly.

The issue also supplied constraint_id:"c1". **c1 exists**, but the existing contract requires a null constraint ID for missing_requirement. Deterministic validation correctly emitted verification_reference with the generic message "Verifier issue references an invalid constraint ID". The reference is invalid for this issue type, not nonexistent. JSON/schema validity and verifier semantic/reference correctness are separate.

### order_conflict-44: swapped citations and premature conflict blocking

| Predicted rule | Attached exact source text | Span |
| --- | --- | --- |
| brake before gateway | gateway must finish flashing and activate before brake starts flashing. | release-44 [77:148] |
| gateway before brake | brake must finish flashing and activate before gateway starts flashing. | release-44 [150:221] |

Offsets and quotes are literally valid; each supports the opposite rule. The added contradictory_documents issue blocked verification/planning. The approved label instead retains both formal order constraints for deterministic infeasibility analysis. The prompt distinction between unresolved document contradictions and supported unsatisfiable formal rules merits a separately approved, versioned review. It does not change this failed outcome.

### unsupported-47: correct unsupported handling

Zero formal constraints and a cited unsupported_requirement at guide-47 [81:142] correctly preserve the unmodeled Wi-Fi demand. This was a successful abstention and gate result, not a successful verifier call.

## Provider execution, usage and latency

Existing Groq adapter, model **openai/gpt-oss-20b**, JSON Object Mode with strict application validation, temperature 0, maximum output 2,048 tokens, 45-second timeout. The [executed runner snapshot](../eval/live_extraction/synthetic-pilot-v1/runner.py) called real http_transport and retained live-origin provider responses. No fixture fallback. Three extraction requests and one verification request; no explanation requests. Four of six permitted requests used; zero retries or provider errors.

All request starts below are 7 November 2026 IST (UTC+05:30). Full UTC timestamps, allowlisted rate-limit headers, response model and raw structured responses are in [calls.json](../eval/live_extraction/synthetic-pilot-v1/calls.json).

| Case / stage | Start IST | HTTP | Latency ms | Prompt | Completion | Total tokens |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| clear / extraction | 00:03:36.961935 | 200 | 3335.475 | 1978 | 1917 | 3895 |
| clear / verification | 00:04:46.965951 | 200 | 2141.561 | 1333 | 1298 | 2631 |
| order / extraction | 00:05:56.970928 | 200 | 2252.914 | 1931 | 1352 | 3283 |
| unsupported / extraction | 00:07:06.975223 | 200 | 1238.874 | 1881 | 480 | 2361 |
| **Total** | | **4 responses** | | **7123** | **5047** | **12170** |

Reasoning tokens total 4,436, already included in completion tokens. Extraction median latency: 2,252.914 ms (n=3); verifier n=1. Starts were paced approximately 70 seconds apart; total experiment elapsed 211.356 seconds. The original pacing_wait_ms field measures start-to-start interval, not isolated sleep; it is preserved but not treated as exact sleep latency. Per-call latency_ms excludes pacing. No population-tail claim is justified.

Historical HTTP 403/429 failures remain in [the smoke report](PHASE2C_GROQ_SMOKE.md); none occurred in this pilot. Recorded remaining-token headers are historical, not current quota. Token totals do not establish zero billing cost.

## Recovery, integrity and checks

[Offline recovery results](../eval/live_extraction/synthetic-pilot-v1/recovery.json) verify **12/12 original execution-manifest hashes**, the approved dataset, original corpus and production-source hashes. The recovery recalculates metrics from typed saved predictions without invoking inference, planning, simulation or a new evaluation. Original calls, predictions, summary and execution manifest are preserved. [analysis.json](../eval/live_extraction/synthetic-pilot-v1/analysis.json) separates interpretation from original metrics. Hashes show local consistency, not independent attestation.

From the project root in PowerShell:

```powershell
# Offline only. Do not run pilot.py execute again.
.\.venv\Scripts\python.exe eval/live_extraction/recover_pilot.py
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.ota_state/pilot-resume-new tests/test_live_pilot_metrics.py tests/test_benchmark.py tests/test_extraction_evaluation.py tests/test_llm_client.py tests/test_llm_evidence.py tests/test_llm_pipeline.py tests/test_graph.py tests/test_plan_validation.py
.\.venv\Scripts\python.exe -m pip check
```

Actual resumed regression results: **173 passed, 0 failures, 0 errors, 13 warnings in 28.75 seconds**. LangSmith warnings concern deprecated asyncio.iscoroutinefunction under Python 3.14.4. pip check: **No broken requirements found.** The selected suite does not replace the historical 760-test full-suite result. An initial offline recovery-script attempt failed strict Python-object parsing of JSON lists; JSON-mode parsing corrected this, then recovery passed. No evidence or production logic was changed.

## Limitations and remaining-work checklist

Tiny synthetic development sample, reused existing cases, owner-only review, one model/run and one verifier judgment: no held-out or real-world accuracy claim. Production source hashes match the pre-inference manifest, covering planner, simulator, integrations and workflows; no demo production changes were made.

1. Review false rejection, citation reversal and premature blocking. Any prompt/production correction requires separate approval and a new version; retain this failed baseline and frozen gold.
2. Review [the real-document packet](../eval/live_extraction/review-materials-v1/REAL_DOCUMENT_REVIEW.md) and [candidate data](../eval/live_extraction/review-materials-v1/real-candidates.json). Twenty proposed excerpts (18 pinned MCUboot, two short Zephyr/PX4 candidates) contain **zero admitted schema-expressible positive ECU cases**. Source genuine explicit ECU constraints; do not transform tool prerequisites or same-device image metadata into invented ECU dependencies. Labels remain unapproved.
3. Only after separate corpus and bounded-request approval, run a real-document pilot. No new evaluation began here. Keep real/synthetic scores separate.
4. For publication, reconcile README/readiness claims, then run the complete offline suite, dependency/credential scan and package-wide hash verification. If real-document evaluation cannot be completed today, publish it as an explicit outstanding limitation rather than claim completion.

Retained historical evidence: **26/28 smoke fault cases passed, with two genuine bootability-invariant violations**; MCUboot differential results remain **6 MATCH, 2 intentional policy MISMATCH, 4 UNSUPPORTED**. No hardware, real-vehicle, full MCUboot equivalence, regulatory compliance or safety-certification claim is made. No commit, push or deployment.
