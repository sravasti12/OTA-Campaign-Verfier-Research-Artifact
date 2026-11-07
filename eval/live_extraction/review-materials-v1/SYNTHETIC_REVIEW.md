# Synthetic label review — human approval pending

All cases are synthetic; no live accuracy scores are asserted. Frozen labels are unchanged.
Canonical corpus SHA-256: `7a8a5008b3005a870f377b0bf7ea536c51b48dfc6a9a3419ed167f770d713ff1`

## clear-42 (development)

**Review status: PENDING — automated checks are not human approval.**

Expected blocked: `False`. Strict case schema loaded successfully.

Document `release-42` — exact text:

```text
Synthetic release record 42.
Display theme and log wording were refreshed.
When brake runs >=2, gateway must run >=2.
```

Document `guide-42` — exact text:

```text
Synthetic ECU installation guide.
Retain these notes with the campaign record.
Do not flash gateway and brake at the same time.
Flashing gateway requires ignition off and battery at least 30 percent.
```

Expected extracted constraints and exact supporting spans:

```json
[
  {
    "constraint": {
      "id": "brake-needs-gateway",
      "source_document_id": "release-42",
      "source_text": "When brake runs >=2, gateway must run >=2.",
      "type": "requires",
      "ecu": "brake",
      "version_spec": ">=2",
      "needs": "gateway",
      "needs_version_spec": ">=2"
    },
    "evidence": {
      "document_id": "release-42",
      "start_char": 75,
      "end_char": 117
    }
  },
  {
    "constraint": {
      "id": "shared-channel",
      "source_document_id": "guide-42",
      "source_text": "Do not flash gateway and brake at the same time.",
      "type": "mutex",
      "ecus": [
        "gateway",
        "brake"
      ]
    },
    "evidence": {
      "document_id": "guide-42",
      "start_char": 79,
      "end_char": 127
    }
  },
  {
    "constraint": {
      "id": "parked-charged",
      "source_document_id": "guide-42",
      "source_text": "Flashing gateway requires ignition off and battery at least 30 percent.",
      "type": "precondition",
      "ecu": "gateway",
      "ignition": "off",
      "minimum_battery_percent": 30.0
    },
    "evidence": {
      "document_id": "guide-42",
      "start_char": 128,
      "end_char": 199
    }
  }
]
```

Expected issues:

```json
[]
```

Automated draft gate codes: `[]`; verdict codes: `[]`.

Potential labeling/interpretation risks: Check operator direction, numeric versions and complete source context; do not infer extra order.

- [ ] Inventory and named-component mapping reviewed against the frozen JSON.
- [ ] Every rule/operator/type and exact Unicode span checked.
- [ ] Ambiguity/unsupported assumptions and acceptable gate outcome adjudicated.
- [ ] No prior model output used to redefine this label.

## dependency_only-43 (development)

**Review status: PENDING — automated checks are not human approval.**

Expected blocked: `False`. Strict case schema loaded successfully.

Document `release-43` — exact text:

```text
Synthetic release record 43.

Display theme and log wording were refreshed.

When brake runs >=2, gateway must run >=2.
```

Document `guide-43` — exact text:

```text
Synthetic ECU installation guide.

Retain these notes with the campaign record.
```

Expected extracted constraints and exact supporting spans:

```json
[
  {
    "constraint": {
      "id": "brake-needs-gateway",
      "source_document_id": "release-43",
      "source_text": "When brake runs >=2, gateway must run >=2.",
      "type": "requires",
      "ecu": "brake",
      "version_spec": ">=2",
      "needs": "gateway",
      "needs_version_spec": ">=2"
    },
    "evidence": {
      "document_id": "release-43",
      "start_char": 77,
      "end_char": 119
    }
  }
]
```

Expected issues:

```json
[]
```

Automated draft gate codes: `[]`; verdict codes: `[]`.

Potential labeling/interpretation risks: Check operator direction, numeric versions and complete source context; do not infer extra order.

