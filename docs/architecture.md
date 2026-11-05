# Architecture and decision boundaries

OTA Campaign Verifier is a software-defined vehicle update **simulation**. It
models campaign scheduling and fault/recovery behavior; it has no vehicle adapter.

```mermaid
flowchart TD
    Inputs[Source documents + authoritative ECU inventory]
    Extract[LLM: strict JSON extraction]
    Schema[Code: schema + exact source evidence checks]
    Verify[LLM: separate faithfulness judgment]
    Gate{Verified extraction?}
    Plan[Deterministic Z3 planner: overlapping writes, ordered activation]
    Feasible{Feasible?}
    Conflict[Subset-minimal conflict or unknown]
    Baseline[Deterministic baseline A/B fault sweep]
    Guarded[Optional deterministic guarded boot sweep]
    Facts[Deterministic facts + retained traces + policy-specific status]
    Explain[LLM: advisory explanation, deterministic fallback]
    Human[Pause for explicit human review]
    Decision[Versioned decision bound to policy + snapshot hash]
    Compat[compat.py: single requires rule]
    Recovery[Authorized compatible rollback search]
    Storage[(SQLite checkpoints, receipts, revisions, review provenance)]
    OIDC[Optional Streamlit OIDC + server role allowlist]
    Inputs --> Extract --> Schema
    Schema -->|valid| Verify --> Gate
    Schema -->|invalid| Facts
    Gate -->|ready| Plan --> Feasible
    Gate -->|blocked| Facts
    Feasible -->|yes| Baseline --> Facts
    Feasible -->|no or unknown| Conflict --> Facts
    Baseline -->|guarded selected or comparison requested| Guarded --> Facts
    Compat -.-> Plan
    Compat -.-> Baseline
    Compat -.-> Guarded
    Recovery -.-> Baseline
    Recovery -.-> Guarded
    Facts --> Explain --> Human --> Decision
    OIDC -.-> Inputs
    OIDC -.-> Human
    OIDC -.-> Decision
    Storage -.-> Human
    Storage -.-> Decision
    Storage -.-> Extract
    classDef llm fill:#fff2cc,stroke:#ad7b13,color:#31270c
    classDef deterministic fill:#dff4ef,stroke:#087f8c,color:#142334
    class Extract,Verify,Explain llm
    class Schema,Plan,Baseline,Guarded,Facts,Compat,Recovery deterministic
```

Only the three yellow stages can call a model. Compatibility, planning, fault
injection, recovery, and invariant checks use deterministic code. The planner and
invariants use the same compatibility rule for every relevant intermediate state.
A second model judgment is evidence, not proof; correlated extraction errors are
measured by the benchmark's deliberately incorrect fixture profiles.

Nominal compatibility and fault tolerance are separate. A feasible parallel plan
can still fail boot or rollback invariants. Baseline and guarded reports retain
separate assessments; an explicit policy-specific revision determines what a
human decision covers. Advisory explanations cannot select a policy, alter
permissions, or approve a campaign.

SQLite is an optional trusted single-host workspace. Responses are journaled
before graph checkpoint completion; committed outputs can be reused, while
uncertain remote requests require an explicit new revision. SQL decisions are
authoritative if a process dies before its graph checkpoint catches up. Backups
capture WAL commits and are verified before restore to a new path.

Shared browser review uses authenticated issuer/subject identities and server
roles. Host operators owning source/database files remain trusted. Local mode
records reviewer names as entered. Neither hashes nor OIDC provenance constitute
a signed or tamper-resistant audit log.
