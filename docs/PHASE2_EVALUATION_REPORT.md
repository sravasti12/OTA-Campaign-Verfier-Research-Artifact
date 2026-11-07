# Phase 2 consolidated engineering evaluation

**Phase 2 remains INCOMPLETE.** Updated 7 November 2026: the owner-approved five-case **REAL-DOCUMENT DEVELOPMENT PILOT** stopped after four Groq requests (three HTTP200, one HTTP400 JSON-generation failure). Three cases were attempted, two produced usable drafts, two remain NOT_RUN, and none reached Z3. Available semantic precision/recall/F1: 100%/50%/66.7%; complete expected outcomes: 0/3 attempts. Separately, the frozen **SYNTHETIC DEVELOPMENT PILOT** retains semantic F1 100% on five rules, grounding 3/5 and gates1/3. These development measurements must not be combined or described as overall automotive accuracy.

## Objectives and architecture

Evaluate parallel OTA planning cost and source-grounded LLM extraction separately. Pydantic validates inventory, constraints and exact source spans. LLMs only extract, judge faithfulness and explain. One compatibility interpretation serves deterministic Z3 planning and invariant checking; simulation/recovery are deterministic. LangGraph composes those stages and pauses for a human decision. Review/persistence and the public fixture demo are distinct from live local provider configuration.

## Evidence status

| Workstream | Status | Evidence |
| --- | --- | --- |
| Scalability execution | VERIFIED execution; PARTIALLY VERIFIED performance envelope | [Audit](PHASE2B_EVIDENCE_AUDIT.md), [methodology/results](PHASE2B_SCALABILITY.md) |
| Sequential comparison | VERIFIED for recorded synthetic inputs | 420 valid baseline schedules; paired makespans only where both methods returned valid plans |
| Groq integration | VERIFIED bounded smoke across attempts | [Complete smoke/follow-up history](PHASE2C_GROQ_SMOKE.md) |
| Synthetic accuracy pilot | EXECUTED; significant grounding/verifier/gate failures | [Pilot results and frozen approval](PHASE2C_PILOT_REPORT.md); three owner-reviewed development cases only |
| Real-document live accuracy | PARTIALLY EXECUTED; stopped on HTTP400 | [Actual pilot results](PHASE2C_REAL_DOCUMENT_PILOT.md); five owner-approved development cases, only two usable extractions |
| Full accuracy dataset run | NOT STARTED | Requires review of a bounded pilot and new authorization |

## Scalability measurements

Ten fixed-seed workload families at 10/30/50/100 ECUs produced 600 measured Z3 and 600 baseline trials, with 40 separate Z3 warm-ups. The solver budget was 10 seconds, outer watchdog 45 seconds. The API measurement includes model construction, optimization, internal replay and plan construction; generation/schema/external replay/process duration are separate. Hardware/software, actual input hashes and source snapshots are retained.

Z3 outcomes: **225 feasible, 180 infeasible, 180 unknown, 15 watchdogs**. Baseline: **420 valid, 180 no schedule**. All 180 deliberate negatives were identified as infeasible; no feasible plan was returned for the primary 100-ECU positive cases. This is not evidence of general efficient 100-ECU planning. Some solutions are feasible without proved optimality; some unsat cores are proved but not established subset-minimal within budget.

The sequential baseline shares compatibility/authorization/environment semantics, but is a greedy constructor, not a complete solver or parallel optimizer. Paired valid makespan ratios cannot substitute for successful-plan discovery rates. The 225 valid pairs exclude unresolved Z3 cases. No primary 100-ECU pair exists. See the complete [CSV](../eval/scalability/evidence/primary-summary-v1/cells.csv) and [latency](../eval/scalability/evidence/primary-summary-v1/api_latency.png), [memory](../eval/scalability/evidence/primary-summary-v1/memory.png), [outcome](../eval/scalability/evidence/primary-summary-v1/outcomes.png), [makespan](../eval/scalability/evidence/primary-summary-v1/makespan_ratios.png) charts.

Historical parent memory monitoring targeted the Windows launcher, making the advertised soft memory envelope unreliable. Worker self-peaks are preserved; killed-worker memory is unavailable. The fix and isolated real-process confirmation are not a fresh full corrected-monitor study. The host was not isolated, samples are small/repeated by seed, and negatives are deliberately local contradictions. No population-tail, vehicle-fleet or hardware claim is made.

## Live integration, source grounding and provider failures

Groq `openai/gpt-oss-20b` performed actual extraction, faithful verification and explanation on one synthetic two-ECU example. The exact requirement was `brake@>=2 requires gateway@>=2`, supported by the full source span. Strict schema/citation checks and normalized one-rule comparison passed. Z3 returned a valid 90-second simulated schedule with serialized activation order and proved makespan optimality. This is integration correctness on one case, not accuracy on unfamiliar documents.