- [ ] Inventory and named-component mapping reviewed against the frozen JSON.
- [ ] Every rule/operator/type and exact Unicode span checked.
- [ ] Ambiguity/unsupported assumptions and acceptable gate outcome adjudicated.
- [ ] No prior model output used to redefine this label.

## order_conflict-44 (development)

**Review status: PENDING — automated checks are not human approval.**

Expected blocked: `False`. Strict case schema loaded successfully.

Document `release-44` — exact text:

```text
Synthetic release record 44.

Display theme and log wording were refreshed.

gateway must finish flashing and activate before brake starts flashing.

brake must finish flashing and activate before gateway starts flashing.
```

Document `guide-44` — exact text:

```text
Synthetic ECU installation guide.

Retain these notes with the campaign record.
```

Expected extracted constraints and exact supporting spans:

```json
[
  {
    "constraint": {
      "id": "gateway-first",
      "source_document_id": "release-44",
      "source_text": "gateway must finish flashing and activate before brake starts flashing.",
      "type": "order",
      "before": "gateway",
      "after": "brake"
    },
    "evidence": {
      "document_id": "release-44",
      "start_char": 77,
      "end_char": 148
    }
  },
  {
    "constraint": {
      "id": "brake-first",
      "source_document_id": "release-44",
      "source_text": "brake must finish flashing and activate before gateway starts flashing.",
      "type": "order",
      "before": "brake",
      "after": "gateway"
    },
    "evidence": {
      "document_id": "release-44",
      "start_char": 150,
      "end_char": 221
    }
  }
]
```

Expected issues:

```json
[]
```

Automated draft gate codes: `[]`; verdict codes: `[]`.

Potential labeling/interpretation risks: Retain both explicit rules even if the planner later proves a conflict.

- [ ] Inventory and named-component mapping reviewed against the frozen JSON.
- [ ] Every rule/operator/type and exact Unicode span checked.
- [ ] Ambiguity/unsupported assumptions and acceptable gate outcome adjudicated.
- [ ] No prior model output used to redefine this label.

## intermediate_trap-45 (development)

**Review status: PENDING — automated checks are not human approval.**

Expected blocked: `False`. Strict case schema loaded successfully.

Document `release-45` — exact text:

```text
Synthetic release record 45.

Display theme and log wording were refreshed.

brake at versions >=2 requires gateway at versions >=2.

gateway at versions >=2 requires brake at versions >=2.
```

Document `guide-45` — exact text:

```text
Synthetic ECU installation guide.

Retain these notes with the campaign record.
```

Expected extracted constraints and exact supporting spans:

```json
[
  {
    "constraint": {
      "id": "brake-needs-gateway",
      "source_document_id": "release-45",
      "source_text": "brake at versions >=2 requires gateway at versions >=2.",
      "type": "requires",
      "ecu": "brake",
      "version_spec": ">=2",
      "needs": "gateway",
      "needs_version_spec": ">=2"
    },
    "evidence": {
      "document_id": "release-45",
      "start_char": 77,
      "end_char": 132
    }
  },
  {
    "constraint": {
      "id": "gateway-needs-brake",
      "source_document_id": "release-45",
      "source_text": "gateway at versions >=2 requires brake at versions >=2.",
      "type": "requires",
      "ecu": "gateway",
      "version_spec": ">=2",
      "needs": "brake",
      "needs_version_spec": ">=2"
    },
    "evidence": {
      "document_id": "release-45",
      "start_char": 134,
      "end_char": 189
    }
  }
]
```

Expected issues:

```json
[]
```

Automated draft gate codes: `[]`; verdict codes: `[]`.

Potential labeling/interpretation risks: Retain both explicit rules even if the planner later proves a conflict.

- [ ] Inventory and named-component mapping reviewed against the frozen JSON.
- [ ] Every rule/operator/type and exact Unicode span checked.
- [ ] Ambiguity/unsupported assumptions and acceptable gate outcome adjudicated.
- [ ] No prior model output used to redefine this label.

## ambiguous-46 (development)

**Review status: PENDING — automated checks are not human approval.**

Expected blocked: `True`. Strict case schema loaded successfully.

Document `release-46` — exact text:

```text
Synthetic release record 46.
Display theme and log wording were refreshed.
Update gateway first where required.
```

Document `guide-46` — exact text:

```text
Synthetic ECU installation guide.
Retain these notes with the campaign record.
```

Expected extracted constraints and exact supporting spans:

```json
[]
```

Expected issues:

```json
[
  {
    "kind": "ambiguous_requirement",
    "evidence": {
      "document_id": "release-46",
      "start_char": 75,
      "end_char": 111
    },
    "source_text": "Update gateway first where required.",
    "message": "Clarify the intended order"
  }
]
```

Automated draft gate codes: `['ambiguous_requirement']`; verdict codes: `['ambiguous_requirement']`.

Potential labeling/interpretation risks: Hidden intended order is not source-supported and must NOT become an extraction FN; review only the cited ambiguity/abstention.

- [ ] Inventory and named-component mapping reviewed against the frozen JSON.
- [ ] Every rule/operator/type and exact Unicode span checked.
- [ ] Ambiguity/unsupported assumptions and acceptable gate outcome adjudicated.
- [ ] No prior model output used to redefine this label.

## unsupported-47 (development)

**Review status: PENDING — automated checks are not human approval.**

Expected blocked: `True`. Strict case schema loaded successfully.

Document `release-47` — exact text:

```text
Synthetic release record 47.

Display theme and log wording were refreshed.
```

Document `guide-47` — exact text:

```text
Synthetic ECU installation guide.

Retain these notes with the campaign record.

Flashing gateway requires a reliable garage Wi-Fi connection.
```

Expected extracted constraints and exact supporting spans:

```json
[]
```

Expected issues:

```json
[
  {
    "kind": "unsupported_requirement",
    "evidence": {
      "document_id": "guide-47",
      "start_char": 81,
      "end_char": 142
    },
    "source_text": "Flashing gateway requires a reliable garage Wi-Fi connection.",
    "message": "Wi-Fi is outside the supported precondition model"
  }
]
```

Automated draft gate codes: `['unsupported_requirement']`; verdict codes: `['unsupported_requirement']`.

Potential labeling/interpretation risks: Wi-Fi is outside ignition/battery preconditions; do not invent supported conditions.

- [ ] Inventory and named-component mapping reviewed against the frozen JSON.
- [ ] Every rule/operator/type and exact Unicode span checked.
- [ ] Ambiguity/unsupported assumptions and acceptable gate outcome adjudicated.
- [ ] No prior model output used to redefine this label.

## heldout-clear-142 (heldout)

**Review status: PENDING — automated checks are not human approval.**

Expected blocked: `False`. Strict case schema loaded successfully.

Document `heldout-142` — exact text:

```text
Held-out simulation wording.
Cosmetic log changes only.
A brake image matching >=2 may run only if gateway matches >=2.
The flash-write windows for gateway and brake shall be disjoint.
Before starting gateway: ignition must be off; battery charge must be no less than 30%.
```

Expected extracted constraints and exact supporting spans:

```json
[
  {
    "constraint": {
      "id": "brake-needs-gateway",
      "source_document_id": "heldout-142",
      "source_text": "A brake image matching >=2 may run only if gateway matches >=2.",
      "type": "requires",
      "ecu": "brake",
      "version_spec": ">=2",
      "needs": "gateway",
      "needs_version_spec": ">=2"
    },
    "evidence": {
      "document_id": "heldout-142",
      "start_char": 56,
      "end_char": 119
    }
  },
  {
    "constraint": {
      "id": "shared-channel",
      "source_document_id": "heldout-142",
      "source_text": "The flash-write windows for gateway and brake shall be disjoint.",
      "type": "mutex",
      "ecus": [
        "gateway",
        "brake"
      ]
    },
    "evidence": {
      "document_id": "heldout-142",
      "start_char": 120,
      "end_char": 184
    }
  },
  {
    "constraint": {
      "id": "parked-charged",
      "source_document_id": "heldout-142",
      "source_text": "Before starting gateway: ignition must be off; battery charge must be no less than 30%.",
      "type": "precondition",
      "ecu": "gateway",
      "ignition": "off",
      "minimum_battery_percent": 30.0
    },
    "evidence": {
      "document_id": "heldout-142",
      "start_char": 185,
      "end_char": 272
    }
  }
]
```

