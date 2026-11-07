# Final five-case admission packet ? real-review-v3

**All five cases remain UNREVIEWED / NOT ADMITTED.** ADMIT below is an assistant recommendation, not human approval. No live inference was performed.

## Revision and integrity

Canonical dataset SHA-256: `2800892519dddf8ccbe7291db6109a7e41acfbde1cd5ed638d2b529eb57e9004`

Dataset-file SHA-256: `6590470dd8681c27c01bc1cc29625f4f575caeb3fac3505c602e8b349ca74d45`

Parent packet `real-review-v2` is preserved byte-for-byte; original case IDs are retained for lineage. The synthetic pilot and historical results remain unchanged. Full source snapshots are copied into sources/.

Changes: Flysky local visual verification; added exact adjacent ExpressLRS version-format definition to case03; recalculated its evidence offsets and dataset hash. No production code changed.

## Final review table

| Case | Exact supporting text | Proposed output | Evidence span | Expected gate | Uncertainty / recommendation |
| --- | --- | --- | --- | --- | --- |
| real-v2-01 | Note: You must update the transmitter firmware before updating the receiver firmware. | `order(transmitter, receiver)` | `[0:85)` | ready_after_faithfulness | Visual transcription verified. Completion/activation-before-next-start is a conservative scheduling interpretation; owner sign-off pending. **ADMIT**. |
| real-v2-02 | a Receiver with version string of 3.2.0 will NOT sync or bind with a TX Module with firmware version 2.4.0 | `requires(receiver@==3.2.0, tx@!=2.4.0)` | `[0:106)` | ready_after_faithfulness | Only this explicit incompatible pair is excluded; other versions are not certified compatible. Existing != support checked through schema/parser/gate/Z3. **ADMIT**. |
| real-v2-03 | That first number in the Version string should match between a TX Module and a Receiver. | `0 constraints + unsupported_requirement` | `[227:315)` | blocked | Input now defines Major.Minor.Patch. Variable major equality is outside the constant-comparison schema. **ADMIT** as unsupported control. |
| real-v2-04 | When swap-using-scratch algorithm is used, in addition to the slots of image areas, the bootloader requires a scratch area to allow for reliable image swapping. | `0 constraints + unsupported_requirement` | `[0:160)` | blocked | Scratch memory is outside the formal campaign schema. LF layout wraps explicitly joined. **ADMIT** as unsupported control. |
| real-v2-05 | MCUboot implements a Simple Management Protocol (SMP) server. | `0 constraints; 0 issues` | `[0:61)` | ready_after_faithfulness | Descriptive capability imposes no requirement. Ready is extraction handoff only. **ADMIT** as descriptive control. |

## Flysky visual evidence and interpretation

The exact saved 7,858,745-byte manufacturer PDF was rendered using the built-in Windows.Data.Pdf API. The assistant inspected these actual rasterizations:

- [PDF page7 / printed p2](rendered-pages/flysky-page-7.png): introduction names the Noble NB4+ transmitter and FGr4B receiver.
- [PDF page67 / printed p62](rendered-pages/flysky-page-67.png): NB4+ header, section 7.16 Update Receiver Firmware, and bold transmitter-before-receiver statement.

The two-line source quotation is preserved below. One LF is replaced by one ASCII space for the ingested sentence; no wording or punctuation changes. This verifies the text/model/section, not human approval of the formal label. The manual does not explicitly define activation or scheduling timestamps: completion/activation before the next flash starts remains a disclosed conservative interpretation.

Official entry URL resolves to the exact Squarespace PDF recorded in sources/flysky-source.json. The filename 20231219 is the document revision identifier, not an asserted firmware version or independently established publication date. No firmware versions or flash durations are inferred from the manual.

## Exclusion implementation checks

The existing Requires.needs_version_spec validates through versions.parse_spec, which supports !=. versions.matches implements normalized numeric inequality (2.4.0 and 2.4.0.0 compare equal). validate_draft accepts the exact grounded exclusion. The Z3 planner calls _symbolic_match, which delegates current/target comparisons to that same matches function; requirement_holds applies implication at every activation stage.

Actual offline Z3 controls: receiver 3.1.2 -> 3.2.0 with TX target 2.4.0: INFEASIBLE; target 2.4.0.0: INFEASIBLE; target 3.0.1: FEASIBLE. A separate receiver 3.2.0 -> 3.2.1 / TX 2.3.0 -> 2.4.0 control requires receiver-before-TX activation to avoid an incompatible intermediate state, and Z3 produces that order. All allowed-plan states pass the existing compatibility checker. These are synthetic implementation controls, not executions of ExpressLRS firmware.