Initial requests were denied with HTTP 403; the observed GPT-OSS denial included Cloudflare 1010. The approved truthful versioned User-Agent compatibility change was followed by HTTP 200. The original example's explanation then hit HTTP 429. A later single explanation-only retry succeeded with all 38 facts and unchanged validation, using 4,871 prompt and 423 completion tokens. Original failures remain present. For the example: **four requests, three successful inference responses, one HTTP 429**. It was not a single uninterrupted successful workflow rerun.

Source/schema validity does not prove semantic truth; valid quotes may support incorrectly directed rules. A same-model faithfulness call can correlate with extraction errors. Agreement cannot replace independently reviewed gold. Provider limits are organization-wide, and historical remaining-token headers are not current quota. Local JSON Object Mode still requires strict application validation. No automatic live retries or paid quota changes were enabled.

## Retained safety findings

The nominal simulation passed. Of 28 injected faults, **26 passed and two supported boot failures produced genuine bootability-invariant violations**. Baseline activation precedes boot-health observation; injection marks the active candidate invalid. Authorized compatible recovery restored original images, but did not erase the earlier four trace findings. The analysis remains `simulation_violations`, with no human approval. See the detailed trace/root-cause analysis in [the smoke report](PHASE2C_GROQ_SMOKE.md).

## Accuracy dataset and metrics

Twelve frozen synthetic extraction cases have ground-truth-first labels and exact spans. The owner explicitly approved three (`clear-42`, `order_conflict-44`, `unsupported-47`) for this synthetic development pilot only; the remaining nine are not approved for inference. This is not independent automotive-domain expert validation. Approval recording time was 7 November 2026 00:01:50.529649 IST. Approved canonical dataset SHA-256: `5908bf34ff185eaaa3a7000b889e4273e6f806b9619af3d71923aead4fd91c52`. Twenty real-source candidates are prepared; eighteen derive from pinned MCUboot documentation and two are short Zephyr/PX4 source candidates. **Zero are admitted schema-expressible positives.** Build/toolchain prerequisites and same-device image metadata are not automatically ECU requirements. Broad positive coverage remains missing.

The original twenty real-source proposals retain their historical unreviewed status. A separate five-case `real-review-v3` corpus was subsequently owner-approved for a bounded development evaluation; canonical SHA-256 `2800892519dddf8ccbe7291db6109a7e41acfbde1cd5ed638d2b529eb57e9004`. That approval covers two narrow embedded-radio positives, two unsupported controls and one descriptive negative; it is not independent automotive-domain expert validation. The [separate approval record](../eval/live_extraction/real-pilot-v1/approval.json) preserves the earlier packet without rewriting its pre-approval status.

The synthetic pilot used real Groq `openai/gpt-oss-20b` responses: three extractions and one verification, four HTTP200 responses, no retries, 12,170 total tokens (7,123 prompt; 5,047 completion). Those results and frozen evidence are unchanged. The subsequent real-document pilot uses separately frozen extract-v2/verify-v2 prompts and separate evidence; no production changes occurred during that evaluation.

| Synthetic development metric | Actual result |
| --- | --- |
| Semantic precision / recall / F1 | 100% / 100% / 100%; TP=5, FP=0, FN=0 |
| Semantic-only supported-case exact match | 2/2 |
| Joint rule meaning and exact gold evidence | 3/5 (60%) accuracy, precision and recall |
| Literal citation validity | 5/5 |
| Extraction schema validity | 3/3 |
| Verifier false rejection on correct reviewed drafts | 1/1 |
| Verifier false acceptance on incorrect reviewed drafts | Undefined (zero reviewed) |
| Expected gate correctness / complete case correctness | 1/3 each |
| Supported cases handed off | 0/2 |
| Correct cited unsupported abstention | 1/1 |
| Extra semantic-rule hallucination proxy | 0/5; excludes verifier inventions and misattribution |

`clear-42` extracted all three requirements correctly but the live verifier falsely demanded an unconditional brake-version requirement. Its missing_requirement issue also used `constraint_id:"c1"` where null is required; c1 exists, but is invalid for this issue type. `order_conflict-44` emitted both opposing ordering rules with swapped supporting citations and added a conflict issue, prematurely blocking deterministic handoff. The two directions still yield a perfect semantic multiset score, demonstrating why that score cannot stand for overall reliability. `unsupported-47` correctly emitted no constraints and the cited unsupported issue. All three gates blocked; **Z3 did not run in this pilot**. Both contradictions and all failure evidence are retained. See [the complete pilot report](PHASE2C_PILOT_REPORT.md) for case-level spans, timestamps, latency and outputs.

Empty denominators remain null; skipped verification is not successful verification. The small reused synthetic development set and owner-only review do not support a real-document/generalization claim. Prompts, labels and scoring were not changed after observing predictions.

## Partial real-document development results

