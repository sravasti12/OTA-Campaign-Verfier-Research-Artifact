# Scalability and live LLM evaluation plan

Audit date: 2026-11-06. Status: **Phase 2A audit/design only, awaiting approval for Phase 2B**. No new scalability measurements, labeled real-document dataset, live inference or benchmark implementation is delivered by this plan. Synthetic performance and live inference quality must be reported separately.

Numbering: the request calls this follow-on workstream Phase 2A-2D. In the README's chronological project sequence it is **proposed Phase 13A-13D**, after Phase 12's MCUboot work. This requested filename and historical MCUboot evidence identifiers remain unchanged. This phase does not authorize a subsequent standards-evidence workstream or compliance claims.

## 1. Repository audit

| Area | Existing entry points and evidence | Implication for evaluation |
| --- | --- | --- |
| Domain | `src/ota_verifier/models.py`, `versions.py`, `policy.py` | Strict/frozen Pydantic records; dotted numeric versions; scoped downgrade authorization. Generate schema-valid input before timing. |
| Shared compatibility | `compat.py`: `requirement_holds`, `check_compatibility` | Installed active versions must satisfy all applicable requires, initially and after every activation. Reuse this single rule in baseline validation; do not invent another compatibility interpretation. |
| Planner | `planner.py`: `plan_campaign`, `_build_problem`, `_conflict`, `_optimize`, `_make_plan` | Incremental `z3.Solver`, not `Optimize`. Feasibility, assumption-based cores, makespan minimization and tie-breaking share an elapsed-time budget. |
| Concrete replay | `scheduling.py`: `duration_ms`, `activate_target`, `validate_plan` | Every returned plan is replayed internally; benchmark an additional external validation separately. A valid schedule is not a fault-recovery guarantee. |
| Independent small oracle | `benchmark/oracle.py`: `exhaustive_optimum`; `tests/test_exhaustive_planner.py` | At most three constrained 1-to-2/no-op ECUs with one/two-minute durations. Useful correctness controls, not a scalable baseline. |
| Existing corpus | `benchmark/corpus.py`, `data/benchmark_v1.json` | Frozen `ota-benchmark-v1`, seed 42; 11 deterministic campaigns and 12 synthetic extraction cases across development/held-out wording. Preserve, do not overwrite. |
| Existing runner | `benchmark/runner.py`: `evaluate_core`, `TimedClient`, `BenchmarkReport`; `eval/run_benchmark.py`, `eval/run_eval.py` | Already distinguishes core/fixtures/live, retains call latency and manifests. The current core runner also stress-tests: do not include those sweeps in planner-only timing. |
| Gold comparison | `evaluation.py`: `constraint_signature`, `compare_constraints`, `evaluate_case`, `summarize` | Semantic multiset matching ignores model IDs and normalizes numeric specs; duplicates count as false positives. Existing downstream truth comparisons are useful but bounded. |
| Extraction metrics | `benchmark/metrics.py`: `extraction_metrics`, `ratio` | Per-type precision/recall, exact-span metrics, malformed schemas, bad-draft faithfulness acceptance and blocked-case behavior have distinct denominators. Empty denominators are null. New real cases need an adapter, not synthetic-case relabeling. |
| One LLM boundary | `llm/client.py`: `ClientSettings.from_env`, `LLMClient.generate_json`, `FixtureClient` | Ollama/Gemini/Groq, explicit models, temperature 0, schema/json modes. No silent provider fallback; fixture responses explicitly have fixture origin. |
| Extraction | `llm/extractor.py`, `llm/models.py` | `DocumentRequest` contains authoritative inventory and nonempty source documents; input campaign constraints must be empty. Output draft contains constraints, citations and issues. |
| Deterministic evidence checks | `llm/evidence.py`, `llm/verifier.py`: `validate_json`, `source_segments`, `evidence_error`, `validate_draft` | Reject extra/schema-invalid fields, duplicate JSON keys, fences, nonfinite values, unknown ECUs and invalid citations. Citation must cover one full code-generated segment, not just a plausible substring. |
| Faithfulness and handoff | `llm/verifier.py`: `verify_faithfulness`, `validate_verdict`; `llm/pipeline.py`: `extract_and_verify`, `verified_campaign` | Separate second prompt checks omissions as well as extracted claims. Unresolved findings block handoff. Saved raw responses, prompt/input hashes and authoritative inventory are rechecked. Agreement is not proof of correctness. |
| Existing regressions | Planner/plan validation/exhaustive tests; `test_benchmark.py`, `test_extraction_evaluation.py`, `test_llm_client.py`, `test_llm_evidence.py`, `test_llm_pipeline.py` | Existing negative profiles include omission, reversal, false approval and malformed output. They test the harness, not live model accuracy. |
| Frozen MCUboot work | `validation/mcuboot/`, `docs/MCUBOOT_*.md` | Preserve source, historical manifests and fresh/replay distinctions. No new native bootloader work is necessary for planner/LLM evaluation. |

