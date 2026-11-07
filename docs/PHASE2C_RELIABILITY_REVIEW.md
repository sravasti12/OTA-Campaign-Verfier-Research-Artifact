# Phase 2C targeted reliability changes and real-document readiness

7 November 2026, Asia/Calcutta. No Groq requests or new live evaluation. The original three-case synthetic pilot and every file covered by its 20-entry recovery manifest remain unchanged. Its results remain semantic F1 100% on five rules, exact rule-to-evidence grounding 3/5, expected gates 1/3, four HTTP 200 requests and 12,170 tokens; no live-pilot case reached Z3.

## Root causes and bounded changes

| Observation | Root cause | Change | What remains unresolved |
| --- | --- | --- | --- |
| clear-42 falsely rejected | Live verifier inferred an unconditional brake-version demand from a conditional antecedent | verify-v2 explicitly distinguishes antecedents from independent demands | Saved false verdict still blocks; no deterministic semantic override or automatic repair |
| Invalid verifier reference | Model used existing c1 for missing_requirement, which requires null; existing validator already enforced this | Separate diagnostics for nonexistent ID, missing required ID, and inappropriate non-null omission ID; preserve offending reference/evidence | Model can still emit invalid references; integration rejects them |
| Order citations swapped | Model attached each rule to the opposite sentence; exact quote checks only established substring provenance | New bounded source-support guard checks the complete unqualified sentence grammar `X must finish flashing and activate before Y starts flashing.` against rule type/direction | Other wording and other constraint types still rely on source checks plus LLM review; no universal entailment claim |
| Premature conflict blocking | Model added contradictory_documents despite instructions to retain unsatisfiable formal rules; old prompt also requested unresolved contradictions without a precise boundary; gate blocked all such issues | extract-v2 clarifies the distinction. Only a conflict witnessed by correctly directed opposite rules in the bounded grammar is deferred to Z3 | Unexplained conflicts and wrong citations still block; model may still misclassify a different conflict |
| Unsupported requirement | Saved unsupported-47 behavior was correct | Retain issue-based fail-closed gate and strengthen instruction against fabricated defaults; tests protect it alongside deferred conflicts | No general deterministic proof that an arbitrary unsupported demand was not omitted or fabricated |

This is not a change to deterministic planning, compatibility, simulation or safety rules. The source guard only rejects contradictions it can recognize; it does not extract, infer or repair rules. A None recognition result means **not checked by this guard**, not source support proved. Unknown language must still pass the separate faithfulness review, which remains fallible.

For solver deferral, the finding must cite an exact supported order entry and a separately cited reverse order must also be present. Both entries must match the bounded grammar; exact document/span validation and known-ECU checks still run. Any unresolved source/reference/unsupported finding blocks the pipeline. The conflict remains in `draft.issues`; the verification request explicitly lists `solver_deferred_order_conflicts`. Faithfulness must still approve before a campaign is exposed. No rule or finding is silently deleted, and the gate does not itself decide satisfiability.

## Offline replay and regression evidence

- Saved clear-42 extraction/verdict: remains blocked, with the original false missing-requirement finding and a precise null-ID diagnostic. c1 exists; the error is its use for an omission finding.
- Saved order_conflict-44 extraction: now produces two deterministic source_support blockers; original predictions/citations/conflict issue remain intact. No verifier or solver call.
- Saved unsupported-47 extraction: still zero rules, cited unsupported issue, blocked before verification.
- Separate **constructed offline control** using frozen gold order rules plus the retained conflict issue and a fixture faithful verdict: preserves both directions, defers the fully witnessed conflict, reaches real deterministic Z3 and reports infeasibility. This is not a corrected live prediction and not an improved accuracy measurement.
- Additional tests reject nonexistent verifier IDs, missing IDs for constraint-specific findings, recasting explicit order as a version dependency, invalid conflict evidence, and hiding unsupported findings behind a deferred conflict. Conditional/negated/unknown wording is not guessed by the source guard.

