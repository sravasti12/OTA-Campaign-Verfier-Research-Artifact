# Portfolio and interview guide

Use these claims with the [evaluation report](PHASE2_EVALUATION_REPORT.md) and [readiness report](PROJECT_READINESS_REPORT.md). This is a simulation project. Live accuracy evaluation is blocked; no accuracy percentages, hardware assurance or regulatory approval are claimed.

## Automotive software engineering bullets

- Built a Python OTA campaign simulator with Z3 parallel scheduling and compatibility checks at every serialized ECU activation, exposing update paths with valid endpoints but invalid intermediate states.
- Implemented deterministic A/B fault injection and authorized compatible recovery search, retaining historical bootability findings even after successful rollback.
- Compared recovery endpoints against pinned MCUboot v2.4.0 C execution over simulated flash across 12 scenarios: six matches, two intentional campaign-policy differences and four unsupported comparisons.

## Software validation/testing bullets

- Developed reproducible fault-sweep, invariant and differential-test evidence with explicit matched, mismatched, unsupported and inconclusive outcomes.
- Benchmarked 600 measured Z3 scheduling trials across 10–100-ECU synthetic networks; published feasible, infeasible, unknown and watchdog outcomes alongside baseline results and monitoring limitations.
- Added deterministic, hash-verified engineering exports that preserve source spans, fault findings, rollback paths and missing human approval; tested tampering and unsupported assurance assertions.

Use the exact final test count from the current readiness record if adding a test-count bullet. Historical 197-test follow-up and earlier release totals are different selections, not counts to sum.

## Python/backend bullets

- Designed typed Pydantic input/evidence contracts, provider adapters, LangGraph orchestration and revision-bound review workflows with optional SQLite persistence.
- Implemented offline-verifiable JSON/Markdown evidence packages with canonical content hashes, explicit missing-evidence gaps and strict approval-state validation.
- Integrated Groq, Gemini and Ollama behind one LLM interface while keeping compatibility, planning, simulation and invariants independent of inference.

## Applied AI bullets

- Executed live Groq GPT-OSS 20B extraction, source-grounded faithfulness verification and explanation on a bounded synthetic smoke case; retained HTTP 403/429 failures and the separately successful explanation retry.
- Designed extraction scoring for normalized constraint multisets, exact evidence spans, abstention and verifier false acceptance, with independent human gold review required before live accuracy measurement.
- Prepared twelve synthetic review cases and twenty real-document candidates, explicitly withholding accuracy claims where independent review or ECU semantics were unresolved.

Do not replace “smoke integration” with “validated model accuracy.” Do not call the twenty candidates approved or the twelve synthetic wording cases real firmware documentation.

## Two-minute project explanation

OTA updates are difficult because a set of individually valid firmware releases can become incompatible while a vehicle is partway through a campaign. I built a simulation that takes source documents and ECU inventory, extracts supported requirements with an LLM, checks their schema and source evidence, and asks a separate model pass to assess faithfulness.

The decisions are deterministic. Z3 schedules overlapping writes while keeping activation order compatible. The simulator then injects faults at defined A/B update boundaries, checks invariants and searches for authorized recovery paths. LangGraph ties the evidence together and pauses for human review; it does not execute vehicle updates.

I focused on showing limitations rather than hiding failures. Real MCUboot C execution over simulated flash supported six of twelve selected comparisons; two differed intentionally at the campaign-policy layer and four were unsupported. The larger scheduling benchmark exposed unknowns and watchdogs rather than supporting a general 100-ECU performance claim. A live Groq smoke demonstrated integration, but independent accuracy evaluation remains blocked on label review. Two baseline bootability violations remain visible after rollback. The project generates reviewable evidence, not a regulatory verdict.

## Technical architecture explanation

Source-only `DocumentRequest` records keep the authoritative inventory separate from extracted constraints. The extraction adapter requests strict JSON; local code checks schema, known references and exact full-segment citations. The faithfulness pass receives original sources and the draft, not gold answers. `verified_campaign` rechecks saved input/response integrity before the planner sees constraints.

The Z3 model handles requires/mutex/preconditions/order, capacity/deadline and explicit downgrade authorization. Write overlap and ordered activation are distinct. The shared `compat.py` rule is reused in planning validation and invariant checks. The planner reports feasible with an optimality flag, infeasible with a core/minimality flag, or unknown. A schedule alone does not establish recoverability.

Baseline and guarded policies model different boot mechanisms. Deterministic fault sweeps preserve intermediate findings and rollback authorization. Evidence catalog generation and explanation are separate from those verdicts. Optional persistent review binds decisions to immutable revisions/snapshot hashes; the public hosted demo uses fixture responses and no live keys. The new exporter consumes existing snapshots without altering any decision stage.

## Ten technical interview questions

1. **Why can compatible initial/final states still be unschedulable?** Two target versions can require each other before either is allowed to activate. Serialized activation then has no legal first transition.
2. **Why distinguish requires from order?** Requires constrains active versions; independent writes can overlap. An explicit order additionally requires one ECU to finish/activate before another write starts.
3. **What does a Z3 unknown result mean?** No decisive outcome was returned within the available work budget. It is not infeasibility, nor a passing schedule.
4. **Is an unsat core the smallest conflict?** Not necessarily. Subset-minimal means no element can be removed while retaining conflict; minimum cardinality is stronger. Some recorded cores did not establish even subset minimality before timeout.
5. **Why can pytest pass while fault cases violate invariants?** A regression can correctly assert that an injected unsafe baseline transition must produce a finding. That does not make the campaign fault-safe.
6. **Why preserve a boot failure after recovery?** The invariant applies throughout execution. Later restoration cannot erase the interval when the selected active image was invalid.
7. **What did MCUboot comparison establish?** Bounded selected-image/confirmation endpoints in actual C over simulated flash, with explicit policy differences and unsupported mechanisms. It did not establish full mechanism equivalence or hardware behavior.
8. **Does a faithfulness LLM prove extraction correct?** No. Extractor and verifier may share correlated errors. Exact citations constrain evidence, but independent reviewed gold and human review remain necessary.
9. **What did the scalability study reveal?** 225 feasible, 180 infeasible, 180 unknown and 15 watchdog Z3 outcomes in 600 trials. No primary positive 100-ECU schedule returned. Historical parent memory monitoring had a launcher-PID defect, disclosed rather than concealed.
10. **What do evidence hashes protect?** They detect content changes relative to a trusted manifest. They do not authenticate a source or stop an adversary replacing both artifacts and manifests; signatures and organizational controls are separate.

## Limitations to state openly

Synthetic topology timing is not vehicle-fleet performance. The full corrected-monitor matrix has not been rerun. Firmware bytes, flash timing, multi-fault behavior and complete hardware/application-health semantics are not exhaustively modeled. Live integration on one case is not extraction accuracy. Proposed document candidates lack admitted positive ECU mappings and human sign-off. Organizational process evidence, normative clause review, real OIDC and remote CI remain outside the verified package. Human decisions must not be fabricated.

## GitHub description and README guidance

Suggested description: “Simulation-first OTA campaign verification with Z3 scheduling, deterministic A/B fault recovery, source-grounded LLM extraction and reviewable engineering evidence.”

Keep the README's strengths near the top, number follow-on workstreams after the original implementation phases, and put measured limits beside measured benefits. Link the Phase 2 report, candidate review gate and sample export. Keep fixture-demo, local live integration, accuracy evaluation and standards-concept mapping visibly distinct. Publish only reviewed sanitized evidence; do not publish credentials or call logs automatically.