`PLAN.md` is a separate draft research proposal, not a dependency or evidence source for this evaluation. Additional research files appeared during this audit (`formal/`, `campaigns/`, `tools/`, `results/`, `run_all.py`, related tests/configuration). They are outside this audit's benchmark/LLM scope, are not assessed as completed capabilities here, and were left untouched. Freeze and record the actual checkout/dirty diff again before Phase 2B; this audit does not certify concurrent research work.

### Exact planner semantics

- **Requires:** `ecu@version_spec` implies `needs@needs_version_spec` at the initial state and every ordered activation state. A version dependency does not automatically impose finish-before-start write order.
- **Mutex:** member write intervals cannot overlap. **Order:** the earlier updated ECU finishes/activates before the later one starts; an unchanged endpoint makes that ordering constraint vacuous under the current contract.
- **Precondition:** a changed ECU requires an exact ignition state and minimum battery percentage in the fixed initial environment. Waiting cannot improve these values.
- Writes are nonpreemptive, go to inactive slots and may overlap; durations are rounded upward to integer milliseconds. Activations occur at completion with unique ordered ranks, even on timestamp ties. No bridge releases, atomic multi-ECU activation, bandwidth/power physics or campaign retries are modeled.
- `PlanningOptions.timeout_ms` defaults to **10,000**, `max_parallel=None` means unlimited independent write channels, and deadline is optional. The production solver seed is **0**. Workload seeds are a different setting and must not be described as varied solver seeds.
- Objective: minimum modeled makespan; then earliest starts and activation ranks in stable ECU-ID order. `plan.optimal=True` establishes makespan optimality, not necessarily completed tie-breaking; the note distinguishes incomplete tie-breaking.
- Feasible schedules may be returned without proved optimality. Infeasible results carry a proved core whose `subset_minimal` flag can be false when shrinking times out; subset-minimal is not globally smallest. Unknown is not infeasible.
- Budget starts before model construction; Z3 checks receive remaining time. Model construction and final serialization/concrete replay are not independently preempted by that budget. Therefore an external process watchdog is required; a 10-second solver setting is not a hard 10-second end-to-end bound.

## 2. Scalability workload design

These are **synthetic ECU networks**, not measured fleet data. Sizes: **10, 30, 50 and 100 total ECUs**. Record changed ECU count separately. Primary cases update every ECU; supplementary cases include 50% no-ops so nominal inventory size cannot masquerade as a larger scheduling problem.

Proposed fixed topology seeds: **11, 29, 47**. Use a local seeded generator and materialize/hash full JSON inputs; never rely on a seed alone across changing generator/dependency versions. Include source IDs and explicitly synthetic source sentences for every generated constraint. Generate inventory/state/authorizations first, constraints second, then schema-validate.