Expected issues:

```json
[]
```

Automated draft gate codes: `[]`; verdict codes: `[]`.

Potential labeling/interpretation risks: Check operator direction, numeric versions and complete source context; do not infer extra order.

- [ ] Inventory and named-component mapping reviewed against the frozen JSON.
- [ ] Every rule/operator/type and exact Unicode span checked.
- [ ] Ambiguity/unsupported assumptions and acceptable gate outcome adjudicated.
- [ ] No prior model output used to redefine this label.

## heldout-dependency_only-143 (heldout)

**Review status: PENDING — automated checks are not human approval.**

Expected blocked: `False`. Strict case schema loaded successfully.

Document `heldout-143` — exact text:

```text
Held-out simulation wording.
Cosmetic log changes only.
A brake image matching >=2 may run only if gateway matches >=2.
```

Expected extracted constraints and exact supporting spans:

```json
[
  {
    "constraint": {
      "id": "brake-needs-gateway",
      "source_document_id": "heldout-143",
      "source_text": "A brake image matching >=2 may run only if gateway matches >=2.",
      "type": "requires",
      "ecu": "brake",
      "version_spec": ">=2",
      "needs": "gateway",
      "needs_version_spec": ">=2"
    },
    "evidence": {
      "document_id": "heldout-143",
      "start_char": 56,
      "end_char": 119
    }
  }
]
```

Expected issues:

```json
[]
```

Automated draft gate codes: `[]`; verdict codes: `[]`.

Potential labeling/interpretation risks: Check operator direction, numeric versions and complete source context; do not infer extra order.

- [ ] Inventory and named-component mapping reviewed against the frozen JSON.
- [ ] Every rule/operator/type and exact Unicode span checked.
- [ ] Ambiguity/unsupported assumptions and acceptable gate outcome adjudicated.
- [ ] No prior model output used to redefine this label.

## heldout-order_conflict-144 (heldout)

**Review status: PENDING — automated checks are not human approval.**

Expected blocked: `False`. Strict case schema loaded successfully.

Document `heldout-144` — exact text:

```text
Held-out simulation wording.
Cosmetic log changes only.
Starting brake is permitted only once gateway has completed its write and activation.
Starting gateway is permitted only once brake has completed its write and activation.
```

Expected extracted constraints and exact supporting spans:

```json
[
  {
    "constraint": {
      "id": "gateway-first",
      "source_document_id": "heldout-144",
      "source_text": "Starting brake is permitted only once gateway has completed its write and activation.",
      "type": "order",
      "before": "gateway",
      "after": "brake"
    },
    "evidence": {
      "document_id": "heldout-144",
      "start_char": 56,
      "end_char": 141
    }
  },
  {
    "constraint": {
      "id": "brake-first",
      "source_document_id": "heldout-144",
      "source_text": "Starting gateway is permitted only once brake has completed its write and activation.",
      "type": "order",
      "before": "brake",
      "after": "gateway"
    },
    "evidence": {
      "document_id": "heldout-144",
      "start_char": 142,
      "end_char": 227
    }
  }
]
```

Expected issues:

```json
[]
```

Automated draft gate codes: `[]`; verdict codes: `[]`.

Potential labeling/interpretation risks: Retain both explicit rules even if the planner later proves a conflict.

- [ ] Inventory and named-component mapping reviewed against the frozen JSON.
- [ ] Every rule/operator/type and exact Unicode span checked.
- [ ] Ambiguity/unsupported assumptions and acceptable gate outcome adjudicated.
- [ ] No prior model output used to redefine this label.

## heldout-intermediate_trap-145 (heldout)

**Review status: PENDING — automated checks are not human approval.**

Expected blocked: `False`. Strict case schema loaded successfully.

Document `heldout-145` — exact text:

```text
Held-out simulation wording.
Cosmetic log changes only.
A brake image matching >=2 may run only if gateway matches >=2.
A gateway image matching >=2 may run only if brake matches >=2.
```