Five approved cases were scheduled under Groq `openai/gpt-oss-20b`, at most ten requests, no retries and at least 70 seconds between starts. Four requests were actually sent. Flysky's correct grounded order was falsely rejected by the live verifier; ExpressLRS's supported narrow exclusion was incorrectly labeled unsupported by the extractor. The third case returned HTTP400 `json_validate_failed`, with provider detail "max completion tokens reached before generating a valid document". The fixed 2,048 completion-token allowance includes reasoning. The runner stopped under its declared provider-failure policy, leaving MCUboot cases04/05 NOT_RUN. No rate-limit error occurred, and no case reached Z3.

| Real-document measurement | Actual partial result |
| --- | --- |
| Coverage | 3 attempted / 5 scheduled; 2 usable extraction drafts; 2 NOT_RUN |
| Semantic TP / FP / FN | 1 / 0 / 1 |
| Semantic precision / recall / F1 | 100% / 50% / 66.7% |
| Semantic exact match | 1/2 usable drafts; 1/3 attempts |
| Joint grounding precision / recall | 1/1 (100%) / 1/2 (50%) |
| Schema validity | 2/2 received extraction drafts; usable extraction coverage 2/3 |
| Verifier correctness | 0/1; one false rejection, no incorrect drafts reviewed |
| Gate agreement on usable drafts | 0/2 |
| Mechanical blocked/ready agreement | 1/3 attempts, including a provider-error block; not a successful unsupported classification |
| Complete expected outcome | 0/3 attempts |
| Correct unsupported/descriptive classification | Not estimable; no usable approved unsupported output, descriptive case NOT_RUN |
| Provider responses | Three HTTP200, one HTTP400; no retries |
| Reported token subtotal | 6,337 across three successful requests; failed-request usage and full total unknown |

The semantic precision and zero extra-rule proxy must not hide the omitted exclusion, false verifier claim or incomplete coverage. All predictions, failures and NOT_RUN rows are retained. [Complete report](PHASE2C_REAL_DOCUMENT_PILOT.md), [raw outcomes](../eval/live_extraction/real-pilot-v1/outcomes.json), [supplementary denominator analysis](../eval/live_extraction/real-pilot-v1/analysis.json). No live accuracy improvement is established by comparison with a different synthetic dataset.

## Reproduction and integrity

From the application root, using the existing environment:

```powershell
# Rebuild review material in a NEW directory; never grants approval or calls a model.
.\.venv\Scripts\python.exe eval/prepare_review_materials.py --output eval/live_extraction/review-materials-new
# Verify the deterministic sample exporter package.
.\.venv\Scripts\python.exe -m ota_verifier.engineering_evidence --verify examples/engineering_evidence_v1
# Relevant offline regressions; choose a fresh project-local temp directory.
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.ota_state/evaluation-review-new tests/test_engineering_evidence.py tests/test_review_materials.py tests/test_llm_client.py tests/test_llm_evidence.py tests/test_llm_pipeline.py
```

Raw Phase 2B manifests retain SHA-256 indices; the consolidation audit rechecks 7,768 benchmark/analysis entries and 108 MCUboot final-package entries. MCUboot hash checking here is not fresh native execution. Live smoke packages retain separate raw outputs and hashes under ignored `runs/`; their summaries and source methodology are documented publicly. Publication needs an explicit sanitized-artifact review because ignored files are not included automatically in a Git checkout.

Final broad-suite results, dependency/secret checks and remaining operational risks are recorded in [the project readiness report](PROJECT_READINESS_REPORT.md). No expensive primary benchmark was repeated. No historical labels, fault results or native evidence were changed.

On 7 November, offline recovery verified **12/12 original pilot execution hashes**, the approved dataset/corpus, and production source hashes against the frozen manifest. [Saved-output recovery](../eval/live_extraction/recover_pilot.py) makes no provider calls. Relevant resumed regression tests: **173 passed, zero failures/errors, 13 LangSmith deprecation warnings, 28.75 seconds**; pip check found no broken requirements. This selected run does not replace the historical 760-test full-suite result. Raw pilot evidence and [recomputed metrics](../eval/live_extraction/synthetic-pilot-v1/recovery.json) remain separate from historical smoke and scalability evidence.

## Remaining work

Review the retained synthetic and partial real-document failures before any further versioned prompt/configuration changes or new inference. The five-case corpus has scoped owner approval, but its live evaluation remains incomplete after the JSON-generation failure; any new run needs an explicit request budget and reviewed completion-token configuration. For publication, reconcile README/readiness claims, retain coverage/accuracy limitations, and perform final full-suite/package checks separately. Post-run relevant checks passed **260 tests, zero failures/errors, 13 LangSmith dependency warnings in 20.28 seconds**; pip check found no broken requirements. The 14 original real-pilot execution hash entries, approved packet hashes and original synthetic recovery hashes verify; production sources and prompts match the real-pilot freeze. No commit, push or deployment occurred. Full corrected-monitor performance reruns, live OIDC and remote CI remain separate limitations. The two genuine bootability violations and MCUboot's 6 MATCH / 2 policy MISMATCH / 4 UNSUPPORTED remain unchanged. No production safety or regulatory compliance claim is made.
