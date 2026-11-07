# Phase 2C pilot — dataset-admission audit

Status: **BLOCKED BEFORE INFERENCE — independent label-review evidence and real-document admission are unresolved.** Audit date: 6 November 2026. This is a readiness report, not a completed live accuracy pilot.

The user explicitly required stopping if adequate reviewed labels were unavailable. **Zero new Groq requests were made, zero pilot examples were executed, and no accuracy/grounding/latency scores were calculated.** Metrics are null/not evaluated, not zero accuracy or perfect empty-set performance. Historical smoke responses were not substituted for pilot measurements.

## What exists and what is missing

The [approved evaluation plan](PHASE2_EVALUATION_PLAN.md) calls for pre-inference manual gold review, exact source evidence, distinct real/synthetic partitions, and frozen development/held-out inputs. Two independent reviewers with adjudication are preferred; an author-only review must disclose that limitation and obtain user sign-off. The current user request additionally requires verifying independent review before API calls.

| Artifact | Actual status | Admission implication |
| --- | --- | --- |
| `src/ota_verifier/data/benchmark_v1.json` | Frozen `ota-benchmark-v1`, seed 42, **12 synthetic extraction cases**: six development, six held-out | Existing gold and exact citations are useful controls, but not real-document data |
| `benchmark/corpus.py`, `data/generate.py` | Formal constraints generated before text; no model generates these labels | Label construction is independent of the evaluated LLM; this alone is not independent human review |
| `docs/phase8.md` | Calls v1 a “reviewed synthetic” artifact | Preserve that historical description; case-specific reviewer identity, review date, sign-off/adjudication evidence was not located for this new study |
| Eleven deterministic core campaigns | Planning/simulation gold, not extraction examples | Do not add these to the extraction dataset denominator |
| `examples/documents/*.case.json` | Existing synthetic demonstration cases from the same generator | Not a new independently reviewed held-out corpus |
| Prior live smoke | One already-exposed synthetic requirement | Integration evidence, not a new held-out accuracy case |
| Admitted open-source firmware-document corpus | **None found** | No pinned source/excerpt/license/component mapping/reviewed gold bundle is ready to score |

The corpus canonical SHA-256 verified successfully:

```text
7a8a5008b3005a870f377b0bf7ea536c51b48dfc6a9a3419ed167f770d713ff1
```

Existing schema, provenance and reference-verdict checks were inspected for all twelve extraction cases. Eight supported cases have clean reference gates; two ambiguous and two unsupported cases carry their intended block reasons. An ambiguous case's hidden intended order is **not** justified by its source and must not be scored as a required extracted rule. Existing metric code excludes such blocked cases from supported-constraint semantics and handles them separately. A matching frozen hash and passing deterministic citation checks do not establish independent semantic review.

The plan's targets of 24 real and 16 new synthetic cases are **proposals, not collected counts**. Its real-positive admission threshold has not been met. The existing twelve synthetic wording cases must not be relabeled as real documentation or as the planned new held-out dataset. There is no claim that public documentation would be absent from model training.

## Concrete review packet — not yet admitted or executed

[The review packet](../eval/live_extraction/readiness-v1/pilot-review-packet.json) copies three existing **development** cases, with authoritative inventories, complete documents, unchanged reference constraints/issues, exact spans and expected gate behavior. Reviewer/sign-off fields are explicitly pending. No labels were generated with Groq or changed after observing outputs. No model output exists for this proposed pilot.

| Proposed case | Source evidence and unchanged expected label |
| --- | --- |
| `clear-42` | `release-42[75:117]`: “When brake runs >=2, gateway must run >=2.” → `brake@>=2 requires gateway@>=2` |
| `clear-42` | `guide-42[79:127]`: “Do not flash gateway and brake at the same time.” → mutex on gateway/brake |
| `clear-42` | `guide-42[128:199]`: “Flashing gateway requires ignition off and battery at least 30 percent.” → gateway precondition, off, minimum 30% |
| `order_conflict-44` | `release-44[77:148]`: gateway finishes/activates before brake starts; `release-44[150:221]`: brake finishes/activates before gateway starts → preserve **both** explicit order rules; do not silently remove one |
| `unsupported-47` | `guide-47[81:142]`: “Flashing gateway requires a reliable garage Wi-Fi connection.” → cited `unsupported_requirement`, zero formal constraints, blocked handoff; do not invent an ignition/battery rule |

Offsets are zero-based, end-exclusive Unicode character offsets, not byte offsets. The JSON packet contains full source context, inventory, expected IDs/spans and all reference fields. Human review must assess semantics, evidence and abstention behavior, not merely approve the existence of a hash.

These three are **existing synthetic development controls**, with no new real-document component. Running them requires explicit review/sign-off and acceptance of this reduced pilot scope. They must not later enter new held-out accuracy scores. Faithful extraction of conflicting requirements does not establish campaign feasibility: gold extraction retains both rules and the deterministic planner can find infeasibility. Any cited conflict/block behavior must be adjudicated and its scoring frozen before execution, not decided after seeing model output.

## Conditional request budget and pacing — no requests authorized by this report