| Family | Construction and correctness control |
| --- | --- |
| W1 Independent updates | Valid originals/targets, no requires. Include equal durations and fixed seeded variation. Unlimited capacity has analytic optimum `max(duration)`; capacity-one optimum is `sum(duration)`. |
| W2 Sparse dependencies | Shuffle a witness activation order; select directed pairs requiring earlier target versions, probability 0.05. Initial antecedents false, final state valid. Verify every witness state, not merely graph acyclicity. |
| W3 Dense dependencies | Same witness construction, probability 0.50. Record realized edges/density. This intentionally increases encoded intermediate-state checks; it is a stress workload, not an asserted real-vehicle topology. |
| W4 Mixed version requirements | Numeric equality/inequality guards, satisfied current dependencies and dependencies that cease to apply after update. Include explicitly authorized downgrade cases. Check a witness through nonmonotonic changes. No unsupported compound ranges/prereleases. |
| W5 Resource-constrained parallelism | Fixed valid topology with capacity 2 or 4 and varied durations. Keep an unbounded companion for descriptive capacity comparisons; record exact options, not just ECU count. |
| W6 Satisfiable chains | Target-gated requires along a chain; compatible activation witness. Include distinct `order` companions: requires-only permits overlapping writes, whereas finish/start order serializes them. Do not conflate the two. |
| W7 Contradictory cycles and benign controls | Two changed ECUs 1-to-2: A>=2 requires B>=2 and B>=2 requires A>=2. Both endpoints valid; neither first serialized activation is legal, so genuinely infeasible. Add independent fillers to reach N. Companion cycles with always-satisfied >=1 requirements are feasible. A cycle alone is never an unsat label. |
| W8 Mutex plus ordering | Grouped mutexes, explicit order chains and seeded durations, with a legal sequential witness. Add a paired tight-deadline contradiction and a relaxed-deadline control; resource constraints must actually bind. |
| W9 Environmental conflict | Changed ECU precondition contradicts fixed ignition/battery, using schema-valid enums/percentages. Pair with a satisfiable environment. Separate environmental infeasibility from invalid JSON. |
| W10 Downgrade-policy conflict | Older target without exact ECU/version permission; paired authorized case. Record policy-core membership separately from document constraints. Do not grant permission to make the negative case feasible. |

Primary matrix uses one frozen variant per family/size/seed; paired controls are explicitly supplementary cases with separate IDs, counts and budgets. Duration pool proposed: 1, 2 and 5 simulated minutes, with a fixed fractional-duration subcase for rounding. These durations are model inputs, not wall-clock sleeps.

Positive gold labels require an independently constructed schedule and initial/intermediate/final compatibility checks. Negative labels require a documented contradiction certificate (e.g. exhaustive first-transition impossibility for the two-ECU cycle, impossible fixed precondition, or a deadline below a valid lower bound). Never assign labels from Z3's own output. Every claimed witness also passes `validate_plan`; that shared checker is not described as a fully independent oracle. Keep tiny oracle cases within their actual supported bounds.

Useful lower bounds: longest write; rounded-up total work/capacity; and critical paths of **explicit finish/start order**. Do not apply a write-duration critical-path bound to requires-only activation precedence. Do not claim optimality solely because a returned plan validates.

### Scale and encoding observations

Record total/changed ECUs, constraint counts by type, directed requires edges, graph density, mutex group sizes and implied pair count, explicit order edges, environment, authorizations and capacity/deadline. Requires are instantiated at every activation stage; dense graphs can therefore create roughly cubic numbers of dependency-stage checks as N grows. Capacity uses pairwise occupancy expressions; ordering/tie-breaking also grow. This is an audit-based complexity concern, not a measured latency/memory result.

## 3. Timing, memory and execution protocol

Use separate benchmark code, provisionally `eval/scalability/`; do not instrument/alter production decision logic. One worker process per trial, one worker at a time. Disable LLM calls in core workers and test that any attempted model call fails.

| Field | Measurement boundary |
| --- | --- |
| `generation_ms` | Seeded input generation; excluded from planner timing. |
| `schema_ms` | JSON-to-Campaign parsing; report separately. |
| `planner_api_ms` | `perf_counter_ns` around `plan_campaign`, including model construction, solving, optimization, internal validation and plan construction. This is not pure Z3-check time. |
| `external_validation_ms` | Separate concrete `validate_plan` on a feasible returned plan. The planner already did internal replay; label this extra validation accurately. |
| `serialization_ms` | Serialization/hashing/output cost; separate from decision timing. |
| `worker_total_ms` | Full worker lifetime, including imports/startup and artifact writing. Parent supervisory elapsed time is also retained. |
| memory | Prefer Windows process peak working set via standard-library `ctypes`/OS counters, including native Z3 allocations; label it peak resident working set, not allocated heap. Linux own-process `ru_maxrss` is an optional separately labelled measurement with explicit units. |

`tracemalloc` alone misses native Z3 memory and must not be reported as total solver memory. Record interpreter-only controls without subtracting unrelated process peaks as an exact solver allocation. If the peak API fails, report null with reason. Sampling-derived peaks and killed-worker observations must be marked lower bounds/censored; never replace them with zero. No additional dependency is assumed; implement a small Windows adapter only after approval and verify it against OS observations.

Record CPU model/core count, RAM, OS/build, power mode, Python bitness/version, Z3 package/native version, package lock/freeze, Git revision/dirty diff, source/generator hashes, seed and raw campaign hash. Record warm/cold process and cache conventions. Pin a dedicated benchmark dependency snapshot before measurement rather than treating `pyproject.toml` version ranges as a lock. Preserve existing MCUboot dependency/evidence pins.

