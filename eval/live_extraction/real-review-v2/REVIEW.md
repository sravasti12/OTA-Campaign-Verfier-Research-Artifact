# Five real-document proposals — UNREVIEWED

No labels are approved; no inference was run. These are embedded firmware examples, not automotive validation.

Two proposed schema-expressible positives, two unsupported controls, one descriptive negative. Positive labels and ECU mappings require explicit human review.

Character spans refer to the exact ingested document, not PDF bytes or the whole web page. Raw excerpts and source-file hashes are in candidates.json. PDF/newline transformations are explicit. Synthetic inventory scaffolding is never vendor evidence.

## real-v2-01: Flysky NB4+ update order

**UNREVIEWED / NOT ADMITTED**

[Source](https://www.flysky-cn.com/s/Noble-NB4-User-manual-20231219-EN.pdf) — version: `Manual filename 20231219; NB4+; section 7.16, printed p62, PDF page67 (1-based)`

Exact raw excerpt:

```text
Note: You must update the transmitter firmware before
updating the receiver firmware.
```

Proposed structured output (offsets in ingested text):

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

Expected gate: **ready_after_faithfulness**

Ambiguities: Public manufacturer documentation, not open-source firmware. Map transmitter to NB4+ and receiver to FGr4B. Complete update before the next update starts is a conservative interpretation of before; no download-only interpretation is used. Firmware versions/durations are not stated; do not invent them as source requirements. PDF soft-wrap is joined explicitly for ingestion.

Ingestion: Join explicit newline wraps with one space. Source character span: None.

Automated checks: {'schema': 'PASS', 'exact_ingested_segments': 'PASS', 'source_substring': 'PDF_TRANSCRIPTION_REQUIRES_HUMAN_VISUAL_REVIEW'}

## real-v2-02: ExpressLRS explicit incompatible pair

**UNREVIEWED / NOT ADMITTED**

[Source](https://github.com/ExpressLRS/Docs/blob/805830b6d0bcd352ee7167ab16ab57d1c26fb421/docs/quick-start/receivers/firmware-version.md) — version: `805830b6d0bcd352ee7167ab16ab57d1c26fb421`

Exact raw excerpt:

```text
a Receiver with version string of 3.2.0 will NOT sync or bind with a TX Module with firmware version 2.4.0
```

Proposed structured output (offsets in ingested text):

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

Expected gate: **ready_after_faithfulness**

Ambiguities: Receiver and TX Module are separate embedded radio nodes, not automotive ECUs. This encodes ONLY the stated incompatible pair, not sufficient conditions for binding or every major-version combination. The negated-pair translation requires human approval; do not extrapolate a >=3 rule or create a flash order. The source bullet has no terminal period; the exact text is retained.

Ingestion: None. Source character span: [8693, 8799].

Automated checks: {'schema': 'PASS', 'exact_ingested_segments': 'PASS', 'source_substring': 'PASS'}

## real-v2-03: ExpressLRS major-version relation outside schema

**UNREVIEWED / NOT ADMITTED**

[Source](https://github.com/ExpressLRS/Docs/blob/805830b6d0bcd352ee7167ab16ab57d1c26fb421/docs/quick-start/receivers/firmware-version.md) — version: `805830b6d0bcd352ee7167ab16ab57d1c26fb421`

Exact raw excerpt:

```text
That first number in the Version string should match between a TX Module and a Receiver.
```

Proposed structured output (offsets in ingested text):

```json
{
  "constraints": [],
  "issues": [
    {
      "kind": "unsupported_requirement",
      "evidence": {
        "document_id": "real-v2-03",
        "start_char": 0,
        "end_char": 88
      },
      "source_text": "That first number in the Version string should match between a TX Module and a Receiver.",
      "message": "The surrounding pinned document defines the first number as the major version. The schema supports one comparison against a constant, not equality of two variable major components. Do not fabricate numeric thresholds or expand to unlisted versions. The excerpt and positive pair share one source: not independent samples."
    }
  ]
}
```

Expected gate: **blocked**

Ambiguities: The surrounding pinned document defines the first number as the major version. The schema supports one comparison against a constant, not equality of two variable major components. Do not fabricate numeric thresholds or expand to unlisted versions. The excerpt and positive pair share one source: not independent samples.

Ingestion: None. Source character span: [8473, 8561].

Automated checks: {'schema': 'PASS', 'exact_ingested_segments': 'PASS', 'source_substring': 'PASS'}

## real-v2-04: MCUboot scratch-memory requirement

**UNREVIEWED / NOT ADMITTED**

[Source](https://github.com/mcu-tools/mcuboot/blob/6d3b3d2c38ab20c242e5b9abb04d050086383eb2/docs/design.md) — version: `6d3b3d2c38ab20c242e5b9abb04d050086383eb2`

Exact raw excerpt:

```text
When swap-using-scratch algorithm is used, in addition to the slots of
image areas, the bootloader requires a scratch area to allow for reliable
image swapping.
```

Proposed structured output (offsets in ingested text):

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

Expected gate: **blocked**

Ambiguities: Memory-layout prerequisite is outside requires/mutex/order/ignition+battery. Bootloader is an inventory placeholder on one device, not a new cross-ECU peer. Source newline wraps are joined for ingestion; original text is retained.

Ingestion: Join explicit newline wraps with one space. Source character span: [10302, 10462].

Automated checks: {'schema': 'PASS', 'exact_ingested_segments': 'PASS', 'source_substring': 'PASS'}

## real-v2-05: MCUboot descriptive negative control

**UNREVIEWED / NOT ADMITTED**

[Source](https://github.com/mcu-tools/mcuboot/blob/6d3b3d2c38ab20c242e5b9abb04d050086383eb2/docs/serial_recovery.md) — version: `6d3b3d2c38ab20c242e5b9abb04d050086383eb2`

Exact raw excerpt:

```text
MCUboot implements a Simple Management Protocol (SMP) server.
```

Proposed structured output (offsets in ingested text):

```json
{
  "constraints": [],
  "issues": []
}
```

Expected gate: **ready_after_faithfulness**

Ambiguities: Descriptive capability, not a requirement. Empty constraints AND empty issues expected; ready means extraction handoff only. Does not validate a complete real campaign, hardware or a real update schedule.

Ingestion: None. Source character span: [952, 1013].

Automated checks: {'schema': 'PASS', 'exact_ingested_segments': 'PASS', 'source_substring': 'PASS'}