Final relevant regression run: **196 passed, 0 failures, 0 errors, 13 warnings in 18.56 seconds**. Warnings are LangSmith dependency uses of deprecated asyncio.iscoroutinefunction on Python 3.14.4. `pip check`: **No broken requirements found.** [Machine-readable checks](../eval/live_extraction/real-review-v2/offline-checks.json) record the exact command and interpretation. No full-suite claim replaces the historical 760 tests.

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.ota_state/reliability-review-new tests/test_pilot_reliability.py tests/test_real_review_v2.py tests/test_llm_pipeline.py tests/test_llm_evidence.py tests/test_llm_client.py tests/test_live_pilot_metrics.py tests/test_extraction_evaluation.py tests/test_graph.py tests/test_benchmark.py tests/test_plan_validation.py tests/test_review_materials.py
.\.venv\Scripts\python.exe -m pip check
```

Do not run the old pilot's execute command again. Its source-hash freeze correctly describes the old implementation; authorized v2 changes intentionally differ from that snapshot. Its original 12 execution hashes and all 20 recovery-package hashes still verify. The saved-output recovery script's old-production-source assertion is not a valid new-code regression check; do not bypass that assertion to imply the old production snapshot is unchanged.

## Files changed

- `src/ota_verifier/llm/source_support.py`: new bounded direction check and explicit witnessed-order conflict deferral.
- `src/ota_verifier/llm/verifier.py`: source-support validation, precise reference diagnostics, verify-v2 instructions and deferred-conflict audit input. Ordinary verification user payloads remain unchanged when there is no deferral.
- `src/ota_verifier/llm/extractor.py`: versioned extract-v2 prompt clarification; no parser/schema change.
- `src/ota_verifier/llm/pipeline.py`: docstring describes the bounded deferral; orchestration remains unchanged.
- `tests/test_pilot_reliability.py`: saved-response replay and constructed controls, explicitly fixture-origin.
- `tests/test_real_review_v2.py`: five candidate schema/provenance/span checks and the limited incompatible-pair interpretation.
- `eval/live_extraction/prepare_real_v2.py`: offline review-packet builder that refuses to overwrite an existing packet.
- `eval/live_extraction/real-review-v2/`: five UNREVIEWED proposals, exact text, drafts/spans, synthetic inventory scaffolding, official source snapshots, version records, provenance, checks and hashes.
- This report. Existing pilot evidence, labels and reports were not rewritten. Pre-existing unrelated working-tree changes were left in place.

## Audit of the original 20 proposals

All 20 existing candidates were inspected. Eighteen MCUboot excerpts describe image/flash layout, signature/boot policies, same-device image dependencies, build prerequisites, or descriptive behavior. None supplies a concrete cross-ECU compatibility pair or distinct-node update order with an approved inventory mapping. Multi-image dependencies must not be mislabeled as separate ECUs. The Zephyr snippet describes a same-device bootloader prerequisite; the PX4 snippet is descriptive. Their immutable provenance was also incomplete. Thus zero existing cases are admitted positive ECU examples; none was relabeled to manufacture coverage.

## Five proposed cases for human review

See [the complete review packet](../eval/live_extraction/real-review-v2/REVIEW.md) for **exact source text, proposed structured constraints/issues and offsets for every case**, and [candidate JSON](../eval/live_extraction/real-review-v2/candidates.json) for executable schema scaffolding. All labels and component mappings are **UNREVIEWED / NOT ADMITTED**.

| ID | Source/version | Proposed label | Ingested span | Expected gate |
| --- | --- | --- | --- | --- |
| real-v2-01 | [Flysky manufacturer manual](https://www.flysky-cn.com/s/Noble-NB4-User-manual-20231219-EN.pdf), filename 20231219, NB4+, section 7.16, printed p62 / PDF p67 | order: transmitter before receiver | [0:85] | Ready only after faithful review |
| real-v2-02 | [ExpressLRS Docs pinned revision](https://github.com/ExpressLRS/Docs/blob/805830b6d0bcd352ee7167ab16ab57d1c26fb421/docs/quick-start/receivers/firmware-version.md) | receiver@==3.2.0 requires tx@!=2.4.0 | [0:106] | Ready only after faithful review |
| real-v2-03 | Same pinned ExpressLRS source, general major-version relation | zero rules + unsupported_requirement | [0:88] | Blocked |
| real-v2-04 | [MCUboot design](https://github.com/mcu-tools/mcuboot/blob/6d3b3d2c38ab20c242e5b9abb04d050086383eb2/docs/design.md), pinned v2.4.0 | zero rules + unsupported_requirement for scratch memory | [0:160] | Blocked |
| real-v2-05 | [MCUboot serial recovery](https://github.com/mcu-tools/mcuboot/blob/6d3b3d2c38ab20c242e5b9abb04d050086383eb2/docs/serial_recovery.md), same pin | zero rules, zero issues; descriptive capability | [0:61] | Ready only after faithful review |

Important review points:

- Flysky's sentence says update the transmitter before updating the receiver. The proposed order uses completion before the next operation starts, a conservative reading that requires approval. Manufacturer documentation is publicly accessible, not open-source firmware. The official PDF resolves to a hash-recorded Squarespace artifact. Its two visual text lines are preserved in raw_source_excerpt; a disclosed soft-wrap join creates the ingested sentence. PDF text was retrieved and the exact PDF bytes were downloaded; screenshot retrieval failed, so human visual confirmation remains pending.
- ExpressLRS explicitly excludes receiver 3.2.0 with TX 2.4.0. The proposed `!=` rule represents **only that necessary exclusion**, not all sufficient binding conditions or the full major-version relation. Human review may reject this interpretation. The general major-equality statement is separately unsupported because the schema has only comparisons with constants, not equality between variable version components. Both cases share a source and are not independent samples.
- MCUboot's memory requirement is not an ECU dependency. The descriptive SMP statement imposes no requirement. Both preserve negative controls without invented ECU links.
- Offsets refer to exact ingested Unicode documents, not web HTML/PDF bytes. Windows MCUboot snapshots retain CRLF bytes; source-substring offsets use universal-newline decoded text. PDF/manual and ExpressLRS redistribution terms remain publication review items; public accessibility is not a blanket redistribution grant.
- Inventory version 1, one-minute duration, battery 100% and ignition off are **synthetic schema scaffolding**, not vendor data or firmware assertions. These proposals cover extraction only; a real campaign's inventory/target versions and planning feasibility would need separate evidence. Embedded radio nodes are mapped to generic simulator ECU identifiers, not claimed to be vehicle ECUs. Two proposed positives do not establish automotive-domain coverage.

## Approval gates and remaining limitations

Review the five source excerpts, proposed labels, inventory mappings, transformation/negated-pair interpretations and expected gates first. No label is automatically approved by schema checks. A later real-document pilot requires explicit corpus approval and a separately bounded Groq request/token budget; no inference was run here.

False semantic rejection, unsupported-demand omissions and language outside the bounded grammar remain model-dependent. A future new evaluation is required to measure live impact of v2 prompts/guards. Keep the old failed pilot as the baseline. Existing smoke evidence still has **26/28 fault cases passed and two genuine bootability-invariant violations**; MCUboot evidence remains **6 MATCH, 2 intentional policy MISMATCH, 4 UNSUPPORTED**. No safety/compliance, hardware or real-vehicle validation claim is made. No commit, push or deployment.