Suggested execution progression:

1. Smoke: ten 10-ECU family cases, one seed, no claims of scalability.
2. Pilot: one case per family and size, 40 timed trials. Confirm witness/gold, memory visibility, watchdog and raw output integrity before the main matrix.
3. Primary: ten families x four sizes x three seeds x **five measured repetitions = 600 planner trials**, timeout 10 seconds each. One recorded warm-up per family/size adds 40 excluded-from-statistics calls. Freeze/shuffle execution order once to reduce thermal/order bias.
4. Supplementary: no-op cases, paired positive/negative controls and selected 1-/30-second timeout sensitivity cases. Publish their manifest/count before running; never add a favorable-only rerun after seeing primary results.

Proposed per-trial parent watchdog: 45 seconds; serial worker soft memory stop: 2 GiB. These are supervisory limits, not production Z3 settings or hardware-realism assumptions. Pilot must verify monitoring reliability and available host headroom before the full run. Record terminated/OOM/timeout/crash/unknown as separate statuses. Stop gracefully at a six-hour experiment budget and mark all scheduled unattempted trials `NOT_RUN`; an incomplete matrix is not a completed result.

Runtime planning arithmetic, **not measurements**: 600 trials exhausting 10 seconds corresponds to 100 solver-budget minutes, plus warm-ups/build/validation/baseline costs. If all hit the 45-second watchdog, that alone would be 7.5 hours and exceed the experiment budget. The 40-case pilot has 400 seconds of nominal solver budget and up to 30 minutes of watchdog budget. No claim of 100-ECU efficiency is made before these runs.

For each workload seed keep all repetitions, including unknowns and slow/error runs. Report median, nearest-rank p95, min/max and raw sample count. Fifteen measurements per family/size are a small descriptive sample, not a stable population-tail estimate; also show per-seed results. Do not average only optimal/successful runs and hide timeouts. Show completion/optimality proportions beside conditional successful-run latency; label censored watchdog runs separately instead of substituting timeout values as observed solver latencies.

## 4. Fair baseline

Use a **sequential greedy compatible scheduler**, not the tiny exhaustive oracle at 100 ECUs. In stable ECU-ID order, choose a remaining update whose order predecessors have completed and whose activation preserves compatibility; enforce fixed preconditions, downgrade permissions and deadline. Write/activate it, then repeat. Capacity >=1 and mutex rules hold by construction because it never overlaps writes. Validate its final `Plan` through the same public validator, with no Z3 or LLM calls.

This baseline shares the supported constraint interpretation but is neither a complete feasibility solver nor an optimizer. If greedy choice gets stuck, report `NO_BASELINE_SCHEDULE`; do not declare the campaign infeasible. Mark any deliberately unsupported input family `UNSUPPORTED`, with reason, rather than treating it as a failure or excluding it from the denominator silently. Invalid baseline output is a harness defect, not an unsupported case.

Compare independently timed execution, valid-plan discovery and makespan on the same input/options. Sequential makespan is a constructive upper bound, not the solution to the planner's parallel optimization problem. Report `baseline_makespan / z3_makespan` only for valid plans from both methods and label the denominator's optimality status. Runtime speed ratios require completed valid outcomes from both; failures/unknowns have separate rows. Use the analytic bounds and existing tiny exact oracle for correctness controls, not the baseline as an unsat oracle.

## 5. Live LLM dataset strategy

### Audited candidate sources, not a completed dataset

Official-source screening found these useful starting points:

- [Zephyr DFU documentation](https://docs.zephyrproject.org/latest/services/device_mgmt/dfu.html): partition/layout and Kconfig prerequisites are real requirements but usually outside this project's ECU-version/ignition/battery schema. Useful unsupported controls, not invented positive ECU constraints.
- [MCUboot image tool](https://docs.mcuboot.com/imgtool.html) and [design](https://docs.mcuboot.com/design.html): signed-image options and image dependencies need careful component/semantics review. Signature policy and same-device image relationships cannot automatically become independently updatable ECU dependencies.
- [PX4 bootloader update documentation](https://docs.px4.io/v1.18/en/advanced_config/bootloader_update) and [release index](https://docs.px4.io/main/en/releases/): candidates for explicit versions/procedural statements. Hardware limits, tool/build requirements and same-processor bootloader/application relationships are not automatically inter-ECU constraints.

These sources were inspected for suitability, not approved as gold positives. Freeze any admitted document by exact upstream commit/release, path, retrieval date, source URL, license and raw/content hashes. Mutable `latest`/`main` links above are discovery pointers, not reproducibility pins. Retain the complete local context needed to avoid turning a qualified statement into an unconditional rule.

**Main dataset risk:** suitable genuine ECU-like dependency statements may be scarce. Do not manufacture minimum versions, split a single MCU into fictional ECUs, or convert build/package dependencies into installed-version implications. A reviewed mapping from named firmware components to inventory IDs must preserve the source relationship and the model's semantics. If that is impossible, mark the case unsupported.

Proposed target after screening: **24 real-document cases** (8 development, 16 held-out), plus **16 separately labelled synthetic adversarial cases** (4 development, 12 held-out). These are sampling targets, not promised/collected counts. Within real data aim for at least eight unambiguous schema-expressible positive cases; do not force examples for every constraint type. Zero examples of a type means no quality claim for that type. If the positive threshold cannot be met, stop dataset admission for review; report a reduced/abstention-only study or seek approved additional sources rather than claiming broad extraction accuracy.

Synthetic adversarial data may cover explicit dependencies, minimum versions, order, mutex/preconditions, ambiguity, unsupported requirements, contradictions, missing information, irrelevant distractors and injected instructions. Its results remain separate from real-document results. Existing frozen fixtures remain regression/development controls and do not enter the new real held-out score.

### Gold labeling and review

For every case retain:

- Exact raw source/revision and exact UTF-8 ingested text, normalization recipe and hashes; any excerpt is clearly identified, with context and an exclusion reason log for screened documents.
- Authoritative inventory/current/target versions/environment/permissions, their provenance, and an explicit component-to-ID mapping. Do not let the extractor invent inventory or permissions.
- Expected semantic constraints and exact evidence: document ID plus zero-based, end-exclusive **Unicode character offsets**. Use the repository's `source_segments`; preserve full supported segments. Python offsets are not UTF-8 byte offsets. HTML/Markdown conversion must be frozen before annotation.
- Ambiguity/unsupported/missing-information labels, acceptable gate outcomes, reviewer justification, versioned adjudication history and data origin (`real_document` or `synthetic_adversarial`).
- Source-project/release grouping, split assignment, duplicate/near-duplicate family and overlap with previous fixtures.

Gold must be manually reviewed before live evaluation and held out from prompts. Two independent reviewers with adjudication are preferred; if only the author reviews, record that limitation and obtain user sign-off. Agent-generated proposed labels are not claimed as independent human review. No reviewed dataset exists yet in Phase 2A.

Split by document/release/template family, not random sentence alone. Freeze prompts on development cases, freeze the held-out hash before inference, and never tune prompts on scored held-out errors without declaring a new evaluation version. “Unfamiliar” means held out from this project's prompt/dataset development; public documents may have appeared in model pretraining. We cannot claim model-training novelty.

Clear contradictory statements that both fit the schema must retain both rules. Annotate allowed gate outcomes: ready with complete faithful constraints followed by deterministic infeasibility, or a correctly cited conflict/abstention. Do not reward silently dropping one rule. Ambiguous/unsupported cases without unique gold semantics belong in abstention metrics, not an invented exact-constraint score.

## 6. LLM execution and metrics

Use only `llm/client.py` for actual inference and the existing extraction/schema/evidence/faithfulness pipeline. No planner, simulator or invariant LLM calls. `ClientSettings` reads `.env` without mutating the process; environment wins. Required: `LLM_PROVIDER` and `LLM_MODEL`; optional `LLM_VERIFIER_MODEL`; Gemini/Groq require their configured key, Ollama requires an accessible server with the specified installed model. Only `.env.example` was inspected in this audit; credential presence, model installation, provider availability and free quota are **not verified**.

Before Phase 2C inference, validate configuration without displaying secret values, verify the endpoint/model, ensure the transport is the real HTTP transport (not an injected mock), and retain real response evidence. `CallRecord.origin='live'` alone is insufficient proof because offline tests can mock the transport. Retain command, execution date, sanitized endpoint/provider identity and run origin. No fixture fallback. If unavailable, stop and report setup requirements.

Default proposal: one actual free/local configured model, temperature 0, schema mode `schema`, maximum output 4096 tokens, 60-second per-call timeout, no automatic retries, serial requests no faster than one every five seconds. Verify current provider/model schema support and free quotas at execution time. Do not silently lower schema strictness or change models. Hosted paid use or a paid fallback requires approval. Ollama needs an operator-installed model; no GPU/RAM or download availability is assumed here.

Budget: four pilot development cases (up to eight calls), 40 cases x three repeats x up to two roles (240 calls), plus at most twelve controlled bad drafts x three verifier repeats (36 calls): **284 planned maximum, hard ceiling 300 requests**. Total study wall budget: two hours. Actual verifier calls can be fewer when deterministic validation blocks. Include requests failing transport; retries/new models consume the same budget and require a recorded new arm. All planned-but-unattempted cases remain visible if budget/rate limit stops the study. At 300 full 60-second timeouts alone, runtime could reach five hours; the wall budget stops earlier. These are bounds, not throughput predictions.

Use `TimedClient`-style wrappers to measure extraction and verification attempts independently, including failures. Report provider wall latency, pacing/retry wait and complete pipeline time separately. Record first model-load/cold call separately; temperature zero does not guarantee deterministic inference. Report requested model ID, returned immutable revision/digest if available, settings/schema/prompt hashes and context/token usage if actually provided. Otherwise use null, not an invented model revision or usage value. Maximum character input is currently 100,000; do not silently truncate.

| Metric | Definition and denominator |
| --- | --- |
| Semantic precision/recall/F1 | Exact normalized constraint multiset TP/FP/FN; precision TP/(TP+FP), recall TP/(TP+FN), F1 2TP/(2TP+FP+FN). Report micro, case-level and per-type values with counts. Empty denominators null. |
| Grounding | Exact gold span matches / semantically matched extracted constraints, plus span precision/recall over emitted/gold constraints. Also report deterministic citation validity separately; a real quote can still express the wrong rule. |
| Hallucination/over-extraction | Unsupported emitted semantic constraints / emitted constraints on evaluable cases. Report duplicate and wrongly directed/operator/version errors as separate FP subtypes; do not equate every FP with fabricated source text. |
| Schema/citation rejection | Invalid structured responses / completed extraction responses; citation failures separate; transport failures separate. Do not call provider timeouts schema failures. |
| Semantic abstention | Correct cited block/issue decisions on cases requiring abstention, with coverage and erroneous blocking of valid cases. Provider failure/invalid JSON is blocked operationally but not a successful semantic abstention. |
| Faithfulness false acceptance | Faithful verdicts on semantically wrong drafts / wrong drafts actually reviewed. Report naturally occurring mistakes separately from controlled bad-draft probes. |
| Correlated false acceptance | Gold-wrong drafts reaching ready / semantically wrong emitted drafts, plus verifier-review-conditional rate above. Agreement of both LLM calls is not gold correctness. |
| End-to-end handoff | Ready with exact gold constraints, valid evidence and completed verification / evaluable inputs; independently retain unsafe ready cases and safe blocks. Extraction correctness is separate from campaign feasibility/recovery. |
| Reliability | Attempted/scheduled cases, role call counts, provider errors, refusals, truncation, timeouts, pipeline blocks and not-run cases, all with explicit counts. |

For expressible positives, a blocked/malformed/no-output extraction has missing gold constraints (FN); precision may be null when nothing is emitted, recall is zero when gold is nonempty. Report parseable-output conditional scores alongside all-attempt scores. Preserve provenance-valid drafts even when later review blocks them. Do not let aggregate errors cancel across cases or inflate results with empty cases. Macro aggregation must state how null metrics are handled.

Controlled verifier probes omit a requirement or reverse a supported relationship/operator while retaining exact genuine citations. Run the existing deterministic checks first: rejected probes need no verifier call. A live verifier judges remaining probes using full original documents, never gold labels. This isolates verifier sensitivity without claiming that injected drafts were natural extractor errors. Existing scripted `false_approval` fixtures remain harness tests only.

Acceptance is an engineering gate, not a promised accuracy threshold: every ready extraction must satisfy existing handoff checks; every scored case must have reviewed gold and provenance; any gold-wrong ready case is a reportable finding and prevents a blanket reliable-handoff claim. No arbitrary F1 target is set after observing results. Correct extraction of conflicting requirements can legitimately lead to an infeasible campaign. No extraction/gate score by itself proves final campaign safety or human approval.

## 7. Evidence, reporting and regression gates

Proposed separate directories: `eval/scalability/` and `eval/live_extraction/`, each with versioned manifests, immutable per-attempt records, raw sanitized responses, outcomes and SHA-256 indices. Do not modify existing corpus version/hash or MCUboot evidence. New reports distinguish fresh solver execution, fresh live HTTP inference, replayed responses, synthetic fixtures and documentation analysis. A single command later may orchestrate these, but no runner is implemented in Phase 2A.

Scalability report rows must contain all workload/input counts and options, seed/repetition, expected label/certificate, actual status, note, timings, memory method/units, termination status, makespan, `optimal`, core items/count, source IDs and `subset_minimal`. Use null for inapplicable fields. Preserve exceptions, partial files and scheduled-not-run records; a failed subprocess must not reuse a stale successful row.

Planned charts: size versus latency with timeout/unknown overlays; size versus peak working set; feasible/optimal/unknown proportions; paired valid makespan ratios; conflict-core size and minimality; real-versus-synthetic extraction PR/F1 with counts; acceptance/abstention/error distribution; per-role latency. No plots of projected numbers as measurements. Figures should be standalone artifacts, with raw CSV/JSON and plotting configuration, not only screenshots.

Phase 2B tests: deterministic schema-valid generation; witness/certificate checks; cycle controls; no-op counting; baseline resource/compatibility/permission checks; watchdog/error retention; timing boundaries; native-memory observability; unsupported-baseline handling; source/corpus immutability. Run existing planner/exhaustive/simulator tests before accepting results.

Phase 2C tests: reviewed dataset/segment/hash integrity; split leakage checks; metric denominators/F1; duplicate penalties; transport versus schema/abstention distinctions; live-transport/fixture-origin separation; role/request budget enforcement; source/prompt drift; redacted evidence. Run existing client, extraction, benchmark and workflow regressions. Provider-error logs must exclude headers, credentials and raw secret-bearing exceptions; source documents and returned text need a publication review too.

Phase 2D creates `docs/PHASE2_EVALUATION_REPORT.md` only after measured results exist. Include environment, exclusions, failures, small-sample uncertainty, baseline limitations, provider drift and training-contamination threats. Update the README with a proposed Phase 13 results section only after measurements, never with the illustrative targets in the request as achieved values.

## 8. Approval gates and current blockers

| Stage | Completion gate | Current state |
| --- | --- | --- |
| 2A / proposed 13A | This audit/design, regression status and review of assumptions | Plan prepared; approval pending. |
| 2B / proposed 13B | Approved workload/budget manifest, generator/baseline tests, actual Z3 trials and unfiltered records | Not started. No planner alteration authorized. |
| 2C / proposed 13C | Separate approval; manually reviewed frozen corpus; available real provider/free budget; live-transport provenance | Not started. Dataset admission and live configuration are unresolved. |
| 2D / proposed 13D | Separate approval; consolidate actual measured outputs, charts and limitations | Not started. |

Approval of Phase 2B should settle the 600-trial primary matrix, supplementary-control manifest, resource/wall budgets and sequential-baseline scope. Main blockers for later live work are suitable expressible real-document positives, human annotation review and actual free/local provider configuration. If any is unavailable, stop that stage honestly; do not replace it with invented requirements, scripted outputs or paid services.

### Actual Phase 2A regression check

The following existing offline checks were executed; this is a correctness regression result, not a scalability or live-model measurement:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_planner.py tests/test_plan_validation.py tests/test_llm_client.py tests/test_llm_evidence.py tests/test_llm_pipeline.py tests/test_extraction_evaluation.py tests/test_benchmark.py::test_empty_metric_denominators_are_undefined tests/test_benchmark.py::test_live_api_rejects_fixture_origin tests/test_benchmark.py::test_per_case_errors_cannot_cancel_in_aggregate
```

Actual result: **136 passed, 0 failed, 0 errors, 14 warnings**. Thirteen warnings concern LangSmith's Python deprecation; one is the existing pytest cache-path creation warning. Execution required approved access to pytest's existing project-local temporary directory. No provider inference, synthetic scale runs, fixture regeneration or production change was performed. The separate concurrent research tests were not included in this check.

Only this evaluation-plan document was created for the current task. No production code, planner, public demo, review workflow, old evidence or dependencies were changed by this audit; unrelated workspace changes were preserved. Phase 2A stops here; Phase 2B requires user approval.