## Per-case exact source and proposed labels

### real-v2-01: Flysky NB4+ update order

[Authoritative source](https://www.flysky-cn.com/s/Noble-NB4-User-manual-20231219-EN.pdf)

Version: `Manual filename 20231219; NB4+; section 7.16, printed p62, PDF page67 (1-based)`

Exact raw source excerpt:

```text
Note: You must update the transmitter firmware before
updating the receiver firmware.
```

Proposed structured output:

```json
{
  "constraints": [
    {
      "constraint": {
        "id": "real-v2-01-rule",
        "source_document_id": "real-v2-01",
        "source_text": "Note: You must update the transmitter firmware before updating the receiver firmware.",
        "type": "order",
        "before": "transmitter",
        "after": "receiver"
      },
      "evidence": {
        "document_id": "real-v2-01",
        "start_char": 0,
        "end_char": 85
      }
    }
  ],
  "issues": []
}
```

Source-file character span: `None`. Ingestion transform: Join explicit newline wraps with one space.

Uncertainty: NB4+ model and FGr4B receiver verified on PDF page7; section7.16 and explicit order statement verified on PDF page67 / printed p62. One physical newline becomes one space. Interpreting update-before as completion/activation before the next flash starts is a conservative scheduling interpretation requiring owner approval. The manual does not explicitly use activation terminology or provide firmware versions/durations. Public manufacturer documentation, not open-source firmware.

**Recommendation: ADMIT; human review remains pending.**

### real-v2-02: ExpressLRS explicit incompatible pair

[Authoritative source](https://github.com/ExpressLRS/Docs/blob/805830b6d0bcd352ee7167ab16ab57d1c26fb421/docs/quick-start/receivers/firmware-version.md)

Version: `805830b6d0bcd352ee7167ab16ab57d1c26fb421`

Exact raw source excerpt:

```text
a Receiver with version string of 3.2.0 will NOT sync or bind with a TX Module with firmware version 2.4.0
```

Proposed structured output:

```json
{
  "constraints": [
    {
      "constraint": {
        "id": "real-v2-02-rule",
        "source_document_id": "real-v2-02",
        "source_text": "a Receiver with version string of 3.2.0 will NOT sync or bind with a TX Module with firmware version 2.4.0",
        "type": "requires",
        "ecu": "receiver",
        "version_spec": "==3.2.0",
        "needs": "tx",
        "needs_version_spec": "!=2.4.0"
      },
      "evidence": {
        "document_id": "real-v2-02",
        "start_char": 0,
        "end_char": 106
      }
    }
  ],
  "issues": []
}
```

Source-file character span: `[8693, 8799]`. Ingestion transform: None.

Uncertainty: Receiver and TX Module are separate embedded radio nodes, not automotive ECUs. This encodes ONLY the stated incompatible pair, not sufficient conditions for binding or every major-version combination. The negated-pair translation requires human approval; do not extrapolate a >=3 rule or create a flash order. The source bullet has no terminal period; the exact text is retained.

**Recommendation: ADMIT; human review remains pending.**

### real-v2-03: ExpressLRS major-version relation outside schema

[Authoritative source](https://github.com/ExpressLRS/Docs/blob/805830b6d0bcd352ee7167ab16ab57d1c26fb421/docs/quick-start/receivers/firmware-version.md)

Version: `805830b6d0bcd352ee7167ab16ab57d1c26fb421`

Exact raw source excerpt:

```text
A Version is defined or formatted as "Major.Minor.Patch"

        - major = major new feature and/or incompatible changes
        - minor = minor features or enhancements and/or new targets
        - patch = bug-fixes
    
    That first number in the Version string should match between a TX Module and a Receiver.
```

Proposed structured output:

```json
{
  "constraints": [],
  "issues": [
    {
      "kind": "unsupported_requirement",
      "evidence": {
        "document_id": "real-v2-03",
        "start_char": 227,
        "end_char": 315
      },
      "source_text": "That first number in the Version string should match between a TX Module and a Receiver.",
      "message": "Matching the variable major-version components of two nodes is outside the fixed-constant comparison schema."
    }
  ]
}
```

Source-file character span: `[8246, 8561]`. Ingestion transform: None.

Uncertainty: The version-format definition and major/minor/patch explanations are now included in the input. General equality between two variable major versions is not expressible by one fixed-constant version comparison. Do not enumerate unstated versions. Shares the same source as real-v2-02; not independent coverage.

**Recommendation: ADMIT; human review remains pending.**

### real-v2-04: MCUboot scratch-memory requirement

[Authoritative source](https://github.com/mcu-tools/mcuboot/blob/6d3b3d2c38ab20c242e5b9abb04d050086383eb2/docs/design.md)

Version: `6d3b3d2c38ab20c242e5b9abb04d050086383eb2`

Exact raw source excerpt:

```text
When swap-using-scratch algorithm is used, in addition to the slots of
image areas, the bootloader requires a scratch area to allow for reliable
image swapping.
```

Proposed structured output:

```json
{
  "constraints": [],
  "issues": [
    {
      "kind": "unsupported_requirement",
      "evidence": {
        "document_id": "real-v2-04",
        "start_char": 0,
        "end_char": 160
      },
      "source_text": "When swap-using-scratch algorithm is used, in addition to the slots of image areas, the bootloader requires a scratch area to allow for reliable image swapping.",
      "message": "Memory-layout prerequisite is outside requires/mutex/order/ignition+battery. Bootloader is an inventory placeholder on one device, not a new cross-ECU peer. Source newline wraps are joined for ingestion; original text is retained."
    }
  ]
}
```

Source-file character span: `[10302, 10462]`. Ingestion transform: Join explicit newline wraps with one space.

Uncertainty: Memory-layout prerequisite is outside requires/mutex/order/ignition+battery. Bootloader is an inventory placeholder on one device, not a new cross-ECU peer. Source newline wraps are joined for ingestion; original text is retained.

**Recommendation: ADMIT; human review remains pending.**

### real-v2-05: MCUboot descriptive negative control

[Authoritative source](https://github.com/mcu-tools/mcuboot/blob/6d3b3d2c38ab20c242e5b9abb04d050086383eb2/docs/serial_recovery.md)

Version: `6d3b3d2c38ab20c242e5b9abb04d050086383eb2`

Exact raw source excerpt:

```text
MCUboot implements a Simple Management Protocol (SMP) server.
```

Proposed structured output:

```json
{
  "constraints": [],
  "issues": []
}
```

Source-file character span: `[952, 1013]`. Ingestion transform: None.

Uncertainty: Descriptive capability, not a requirement. Empty constraints AND empty issues expected; ready means extraction handoff only. Does not validate a complete real campaign, hardware or a real update schedule.

**Recommendation: ADMIT; human review remains pending.**

## Offline validation and limitations

All five cases passed strict schema, exact source hash, source-substring (or recorded PDF visual evidence), ingested evidence-offset, and expected fixture-gate checks. Expected faithful verdicts were explicitly constructed offline fixtures. No live faithfulness or extraction accuracy is claimed. Case03 issue evidence is [227:315) in the extended 315-character document; the full raw excerpt is [8246:8561) in the pinned decoded source.

MCUboot v2.4.0 sources remain pinned to 6d3b3d2c38ab20c242e5b9abb04d050086383eb2. Windows snapshot bytes use CRLF; source-file offsets refer to universal-newline decoded Unicode. Their normalized text hashes match the previous pinned-source records. ExpressLRS is pinned to 805830b6d0bcd352ee7167ab16ab57d1c26fb421; the two ExpressLRS examples share a source and are not independent samples.

Numeric inventory fields are synthetic schema scaffolding, not vendor facts. Firmware documents describe embedded radio/bootloader systems, not vehicle ECUs. No full compatibility, hardware or regulatory validation is claimed. Redistribution terms for manufacturer PDF and ExpressLRS documentation remain publication checks.

Focused regression: **120 passed, 0 failed/errors, 13 LangSmith deprecation warnings, 1.32 seconds**. See validation.json and regression.json. No broad audit or live evaluation was run.

```powershell
.\.venv\Scripts\python.exe eval/live_extraction/validate_real_v3.py
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.ota_state/real-admission-v3-new tests/test_real_review_v3.py tests/test_real_review_v2.py tests/test_pilot_reliability.py tests/test_llm_evidence.py tests/test_llm_pipeline.py tests/test_versions.py tests/test_planner.py
```

PDF rendering reproduction on Windows (choose a new output directory; renderer refuses existing image names):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File eval/live_extraction/render_flysky.ps1 -PdfPath eval/live_extraction/real-review-v3/sources/flysky-nb4-manual.pdf -OutputDirectory .ota_state/flysky-render-new
```

Review source text, mappings, normalization and the two positive interpretations before granting corpus approval. A separate bounded request-budget approval is required before live evaluation. No case was approved, no Groq request made, and nothing committed, pushed or deployed.