# Dataset review and conditional evaluation gates

No dataset is approved by this document. No live API requests were made during the completion/audit work. Automated consistency checks and this agent's comments are not independent human annotation.

## Review materials

- [All twelve synthetic cases](../eval/live_extraction/review-materials-v1/SYNTHETIC_REVIEW.md): exact complete source documents, unchanged expected extracted rules and spans, expected ambiguity/unsupported issues, schema/gate checks and a reviewer checklist for every case.
- [Synthetic consistency record](../eval/live_extraction/review-materials-v1/synthetic-checks.json): frozen corpus digest and every case's automated result. Intentional ambiguity/unsupported gate codes are retained.
- [Pending development-review template](../eval/live_extraction/review-materials-v1/review-signoff.template.json): copy into a separately versioned signed review record; do not fill it with invented reviewers or treat its defaults as approval. The existing template covers development cases; held-out admission requires its own case-specific record.
- [Existing three-case pilot packet](../eval/live_extraction/readiness-v1/pilot-review-packet.json): proposed `clear-42`, `order_conflict-44`, `unsupported-47`. All remain pending.
- [Twenty real-document candidates](../eval/live_extraction/review-materials-v1/REAL_DOCUMENT_REVIEW.md), [JSON/provenance](../eval/live_extraction/review-materials-v1/real-candidates.json), and [candidate schema](../eval/live_extraction/review-materials-v1/candidate.schema.json).

## Label methodology and potential issues

Synthetic gold is generated deterministically before wording, independently of the evaluated model. Historical docs call the frozen corpus reviewed, but independent reviewer/date/adjudication records for this new accuracy study were not located. Version/hash checks protect labels from silent edits; they do not prove semantic correctness.

Human review must check complete context, exact IDs/Unicode spans, numeric comparison direction, minimum versus exact version, active-version dependence versus write ordering, mutex semantics and explicit ignition/battery values. Ambiguous cases include hidden intended rules that are deliberately NOT justified by their source; those are abstention controls, not recall targets. Unsupported Wi-Fi requirements must not become invented preconditions. Contradictory supported rules should remain complete even when downstream planning is infeasible. Freeze acceptable conflict/abstention scoring before inspecting model outputs.

Real candidates use actual public documentation, not generated firmware notes. Eighteen excerpts are tied to the already available official MCUboot v2.4.0 commit; source-file and exact excerpt hashes, raw source offsets and full paragraph/context are retained. Apache-2.0 LICENSE/NOTICE accompany these excerpts. Two short Zephyr/PX4 quotations are attributed, but their full context/license/immutable revision capture remains incomplete. Publication dates are unknown rather than invented; retrieval dates are recorded separately.

Every real candidate currently proposes **zero supported campaign constraints**: the passages concern flash layout, build/tool dependencies, image signatures, confirmation behavior or same-device image relationships without an approved ECU mapping. Some are descriptive negatives or tentative guidance. There are zero admitted positive ECU-version cases and no genuine conflicting ECU requirement pair. Do not convert these into fictitious ECU inventories merely to meet a sample quota. The result is a useful candidate/abstention screening packet, **not a representative real-world accuracy dataset**.

## Decisions needed from a human

1. Review/adjudicate the exact three development-case labels and acceptable gate outcomes; record reviewer, date, case IDs, frozen digest and limitations. Two independent reviewers are preferred; a disclosed single-author review plus user sign-off is the plan's alternative.
2. Explicitly accept or reject a synthetic-only development pilot and its maximum six-request/free-quota budget. Approval of autonomous offline preparation does not approve inference.
3. Separately admit a pinned real-document corpus with defensible inventories and source-to-ECU semantics. Expand sources or approve a reduced unsupported/negative-only study if adequate positives cannot be found; do not claim broad requirement-extraction accuracy from it.
4. Freeze methodology/model/prompt settings and token pacing. Review pilot results before any expansion.

Tasks 2 and 4 of the completion request remain **BLOCKED**. The [pilot-readiness report](PHASE2C_PILOT_REPORT.md) contains conditional pacing, rough token estimates and empty-denominator rules. No new model-generated labels or accuracy scores were produced. Keep the prior two bootability violations visible independently of extraction quality.

## Reproduction

```powershell
.\.venv\Scripts\python.exe eval/prepare_review_materials.py --output eval/live_extraction/review-materials-new
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.ota_state/review-packet-check-new tests/test_review_materials.py
```

Reproduction of the eighteen pinned excerpts needs the existing `.mcuboot-reference/upstream` checkout. A clean clone must establish that pinned reference separately using the existing MCUboot setup guide. The two externally screened quotations are recorded in the script with source URLs; they are not asserted commit-pinned or admission-ready. Tests verify packet integrity, not human approval or source authenticity against malicious replacement.