Expected extracted constraints and exact supporting spans:

```json
[
  {
    "constraint": {
      "id": "brake-needs-gateway",
      "source_document_id": "heldout-145",
      "source_text": "A brake image matching >=2 may run only if gateway matches >=2.",
      "type": "requires",
      "ecu": "brake",
      "version_spec": ">=2",
      "needs": "gateway",
      "needs_version_spec": ">=2"
    },
    "evidence": {
      "document_id": "heldout-145",
      "start_char": 56,
      "end_char": 119
    }
  },
  {
    "constraint": {
      "id": "gateway-needs-brake",
      "source_document_id": "heldout-145",
      "source_text": "A gateway image matching >=2 may run only if brake matches >=2.",
      "type": "requires",
      "ecu": "gateway",
      "version_spec": ">=2",
      "needs": "brake",
      "needs_version_spec": ">=2"
    },
    "evidence": {
      "document_id": "heldout-145",
      "start_char": 120,
      "end_char": 183
    }
  }
]
```

Expected issues:

```json
[]
```

Automated draft gate codes: `[]`; verdict codes: `[]`.

Potential labeling/interpretation risks: Retain both explicit rules even if the planner later proves a conflict.

- [ ] Inventory and named-component mapping reviewed against the frozen JSON.
- [ ] Every rule/operator/type and exact Unicode span checked.
- [ ] Ambiguity/unsupported assumptions and acceptable gate outcome adjudicated.
- [ ] No prior model output used to redefine this label.

## heldout-ambiguous-146 (heldout)

**Review status: PENDING — automated checks are not human approval.**

Expected blocked: `True`. Strict case schema loaded successfully.

Document `heldout-146` — exact text:

```text
Held-out simulation wording.
Cosmetic log changes only.
Prefer doing gateway earlier when appropriate.
```

Expected extracted constraints and exact supporting spans:

```json
[]
```

Expected issues:

```json
[
  {
    "kind": "ambiguous_requirement",
    "evidence": {
      "document_id": "heldout-146",
      "start_char": 56,
      "end_char": 102
    },
    "source_text": "Prefer doing gateway earlier when appropriate.",
    "message": "Clarify the intended order"
  }
]
```

Automated draft gate codes: `['ambiguous_requirement']`; verdict codes: `['ambiguous_requirement']`.

Potential labeling/interpretation risks: Hidden intended order is not source-supported and must NOT become an extraction FN; review only the cited ambiguity/abstention.

- [ ] Inventory and named-component mapping reviewed against the frozen JSON.
- [ ] Every rule/operator/type and exact Unicode span checked.
- [ ] Ambiguity/unsupported assumptions and acceptable gate outcome adjudicated.
- [ ] No prior model output used to redefine this label.

## heldout-unsupported-147 (heldout)

**Review status: PENDING — automated checks are not human approval.**

Expected blocked: `True`. Strict case schema loaded successfully.

Document `heldout-147` — exact text:

```text
Held-out simulation wording.
Cosmetic log changes only.
Do not begin the gateway write without an available garage Wi-Fi link.
```

Expected extracted constraints and exact supporting spans:

```json
[]
```

Expected issues:

```json
[
  {
    "kind": "unsupported_requirement",
    "evidence": {
      "document_id": "heldout-147",
      "start_char": 56,
      "end_char": 126
    },
    "source_text": "Do not begin the gateway write without an available garage Wi-Fi link.",
    "message": "Wi-Fi is outside the supported precondition model"
  }
]
```

Automated draft gate codes: `['unsupported_requirement']`; verdict codes: `['unsupported_requirement']`.

Potential labeling/interpretation risks: Wi-Fi is outside ignition/battery preconditions; do not invent supported conditions.

- [ ] Inventory and named-component mapping reviewed against the frozen JSON.
- [ ] Every rule/operator/type and exact Unicode span checked.
- [ ] Ambiguity/unsupported assumptions and acceptable gate outcome adjudicated.
- [ ] No prior model output used to redefine this label.
