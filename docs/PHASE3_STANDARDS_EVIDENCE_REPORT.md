# Standards-concept evidence mapping and export

Status: **VERIFIED offline exporter; PARTIALLY VERIFIED concept research; no regulatory verdict.** This follow-on workstream is project Phase 14, distinct from the original Phase 3 simulator. It does not change planner, recovery or approval behavior.

## Public references and research boundary

[UNECE's official Regulation No. 156 listing](https://unece.org/transport/documents/2021/03/standards/un-regulation-no-156-software-update-and-software-update) identifies the software-update/management-system regulation. Its linked PDF returned HTTP 403 in this research environment. The EUR-Lex version encountered a browser-verification page. Neither restriction was bypassed. **No detailed R156 clause mapping was verified or invented.** Review the applicable official text and amendments with a qualified human before using any mapping for an actual program.

[ISO's public 24089:2023 abstract](https://committee.iso.org/standard/77796.html?browse=ics) describes software-update engineering at organizational and project levels, including update packages and related participants. Its public record lists a 2024 amendment. Full licensed normative text was not used; no inaccessible clauses are quoted or inferred as implementation requirements. The following is a proposed **engineering-concept traceability matrix**, not a clause checklist or satisfaction assessment.

## Concept traceability matrix

Every row requires human review against applicable normative text. Sources are the public UNECE listing and ISO abstract above; associations below are project engineering interpretations, not assertions that those pages prescribe this implementation.

| Engineering concept | Existing capability/evidence | Export location | Missing evidence and human review |
| --- | --- | --- | --- |
| Software/configuration identification | Explicit ECU current/target/slot state | `snapshot.artifacts.input`, source documents | No vehicle identity, production release authority or signed inventory |
| Source requirement traceability | Exact document IDs/text/spans and schema checks | `traceability.constraints_and_spans` | Source authenticity, completeness and independently reviewed semantics |
| Update compatibility | Z3 schedule and shared compatibility replay | Planning plus `traceability.compatibility` | No complete hardware/product configuration universe |
| Dependency/update sequencing | Ordered activations, mutex/capacity/order rules | Full plan/state sequence | No real network bandwidth/power/timing measurements |
| Failure and restoration evidence | Deterministic faults, invariant findings, authorized slot switches | Full simulation and fault trace summary | No hardware validation; baseline bootability violations retained |
| Human decision accountability | Optional revision/hash-bound review bundle | `review_bundle`, `human_review_status` | No decision inferred when absent; identity/role assurance depends on deployment |
| Versioned tool evidence | Package/tool versions and optional existing-artifact references | `tool_versions`, `references` | No independent timestamp authority or digital signature |
| Bootloader comparison | Existing MCUboot C/simulated-flash differential observations | Hash references, original MCUboot reports | Four unsupported scenarios; intentional policy mismatches; no full equivalence |
| LLM extraction validation | Actual bounded Groq smoke; strict local source checks | Snapshot call provenance, linked Phase 2 status | Real-document and synthetic accuracy pilots blocked |
| Organizational management and records | Reviewable local artifacts only | Explicit `gaps` | Responsibilities, supplier agreements, audit/retention process, field monitoring, incident response and regulatory assessment outside project |

## Versioned export design

`src/ota_verifier/engineering_evidence.py` provides an independent deterministic JSON/Markdown export boundary using existing Pydantic records. No new dependency, decision logic or framework was added. Its fields include:

```text
engineering-evidence-v1/
  package.json       # campaign/time, complete snapshot, optional bound review,
                     # spans, compatibility, fault/rollback summary, tools, gaps, hash
  report.md          # derived human-readable status, findings and gaps
  schema.json        # generated strict Pydantic JSON Schema
  SHA256SUMS.json    # exact package/report/schema file hashes
```

The timestamp is explicitly supplied, rather than generated implicitly. For fixed input/timestamp/tool versions, bytes are reproducible. Full source documents, inventory, planner inputs/outputs/states, simulator traces, findings, recovery, call provenance and status remain in the original snapshot. Optional external references carry hash and `HASHED_EXISTING_ARTIFACT`, not a claim of fresh native execution. A package hash binds canonical content excluding itself; file hashes bind exact rendered artifacts.

No review bundle means `NOT_RECORDED`, not inferred approval. A supplied bundle must cover exactly the same snapshot and pass the existing bound-review schema. Derivable summaries must match the embedded original artifacts, including all findings. Missing planning/simulation/handoff evidence is explicitly listed. An extra or altered assurance assertion/scope is rejected, and explanation claims are rechecked with existing validation. Regulatory wording in an actual quoted source is not silently erased; it is source data rather than a verdict by the exporter.

## Actual sample and commands

The sample [package](../examples/engineering_evidence_v1/package.json), [human-readable report](../examples/engineering_evidence_v1/report.md) and [schema](../examples/engineering_evidence_v1/schema.json) use the validated saved two-ECU smoke artifacts plus the successful explanation retry. It is **simulated campaign evidence assembled across attempts**, not a freshly rerun graph/checkpoint. It retains 28 fault cases, two violation cases, four `invalid_active_image` trace findings and no supplied human review. Historical MCUboot manifest references are not fresh execution. No approval is invented.

```powershell
# Verify the committed sample, fully offline.
.\.venv\Scripts\python.exe -m ota_verifier.engineering_evidence --verify examples/engineering_evidence_v1
# Export an existing standalone ReviewSnapshot into a NEW directory.
.\.venv\Scripts\python.exe -m ota_verifier.engineering_evidence --snapshot runs/groq-followup-v1/combined-readonly-snapshot.json --recorded-at 2026-11-06T17:51:43.746732+00:00 --output runs/engineering-export-new
# Alternatively use --bundle <ReviewBundle.json> to preserve a bound human record.
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.ota_state/export-review-new tests/test_engineering_evidence.py tests/test_review_materials.py
```

The original smoke snapshot path is local ignored evidence and may be absent from a clean checkout; the checked-in sample remains independently verifiable. The sample's exact tool versions and references are recorded inside it. It contains sanitized model/source evidence; no authorization headers or `.env` contents are included.

## Validation and limitations

Initial focused checks: **15 passed, 13 existing deprecation warnings** across export and review-material tests. Coverage includes deterministic output, schema round trip, exact source spans, missing-stage gaps, findings preservation, stale/fabricated approval rejection, unsupported assertions, semantic consistency after attacker-style resealing, changed/missing file manifests and evidence tampering. Final broad-suite results are in [readiness](PROJECT_READINESS_REPORT.md).

SHA-256 detects changes relative to a trusted manifest; it is neither a digital signature nor proof of authenticity against an adversary who can replace all files. The exporter validates local consistency, not source truth, completeness of requirements, actual provider billing, vehicle operation or organizational process performance. Referenced files require separate review/verification; a hash reference alone does not validate their substantive claims. This package cannot determine regulatory approval. Normative clause mapping and missing organizational/hardware evidence remain **INCOMPLETE**.