Model/settings would remain Groq `openai/gpt-oss-20b`, current configured JSON Object Mode with strict local schemas/evidence checks, temperature zero, 2,048 maximum completion tokens and no automatic retries. Explanation is not needed for this accuracy pilot. No production extraction or verification change is proposed.

For at most three admitted cases: **maximum six live requests**, up to one extraction and one faithfulness call per case. Deterministic blocks can skip verification; skipped verification is not a successful verifier result. The unsupported gold case should normally block after one extraction, but a wrong extraction could still reach verification, hence the six-request ceiling. Controlled bad-draft probes and repeats are outside this initial pilot budget. Empty false-acceptance denominators remain null.

Prospective prompt estimates were reconstructed locally using existing prompts/schemas and the frozen reference draft for the verifier. **Characters/4 is only a rough estimate, not model tokenization or measured usage.** Actual verifier length depends on the actual extracted draft. API usage is unknown until actual inference.

| Case | Estimated extraction input tokens | Estimated verification input tokens | Maximum completion allowance, both calls |
| --- | ---: | ---: | ---: |
| `clear-42` | 1,989 | 1,345 | 4,096 |
| `order_conflict-44` | 1,961 | 1,240 | 4,096 |
| `unsupported-47` | 1,898 | 1,098 | 4,096 |
| All six possible calls | **9,531 estimated input tokens total** | Included in total | **12,288 maximum output tokens total** |

The rough six-call total is **21,819 input-plus-maximum-output tokens**, not predicted actual consumption or monetary cost. No paid plan or quota upgrade is proposed. Provider limits/billing access must be reconfirmed before eventual execution; a model/key being configured does not itself prove free quota availability.

The last actual project-specific metadata, from the successful explanation retry at **2026-11-06 23:21:43 Asia/Kolkata**, reported **8,000 TPM**, **1,000 daily requests**, and 2,874 remaining tokens at response time. Those are historical observations in `runs/groq-followup-v1/retry.json`, **not fresh current headroom**. No new provider call was made to probe limits while admission is blocked.

Conditional schedule: serial starts at least **70 seconds apart**, including extraction-to-verification, with observed token-reset/remaining headers extending that wait when needed. Reconfirm account headroom before starting; do not assume local pacing controls other organization users. Per-call planning estimates, previous actual usage and output caps must fit available budget; uncertain oversized requests stop for review rather than truncate critical sources. A **15-minute wall budget**, six-request hard ceiling and immediate stop on schema failure, unexpected cost or HTTP 429 bound this pilot. No automatic retries, provider/model switch, fallback fixtures or paid quota changes. The six-call schedule is roughly 6–7 minutes plus any required extra cooldown; it is a planning estimate, not measured performance.

## Evaluation criteria to freeze before a later run

Reuse the approved normalized constraint-multiset comparison and report extraction separately from faithfulness. Retain TP/FP/FN, precision/recall/F1, per-case semantic exact match, exact gold spans, deterministic citation validity, duplicates/unsupported emissions, abstention labels, schema failures, transport/provider failures and role latency. Record every scheduled/attempted/skipped/not-run case and actual provider token usage. Keep real-document and synthetic strata separate; a zero-case real stratum is **not evaluated**.

Unsupported Wi-Fi is an unsupported requirement type, not an extractor failure when correctly cited and blocked. Dropping a supported order rule, inventing a precondition or accepting an unsupported requirement is a reportable model error. Invalid JSON and HTTP failures are operational failures, not correct semantic abstentions. A verifier that faithfully accepts a gold-wrong draft is a distinct false-acceptance finding. Model agreement is not gold correctness. No passing threshold or gold revision may be chosen after output inspection.

## Actual offline checks and preserved engineering findings

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.ota_state/phase2c-readiness-tests-v1 tests/test_benchmark.py tests/test_extraction_evaluation.py tests/test_llm_client.py tests/test_llm_evidence.py tests/test_llm_pipeline.py tests/test_graph.py
```

Actual result: **149 passed, 0 failures/errors, 13 warnings in 43.84 seconds**. Existing LangSmith Python deprecation warnings are retained in [the log](../eval/live_extraction/readiness-v1/regression.log). These fixture/mocked regression checks are **not live pilot accuracy measurements**.

The prior smoke's **26/28 passed fault cases and two genuine bootability-invariant violation cases remain unchanged**. The separately successful live explanation retains `simulation_violations`. This admission audit neither reruns those model calls nor changes deterministic safety logic, prior outputs or passing criteria.

Files: [dataset audit](../eval/live_extraction/readiness-v1/dataset-audit.json), [review packet](../eval/live_extraction/readiness-v1/pilot-review-packet.json), exact regression command/log, and SHA-256 manifest under `eval/live_extraction/readiness-v1/`. Production code, existing corpus and historical evidence are preserved; no credentials appear in the packet.

## Recommendation

**Do not start inference yet.** Supply the existing independent review/adjudication record if it exists, or have a human review and sign off on the exact case labels/evidence and explicitly accept a synthetic-only development pilot. Record reviewer identity/date, limitations and any pre-inference adjudication in a new admission version without overwriting the frozen corpus. Separately assemble/review pinned real-document examples before claiming real-document accuracy. Once admission is resolved, execute only the bounded pilot and return for pilot review; do not run the remaining dataset automatically.
