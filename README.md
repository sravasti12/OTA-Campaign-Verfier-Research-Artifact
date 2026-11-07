# OTA Campaign Verifier

A **software-defined vehicle OTA campaign simulation** that checks the path to
an update, including intermediate versions and fault recovery.

A campaign can end with compatible versions yet have no compatible activation
order. It can also have a feasible nominal schedule but fail to recover after a
boot fault. This project makes those differences visible before a human reviews
the simulated proposal.

LLMs extract requirements, check extraction faithfulness, and explain evidence.
**Compatibility, parallel planning, fault injection, recovery, and invariants are
deterministic code.** They run and are tested without model services.

LangGraph orchestrates the workflow and pauses for human review. The LLM
interprets documentation; it does not decide compatibility, schedule updates,
inject faults or authorize execution. This is a verification pipeline with
inspectable solver and simulation evidence, rather than a conversational answer
treated as an update decision. It does not control real vehicles.

```mermaid
flowchart LR
    D[Release notes and ECU documentation] --> E[LLM requirement extraction]
    E --> V[Schema, source and LLM faithfulness checks]
    V --> Z[Z3 campaign planning]
    Z --> S[Deterministic fault injection and recovery]
    S --> R[Engineering evidence and advisory explanation]
    R --> H[Human review]
```

[Live demo](https://ota-campaign-verifier.streamlit.app/) |
[Measured results](#measured-evaluation-and-current-limits) |
[Project phases](#project-phases) |
[Setup](#setup-and-tests)

[Project and architecture report](docs/OTA_Campaign_Verifier_Project_Report.html)

![Guarded recovery comparison with retained baseline violations](docs/assets/guarded-recovery.png)

*Actual Streamlit UI using scripted synthetic responses. The guarded example
passes its modeled sweep while baseline failures stay visible; human review is
still pending. This is not live-model accuracy, vehicle validation, or
certification evidence.*

[Three-minute demo](docs/demo_walkthrough.md) | [Screen recording](docs/assets/demo.webm) |
[Architecture](docs/architecture.md) | [Release validation](docs/phase11.md)

## Research artifact: formal checking of multi-ECU campaigns

The journal paper's evidence is separate from the planner, LLM and MCUboot work below. It uses only these files:

| Part | Code | Results | Write-up |
| --- | --- | --- | --- |
| TLA+ campaign model, 4 safety and 1 liveness property, 3 flawed designs | `specs/tla/OTACampaign.tla`, `experiments/e0_small_campaign.py` | `results/raw/e0_small_campaign/` | [SMALL_CAMPAIGN_RESULTS](docs/SMALL_CAMPAIGN_RESULTS.md) |
| Scaling (5 to 50 ECUs) and the pair abstraction | `experiments/e3_scaling.py`, `specs/tla/OTAPair.tla` | `results/scaling.csv`, `results/raw/e3_scaling/` | [SCALING_RESULTS](docs/SCALING_RESULTS.md), [soundness](docs/PAIR_ABSTRACTION_SOUNDNESS.md) |
| Model against software-in-the-loop (SIL) simulator | `experiments/e5_predict.py`, `experiments/e5_sil.py`, `sil/` | `results/predictions/e5/`, `results/raw/e5_sil/`, `results/confusion.csv` | in progress |
| Raspberry Pi testbed | none yet | none: **not built** | [build plan](docs/RASPBERRY_PI_TESTBED.md) |

Reproduce with Python 3.11 or later and Java. CI uses Java 17, and the recorded runs used Java 18.

```bash
python tools/fetch_tools.py
python run_all.py --experiment e0_small_campaign
python run_all.py --experiment e3_scaling      # about 3 hours on a laptop
python experiments/plot_scaling.py
python experiments/summarize_scaling.py
python run_all.py --experiment e5_predict
python run_all.py --experiment e5_sil
```

Each run writes a new folder in `results/raw/` with a manifest recording the commit, uncommitted files, seed and environment. Rules are in [results/README.md](results/README.md), and open problems in [RESULTS_AUDIT](docs/RESULTS_AUDIT.md).

## Engineering strengths

- **Intermediate-state reasoning:** one compatibility rule serves Z3 planning and invariant checking, catching campaigns whose endpoints are compatible but whose activation path is not.
- **Parallel flashing with explicit semantics:** writes overlap while activations remain ordered; mutex, capacity, deadline and downgrade requirements stay traceable to evidence.
- **Recovery beyond a nominal plan:** deterministic fault sweeps, authorized rollback search and guarded boot-policy comparisons retain violations and inconclusive results.
- **Reviewable decisions:** extraction citations, revision-bound human approval, SQLite history and verified evidence bundles connect results to the exact inputs and policy.
- **Independent bootloader observations:** pinned MCUboot C execution is compared with the Python model; intentional differences and unsupported mechanisms remain visible.
- **Inspectable engineering evidence:** deterministic JSON/Markdown exports retain source spans, compatibility states, rollback outcomes, safety findings and missing approval, with verifiable hashes.

## Project phases

Phases 1-11 build the campaign-verification workflow. Phase 12 adds MCUboot
validation (12A-12E); Phase 13 covers scalability, LLM evaluation and reliability
retesting; Phase 14 covers standards-concept engineering evidence. These are
fourteen project phases, with implementation and validation limits recorded separately.

| Phase | Capability | Guide |
| --- | --- | --- |
| 1 | Validated ECU/constraint models and shared compatibility rule | [Domain contract](#phase-1-domain-model-and-compatibility) |
| 2 | Z3 parallel flash planning and conflict evidence | [Planning](#phase-2-parallel-flash-planning) |
| 3 | A/B fault injection, invariant checking and recovery search | [Simulation](#phase-3-fault-simulation-and-invariant-checking) |
| 4 | LLM extraction, schema/faithfulness checks and source evidence | [Phase 4](docs/phase4.md) |
| 5 | Streamlit/LangGraph local review and human approval | [Phase 5](docs/phase5.md) |
| 6 | Baseline versus guarded trial-boot comparison | [Phase 6](docs/phase6.md) |
| 7 | SQLite persistence, revisions and review history | [Phase 7](docs/phase7.md) |
| 8 | Reproducible deterministic and extraction-fixture benchmarks | [Phase 8](docs/phase8.md) |
| 9 | Explicit policy selection and policy-bound approval | [Phase 9](docs/phase9.md) |
| 10 | Optional authenticated shared review and operational controls | [Phase 10](docs/phase10.md) |
| 11 | Release validation and portfolio evidence | [Phase 11](docs/phase11.md) |
| 12 | MCUboot reference execution and independent recovery comparison | [Phase 12A-12E](#phase-12-mcuboot-recovery-validation) |
| 13 | Z3 scalability, synthetic/real-document Groq development evaluations, reliability repairs and final retest | [Phase 13 overview](#phase-13-scalability-and-live-llm-evaluation), [final comparison](docs/PHASE2C_FINAL_RETEST_COMPARISON.md) |
| 14 | UNECE R156 / ISO 24089 concept traceability and tested engineering exports; normative/organizational review incomplete | [Phase 14 overview](#phase-14-standards-concept-engineering-evidence), [evidence report](docs/PHASE3_STANDARDS_EVIDENCE_REPORT.md) |

Implemented features and exercised infrastructure are separate: mocked/offline
checks do not establish live provider accuracy, remote CI or live OIDC operation.
Follow-on workstream names “Phase 2” and “Phase 3” refer to project phases 13 and
14 here; they do not replace the original planner/simulator phase numbers.

## Measured evaluation and current limits

| Evaluation | Actual evidence | Qualification |
| --- | --- | --- |
| Z3 scalability | 600 measured trials: 225 feasible, 180 infeasible, 180 unknown, 15 watchdogs | Synthetic 10/30/50/100-ECU inputs; no primary positive 100-ECU schedule returned |
| Sequential baseline | 420 valid schedules, 180 no-schedule outcomes | Greedy sequential construction is not a complete parallel optimizer |
| Live Groq integration | GPT-OSS 20B extraction, faithfulness and explanation succeeded across smoke/follow-up attempts | Four example requests include one HTTP 429; not a dataset accuracy result |
| Fault findings | Nominal smoke passed; 26/28 fault cases passed, two bootability violations | Successful authorized rollback does not erase earlier unsafe states |
| Synthetic Groq development pilot | Three owner-approved cases; semantic precision/recall/F1 100%; grounding 3/5; complete outcomes 1/3 | Five expected rules; swapped citations and verifier/gate errors retained |
| Original real-document pilot | Five approved cases; three attempted; three HTTP 200 and one HTTP 400; semantic F1 66.7% | Two usable drafts, two NOT_RUN cases; no case reached Z3 |
| Final real-document retest | All five cases executed; eight HTTP 200 responses, zero retries; semantic/grounding precision and recall 100%; complete outcomes 4/5 | Two positive rules in known embedded-document cases; Flysky false rejection persists; two feasible zero-step plans |
| Evidence export | Versioned JSON, Markdown, schema and hashes, with tamper/approval checks | Simulated engineering evidence; no regulatory verdict or hardware assurance |

The historical Windows benchmark parent monitored a venv launcher rather than
the worker interpreter. Its parent memory readings/soft-limit enforcement are
unreliable; returned-worker self-peaks remain recorded. The monitoring fix has
an isolated verification, **not** a corrected full matrix rerun.

Historical broad offline check: **760 passed, 0 failures/errors, 13 dependency
deprecation warnings** across the then-existing tests plus MCUboot/scalability
regressions. The final retest's targeted regression run separately recorded
**274 passed, 0 failures/errors, 13 warnings**; it is not a replacement full-suite
count. `pip check` found no broken requirements. Passing regressions do not erase
the recorded fault findings or the live verifier failure.

[Current readiness and remaining risks](docs/PROJECT_READINESS_REPORT.md) |
[Detailed measurements](docs/PHASE2_EVALUATION_REPORT.md) |
[Final real-document comparison](docs/PHASE2C_FINAL_RETEST_COMPARISON.md) |
[Human dataset review](docs/DATASET_REVIEW_GUIDE.md) |
[Sample engineering evidence](examples/engineering_evidence_v1/report.md) |
[Portfolio/interview guide](docs/PORTFOLIO_AND_INTERVIEW_GUIDE.md)

**Phase 13 has measured development results, not established general reliability.**
The final retest completed its five-case execution, but one false faithfulness
rejection remains. The corpus is not an automotive ECU accuracy benchmark, and
no full held-out accuracy study is claimed. The standards-concept mapping still
needs human normative review and organizational evidence beyond this simulation.

## Live demo

[Open OTA Campaign Verifier](https://ota-campaign-verifier.streamlit.app/)

Interactive verification of the hosted deployment remains separate from local tests.

Hosted on Streamlit Community Cloud. The public demo runs real deterministic
analysis on synthetic fixtures; no API keys are needed. Provider configuration
and server-filesystem controls are omitted, and review records are session-only
simulation records.

See the [free deployment and maintenance guide](docs/deploy_free.md) for setup.
The public fixture demo does not validate the separate shared-mode OIDC setup.

## What the demonstrations prove under the model

| Scenario | Measured result | Why it matters |
| --- | --- | --- |
| Parallel update | Six ECU-minutes of writing in four simulated minutes, with every activation compatible | Writes overlap while activation dependencies remain enforced. |
| Intermediate-version trap | Final versions compatible; no feasible activation order; two source-linked conflicting rules | Checking the destination alone misses the problem. |
| Guarded recovery | Baseline violations retained; guarded policy passes 48 cases, including 6 confirmation cases | Policy improvements remain separate from baseline evidence and human approval. |

The frozen reference benchmark matches all 11 labeled deterministic campaigns
and covers 252 core fault cases. Its 12 extraction fixtures yield 8 ready and 4
required-abstention outcomes. These are regression checks using supplied answers,
not measured model performance. See the [recorded local evidence](docs/release-evidence.json).

**Earlier release-record verification:** 548 tests passed on Windows/Python 3.14.4, with 14
upstream/cache warnings. The JUnit digest and counts are retained in the release
summary.

**Release status:** local evidence and the browser demo are validated. Remote
Windows/Linux CI and real OIDC login/role/logout checks remain pending because
those services are not configured. The hosted fixture demo is linked above;
its availability does not establish passing remote CI or shared-mode OIDC checks.

## Setup and tests

[Final publication verification](docs/FINAL_PUBLICATION_READINESS.md) records the
clean public-checkout tests and optional third-party reference checks.

Python 3.11+ is required. In PowerShell, from this directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest -q
```

The workspace verification uses Python 3.14.4. Python 3.11 has not been exercised
here. Deterministic planning and core tests run offline without LLM services,
environment variables or credentials. Offline evaluation-profile tests supply explicit dummy provider settings and
prohibit real HTTP; they do not require private provider configuration. Public tests do not require the four restricted Flysky assets: absent external
references are explicitly reported as unavailable, while present files must
match their hashes. The [optional reference audit](docs/THIRD_PARTY_PUBLICATION.md#offline-commands)
checks the original assets when independently obtained. `.env.example` documents optional provider
configuration; `.env` is ignored.

Run just the Phase 2 tests:

```powershell
.\.venv\Scripts\python -m pytest -q tests/test_planner.py tests/test_exhaustive_planner.py tests/test_plan_validation.py tests/test_cli.py
```

## Phase 1: domain model and compatibility

ECU configuration and runtime state are separate: `ECU` holds current/target
versions and flash duration; `ECUState` holds A/B images and active slot.
Constraints retain stable IDs, source document IDs, and source sentences.
Pydantic rejects unknown fields, malformed specifications, unknown ECU references,
duplicate IDs, invalid active slots, incomplete initial state, and contradictory
current-version observations.

One definition in `compat.py` expresses dependency implication for both concrete
and symbolic evaluation. `check_compatibility` returns all violated `requires`
constraints with source evidence, actual dependency version, and expected spec.
Only active images participate. Missing or extra runtime ECUs raise an input
error rather than being treated as compatible.

Compatibility alone does not imply bootability, valid environment, allowed
ordering, or authorization. Invalid active images and incompatible initial
states remain representable as input for analysis; the planner blocks them.
An active slot must contain an image. Unbootability is represented with
`valid=false`, which is supplied simulation data, not verified cryptographic
image integrity.

Versions are dotted nonnegative numeric components: `4.10 > 4.2`, `4.2.0 == 4.2`,
and leading zeros are insignificant. Each specification has one explicit `==`,
`!=`, `>=`, `<=`, `>`, or `<` comparison. Prereleases, build metadata, compound
ranges, prefixes, and whitespace are rejected.

Strict Python construction uses tuples; JSON arrays are accepted through
`model_validate_json`. Records are frozen and `model_dump_json` preserves source
evidence. Create states with validated constructors rather than unchecked
`model_construct` or `model_copy(update=...)` APIs. `validate_plan` checks nominal
validity, not a caller-supplied claim of optimality.

## Phase 2: parallel flash planning

```powershell
.\.venv\Scripts\python -m ota_verifier.cli examples/parallel_campaign.json --max-parallel 2
```

The demo needs nine total ECU-minutes of writing but finishes in five simulated
minutes: infotainment overlaps the gateway/brake updates. Gateway and brake
share a mutex, and brake activation requires the updated gateway. The result is
JSON containing exact start/end times, activation indices, source constraint
IDs, written slots, and the initial state plus every post-activation state.

Block that campaign with a four-minute deadline:

```powershell
.\.venv\Scripts\python -m ota_verifier.cli examples/parallel_campaign.json --max-parallel 2 --deadline-ms 240000
```

The result identifies the shared-flash-channel requirement and deadline as a
subset-minimal conflict, with the requirement's original document and sentence.
The JSON result is a diagnostic report, not permission to waive requirements.

CLI exit codes are 0 feasible, 2 infeasible, 3 unknown, and 1 invalid input.
Argument syntax errors use argparse's standard exit code 2. Installed packages
also expose the `ota-plan` command. Options include `--timeout-ms` (default 10000),
`--max-parallel`, and `--deadline-ms`. Omitting a concurrency limit assumes
unlimited independent write channels; set a limit to model constrained resources.

### Python API

```python
from pathlib import Path
from ota_verifier.models import Campaign, FeasibleResult, PlanningOptions
from ota_verifier.planner import plan_campaign
from ota_verifier.scheduling import validate_plan

campaign = Campaign.model_validate_json(
    Path("examples/parallel_campaign.json").read_text(encoding="utf-8-sig")
)
result = plan_campaign(campaign, PlanningOptions(max_parallel=2))
if isinstance(result, FeasibleResult):
    assert validate_plan(campaign, result.plan) == ()
    assert result.plan.makespan_ms == 300_000
```

### Planning semantics

| Concern | Explicit modeling rule |
| --- | --- |
| Writes | Nonpreemptive writes to inactive A/B slots; old active images keep running. |
| Timing | Integer milliseconds. Each supplied flash duration is rounded upward to a millisecond. |
| Activation | Instantaneous at write completion. Every activation has a unique index. Equal-time activations execute in index order, with compatibility checked after each. |
| Intermediate compatibility | Initial state and every ordered post-activation state must satisfy every applicable dependency. Writes alone do not change active versions. |
| Mutex | No pair in a mutex group may overlap writes. Intervals are half-open: an end may equal another start. |
| Order | The before ECU must finish and activate before the after ECU starts; equal end/start timestamps are permitted with activation first. |
| Environment | Ignition and battery remain at their initial values. Each changed ECU's preconditions must hold; waiting cannot improve the environment. |
| Capacity | At most `max_parallel` writes overlap. No bandwidth sharing, power load, or flash-speed variation is modeled. |
| Deadline | Every write and activation must finish by the supplied deadline. |
| Downgrades | A numerically older target requires authorization matching the exact ECU and numeric destination version. |
| Image validity | All initial active images must be marked valid. Nominal target writes are assumed successful and valid. |
| No-op ECUs | Numerically equal current/target versions need no step but remain in all compatibility checks. Order applies only when both endpoints are updated; mutex and preconditions apply only to scheduled writes. |
| Update repertoire | One direct current-to-target update per changed ECU; no bridge releases, repeated updates, or atomic multi-ECU activation. |

The solver minimizes campaign makespan in the millisecond model. Among optima,
it prefers earlier starts and then lower activation indices in ECU ID order.
Every returned plan is independently replayed through the concrete compatibility
checker and concrete schedule checks. A validation disagreement raises an
internal error instead of returning a successful result.

A hard scheduling horizon equal to the sum of rounded write durations is
sufficient under these fixed-environment rules: any feasible activation order
can be executed sequentially within that horizon. Capacity and mutex constraints
only restrict overlap, and no modeled requirement imposes a minimum wait.

Result types deliberately distinguish:

- `feasible`: a validated schedule. `plan.optimal` reports whether minimum makespan
  was proved. If optimization times out, an already established feasible schedule
  can still be returned with `optimal=false` and an explanatory note.
- `infeasible`: a proved contradiction, with source constraints and/or explicit
  resource/policy assumptions. `conflict.subset_minimal=true` means removing any
  reported group makes that subset satisfiable relative to the fixed transition
  model. This is not a globally smallest conflict set. If shrinking times out,
  the proved core is retained and minimality is marked false.
- `unknown`: no feasibility verdict was established within the solver budget.
  This never means the campaign is impossible.

The budget is shared across feasibility, conflict shrinking, optimization, and
tie-breaking. Ties may remain noncanonical if that budget expires after makespan
optimality is established; the result note reports this separately. Serialization
and concrete replay can take additional time beyond the solver budget.

Plan states project active images and completed activations. They do not record
partially written inactive images or fault traces. A feasible nominal plan does
not establish recovery or fault-tolerance properties. The Phase 3 simulator adds
actual intermediate simulated slot states and fault/recovery evidence without
changing the planner's nominal guarantees.

## Phase 3: fault simulation and invariant checking

Run the same parallel demo through the full bounded single-fault matrix:

```powershell
.\.venv\Scripts\python -m ota_verifier.cli examples/parallel_campaign.json --max-parallel 2 --stress-test
```

The demo executes one nominal run and **42 single-fault runs** (14 for each of
three updated ECUs). It deliberately has no rollback downgrade authorizations.
The nominal run passes; the stress report contains violations for blocked
rollback paths and boot failures. CLI exit code **4** means observed invariant
violations, not a crashed command or failing pytest test. The JSON retains all
traces, exact fault specifications, recovery evidence, and source-linked findings.

Stress mode adds exit code **5** for an inconclusive result. A report with both
violations and inconclusive cases reports violations; individual cases retain
inconclusive status. Normal planning behavior and exit codes are unchanged.
`--max-recovery-states` sets the deterministic recovery-search bound (default
10000). No LLM, credentials, network, or solver calls are required by the simulator
or recovery API; the CLI still uses Z3 first to obtain a nominal plan.

```python
from ota_verifier.simulator import simulate_plan, stress_test
from ota_verifier.simulation_models import FaultSpec, SimulationOptions

# campaign and result.plan are obtained using the planning example above.
nominal = simulate_plan(campaign, result.plan)
faulted = simulate_plan(
    campaign, result.plan,
    FaultSpec(ecu_id="gateway", stage="write", kind="power_loss"),
)
report = stress_test(campaign, result.plan, SimulationOptions(max_recovery_states=10000))
```

The public simulation API rejects invalid plans and unsupported fault boundaries.
It checks the original state, every stage/fault/halt transition, and each executed
recovery action. Findings retain trace indices, invariant names, ECU IDs, and
constraint evidence where applicable. Successful recovery never removes an
invariant violation already observed earlier in the run.

### Explicit flash and fault model

Each ECU executes erase at write start, write at the integer midpoint, then
verify, activate, and boot at its scheduled end. Even one-millisecond writes
erase before writing. Same-time completions execute verify/activate/boot in the
plan's activation order before new writes start. Intermediate slot contents are
represented as target-version images with `valid=false`; verification marks a
successful write valid. The old active image remains selected during writing.

| Injected fault | Boundary and effect |
| --- | --- |
| Power loss | Before and after all five stages: interrupts all in-progress writes, preserves persisted active pointers and already verified images, then stops the campaign. |
| Write corruption | After write: records corruption, continues until verification detects it, and blocks activation. |
| Verification failure | Before verify: the unverified target is not activated. |
| Activation failure | Before activation: the old active pointer is retained and the verified inactive target is preserved. |
| Boot failure | Before boot, after activation: the selected target is marked unbootable. This is an observed bootability violation, even if fallback later repairs it. |

Every failure cancels other in-progress writes and future scheduled events.
The affected inactive images remain invalid. Completed valid writes are not
silently erased. Power-loss recovery assumes power has returned with the same
supplied battery/ignition values; elapsed outage/reboot time is not modeled.
There is no physical byte-level flash, network transfer, battery drain, corrupted
metadata, damaged original slot, or simultaneous multi-fault model. Before/after
stage injection is finite model coverage, not an assertion of all real fault
conditions or continuous-time behavior. `valid` is simulated integrity/bootability
data, not cryptographic or hardware verification.

### Recovery policy and the four invariants

Recovery explicitly targets **the campaign's original active slots and versions**.
A compatible partial-update safe stop does not satisfy this stronger selected
rollback goal. Inactive contents need not match their initial contents.

1. Selected active images must be bootable.
2. Every observed active-version configuration must satisfy `compat.py`.
3. Installing a newly verified older image or activating an older retained image
   needs an authorization for that ECU and numeric destination version.
4. A failed step needs a proven safe, authorized slot-switch path to the original
   active images.

The planner and simulator share the version-change permission policy in
`policy.py`. Existing old inactive images are not newly installed images, and
returning to an original *newer* image after an authorized downgrade is an
upgrade. Returning to an original older image has **no implicit permission**.
Synthetic input may explicitly include, for example:

```json
"downgrade_authorizations": [
  {
    "ecu_id": "gateway",
    "version": "1",
    "authorized_by": "simulation-reviewer",
    "reason": "Explicitly permit restoring this original image in the demo"
  }
]
```

This permission is scoped to the gateway and version 1. It does not authorize
other ECUs or versions, bypass compatibility, or hide boot failures.

`recovery.find_recovery` performs bounded breadth-first search over existing
valid A/B images. Every successor must be fully bootable, compatible, and
version-authorized. It returns a shortest path when available. For example, the
recovery-trap benchmark requires restoring the brake before the gateway; a local
gateway-only fallback is rejected by the same compatibility checker as planning.
No new images are invented, downloaded, repaired, or flashed during recovery.
Recovery switches are logical transitions at the failure timestamp and are not
subject to the nominal flash-duration deadline or mutex write intervals.

Recovery results distinguish a proved unavailable path from a search limit:

- `available`: a replay-validated action sequence and all intermediate states.
- `unavailable`: exhaustive search proved no path under these rules; rejected
  candidates and their blockers are diagnostic evidence, not executed actions.
- `unknown`: the state bound was exhausted; the run is inconclusive unless an
  invariant violation was already observed. Unknown is never presented as proof
  of a missing rollback path or as a pass.

`SimulationResult.status=failed` means the injected fault aborted the campaign.
Its separate `assessment=passed` means the checked invariants held and the chosen
rollback goal was reachable despite that expected abort. Boot-failure injections
intentionally demonstrate the strict bootability invariant being violated in
this model; even fully authorized recovery cannot make those historical cases
pass. A complete nonempty sweep therefore includes those negative cases.
No-op campaigns have a nominal run and zero fault cases, reported explicitly.

Run Phase 3 tests only:

```powershell
.\.venv\Scripts\python -m pytest -q tests/test_invariants.py tests/test_recovery.py tests/test_exhaustive_recovery.py tests/test_simulator.py tests/test_simulation_models.py tests/test_stress_cli.py
```

Phase 3 tests include parallel interruptions, all fault boundaries, retained
slots, delayed corruption detection, blocked/authorized rollback, historical
findings, recovery search limits, report integrity, round-trip serialization,
CLI behavior, and deterministic isolated runs. Sixteen small recovery scenarios
are compared with an independent exhaustive A/B state graph and all-pairs
shortest-path oracle. This checks recovery availability and shortest path length.

## Phase 4: evidence-linked document extraction

Extract constraints from release notes and ECU documentation through one
`llm/client.py` abstraction, then apply strict schema/provenance checks and a
separate faithfulness review. Ambiguous, unsupported, malformed, or unverified
extractions block automatic planning. Inventory, target versions, and downgrade
permissions remain authoritative structured input.

Try a complete offline demo using explicitly labeled canned responses:

```powershell
.\.venv\Scripts\python -m ota_verifier.documents_cli examples/documents/clear-0.case.json --fixture --plan --max-parallel 2
.\.venv\Scripts\python -m ota_verifier.documents_cli examples/documents/ambiguous-4.case.json --fixture --plan
```

The first reaches planning; the second stops with review findings (exit 6).
Fixture responses are not live model evaluations. To exercise ground-truth
metrics and deliberately reveal correlated extraction/reviewer errors:

```powershell
.\.venv\Scripts\python eval/run_eval.py --mode fixtures
.\.venv\Scripts\python eval/run_eval.py --mode fixtures --profile false_approval --fail-on-false-acceptance
```

The second command intentionally exits 4 after detecting unsafe handoffs against
hidden ground truth. Actual live evaluation is opt-in with `--mode live` and
requires `.env`/environment configuration. Set `LLM_PROVIDER` to `ollama`, `gemini`,
or `groq`, and configure an actual `LLM_MODEL`. Core and fixture tests need no
live services. Developer evaluation-profile tests use isolated dummy settings; optional external-reference
verification is described in the setup qualification above. The verifier can use
`LLM_VERIFIER_MODEL` if configured.

Run records retain exact documents and character spans, hashes, prompts and
versions, provider/model identity, raw responses, validated constraints, and
review findings. API keys and HTTP headers are excluded. The deterministic core
continues to run without any LLM calls.

See [the Phase 4 guide](docs/phase4.md) for provider configuration, evidence
semantics, evaluation definitions, saved-run validation, and explicit limits.

## Phase 5: local review workspace

Launch the Streamlit app after installing `.[dev]`:

```powershell
.\.venv\Scripts\python -m streamlit run app/streamlit_app.py
```

Open `http://localhost:8501`. Offline fixtures are selected by default; click
**Analyze revision** to run the checkpointed workflow without credentials.
The screen shows source evidence, a parallel flash timeline, activation states,
fault traces, recovery paths, advisory explanations, and human review.

LangGraph pauses before the human-review node using `MemorySaver` and
`interrupt_before`. Review decisions bind to an exact run/revision/snapshot hash.
Changes require reanalysis and invalidate the prior active decision; history
remains available. Rerenders and repeated review submissions do not repeat
completed analysis or model calls. Download a JSON review bundle to retain all
source, analysis, explanation, and decision evidence.

A feasible plan can still have stress violations. **Review with findings** does
not turn violations into a pass, and approval is unavailable for blocked,
infeasible, unknown, or failing analysis. The **No updates (approval demo)**
example explicitly has zero update/fault steps; it demonstrates review plumbing,
not fault tolerance of a nonempty campaign.

Configured-provider mode runs only on explicit analysis submission and uses the
same provider abstraction, with optional `LLM_EXPLAINER_MODEL`. Explanation errors
fall back to deterministic summaries. No vehicle execution or deployment exists.
The default memory checkpoints live only in the current process/browser session.
Phase 7 adds an optional SQLite workspace for restart recovery; JSON exports
remain evidence downloads rather than executable checkpoint imports.

See [the Phase 5 guide](docs/phase5.md) for the state graph, exact review policy,
headless API, explanation limits, and test commands.

## Phase 6: compare boot policies

In the local app, load **Authorized rollback comparison**, enable **Compare
guarded trial boot**, then click **Analyze revision**. The **Faults** view pairs
baseline and guarded traces, shows image integrity separately from boot health,
and displays confirmed slots, trial candidates, and actual availability.

The example has explicit synthetic rollback permissions. It compares **42 shared
fault cases** and adds **6 guarded-only confirmation cases**. Three boot-failure
outcomes improve: the unchanged baseline retains violations while the guarded
policy passes its complete 48-case sweep under the stated assumptions. Missing
permissions, incompatible fallback, and availability cycles still produce blocked
recovery or violations; search limits remain inconclusive.

For a headless comparison:

```powershell
.\.venv\Scripts\python -m ota_verifier.cli examples/authorized_boot_campaign.json --compare-boot-policies --max-parallel 2
```

Exit 4 is expected because the baseline still has violations. Comparison results
never overwrite the legacy baseline review gate. Phase 9 separately allows an
explicitly selected guarded policy in a new versioned workflow revision. Options
and complete comparison evidence are bound to the review snapshot; changes
require a new revision.

A candidate becomes effective only after a successful health check. Rejecting a
never-effective candidate retains the old version; returning to an older image
after successful exposure still needs explicit authorization. Confirmation is
modeled as atomic durable metadata, and rebooting ECUs are explicitly unavailable.
Durability here concerns simulated power loss, not Python-process persistence.

See [the Phase 6 guide](docs/phase6.md) for exact semantics, coverage, the negative
cold-start example, APIs, and verification evidence.

## Phase 7: persistent runs and review history

In the Streamlit sidebar, open **Persistent run library** and then **Open SQLite
workspace** to save future analyses in `.ota_state/reviews.sqlite`. Reopen saved
runs after a restart, explicitly resume incomplete analysis, and inspect prior
revisions and implementation versions. Default sessions still use memory.

Completed model outputs are reused; uncertain requests require an explicit new
revision. Decisions bind to the current evidence hash and are committed
transactionally. Reviewer identities remain self-reported in this local tool.

See [Phase 7 usage and recovery rules](docs/phase7.md). Phase 7 completes the
current local portfolio milestone. [The next-phase roadmap](docs/roadmap.md)
records completed evaluation/reproducibility and explicit policy selection.
Optional shared review and operational controls are implemented in Phase 10;
Phase 11 records release evidence and Phase 12 adds MCUboot comparison.


## Phase 8: reproducible benchmark evidence

Run the frozen deterministic and reference-fixture benchmark:

```powershell
.\.venv\Scripts\python -m ota_verifier.benchmark.runner --mode fixtures --split all --fail-on-findings --output runs/my-benchmark.json
```

The corpus contains 11 deterministic campaigns and 12 extraction cases with
separate development and held-out wording. Reports include per-type semantic
precision/recall, exact citation metrics, schema rejection, faithfulness false
acceptance, latency, provider configuration, and version fingerprints. Fixture
scores are scripted harness checks, not live-model accuracy. Use `--mode core`
for the deterministic benchmark alone; live evaluation requires explicit
`--mode live` and configured credentials.

See [Phase 8 methodology and commands](docs/phase8.md) and the recorded
[reference baseline](eval/baseline_v1.json). Offline CI is configured for
Python 3.11-3.14 on Windows and Linux; only Windows/Python 3.14 has been verified
locally. Correctly detecting an expected campaign violation counts as a passing
benchmark check, never approval of that campaign.


## Phase 9: choose the policy under review

In the Streamlit sidebar, select **Policy to review** before analyzing. Choose
**Baseline policy** or **Guarded trial boot policy** to create policy-specific
`workflow-v2` / `review-bundle-v2` evidence. **Legacy baseline review** retains
the earlier gate and export schema.

For **Authorized rollback comparison**, selecting guarded trial boot produces a
passing guarded assessment while retaining all baseline violations. Only an
explicit human decision can approve that selected simulation proposal. Switching
policy or changing trial options requires a new revision and invalidates the
prior decision's applicability. Missing permissions, regressions, unknowns, and
incomplete selected-policy coverage still block approval.

See [Phase 9 review rules and API](docs/phase9.md). Optional shared review and
operational controls are described in Phase 10 below.


## Phase 10: optional shared review and operational controls

Local mode remains the default offline demo. Optional single-host shared mode
uses Streamlit OIDC login and an operator-controlled issuer/subject allowlist.
Reader, analyst, reviewer, and admin roles are enforced at the service boundary;
reviewer identity and provenance commit atomically with the human decision.
Shared mode requires a deliberate schema migration and protected configuration.

Verified SQLite backup/restore includes WAL commits, revisions, review history,
authentication metadata, and checkpoints. Reviewed runs can be archived read-only
without deleting evidence. Portable exports have content identifiers; authenticated
exports retain provenance separately from historical self-reported identities.

Follow [Phase 10 setup, maintenance commands, and limits](docs/phase10.md).
Login and UI authorization are tested with mocked verified identities; an actual
identity-provider login and network deployment have not been exercised. The
checked-in server stays on loopback. Phase 12 separately validates bounded
recovery observations against MCUboot.


## Phase 11: release validation and portfolio evidence

Generate a new offline release evidence pack:

```powershell
.\.venv\Scripts\python -m ota_verifier.release_validation --output runs/my-release
```

It contains the three demo review bundles, the fixture benchmark, verified
migration/backup/restore artifacts, receipt-reuse checks, and an artifact hash
index. Proposals remain awaiting human review. External CI and live OIDC gates
remain explicitly pending, as agreed for this milestone.

[Phase 11](docs/phase11.md) documents verification, remaining setup, and release
criteria. [Architecture](docs/architecture.md) explains the model boundaries;
[the demo walkthrough](docs/demo_walkthrough.md) includes the presentation script
and instructions for regenerating the real browser screenshots and recording.


## Phase 12: MCUboot recovery validation

The MCUboot extension follows the original eleven project phases. Its archived
reports use the workstream labels **1A-1E**; here they are **12A-12E** to avoid
confusing them with the original domain-model Phase 1. Evidence filenames and
historical reports retain their original identifiers.

| Subphase | Completed work | Engineering record |
| --- | --- | --- |
| 12A | Repository audit, reference selection and model-gap analysis | [Validation plan](docs/MCUBOOT_VALIDATION_PLAN.md) |
| 12B | Executable official MCUboot reference and actual C observations | [Reference environment](docs/MCUBOOT_REFERENCE_ENVIRONMENT.md) |
| 12C | Independent twelve-scenario comparison | [Differential findings](docs/MCUBOOT_DIFFERENTIAL_VALIDATION.md) |
| 12D | Evidence-backed policy distinction and regression guards | [Model refinement](docs/MCUBOOT_MODEL_REFINEMENT.md) |
| 12E | Unified runner, full regressions and independently verifiable packages | [Final engineering report](docs/MCUBOOT_VALIDATION_REPORT.md) |

An independent harness compares the guarded recovery simulator with real MCUboot
v2.4.0 C bootloader code running over simulated flash. Phases 12A-12E are complete.
The reference is pinned to commit
`6d3b3d2c38ab20c242e5b9abb04d050086383eb2`, using scratch swap,
RSA-2048/SHA-256 and primary-slot validation in the official simulator under WSL2.

| Differential result | Scenarios |
| --- | ---: |
| MATCH — bounded observable endpoints | 6 |
| MISMATCH — intentional campaign-policy differences | 2 |
| UNSUPPORTED — mechanism or interruption boundaries differ | 4 |
| INCONCLUSIVE | 0 |

The mismatches preserve explicit downgrade authorization and the campaign's
original-image recovery objective. Unsupported cases remain unsupported;
matching endpoints do not establish signature verification, scratch-journal
recovery or application-health equivalence. No production simulator defect was
identified, and its behavior was preserved. This is software simulation evidence,
not full MCUboot equivalence, hardware or real-vehicle validation.

Recorded Phase 12E runs (each with 0 failures/errors/skips and 14 warnings):

| Run | Native evidence | Python tests passed | Artifact hashes verified |
| --- | --- | ---: | ---: |
| [Fresh execution](validation/mcuboot/final_evidence/phase1e-fresh/validation.json) | Real C tests executed again | 582 | 58 |
| [Evidence replay](validation/mcuboot/final_evidence/phase1e-replay/validation.json) | Historical C logs; no fresh native execution | 586 | 50 |

The replay run includes four status-guard tests added after the fresh run.
Warnings and JUnit results are retained in each package; unsupported scenarios
are not counted as successful validations.

After the [reference environment setup](docs/MCUBOOT_REFERENCE_ENVIRONMENT.md),
run from this directory in PowerShell:

```powershell
# Build/test real MCUboot, compare both implementations, review policies and run regressions.
.\.venv\Scripts\python.exe validation/mcuboot/validate.py --mode fresh

# Reuse recorded native evidence; Python simulation and regression tests still execute.
.\.venv\Scripts\python.exe validation/mcuboot/validate.py --mode replay

# Verify the recorded fresh package, including its consolidated report.
.\.venv\Scripts\python.exe validation/mcuboot/validate.py --verify validation/mcuboot/final_evidence/phase1e-fresh/validation.json
```

New runs use separate timestamped evidence directories. See the
[engineering report, complete scenario table and Windows/WSL2 reproduction guide](docs/MCUBOOT_VALIDATION_REPORT.md)
for methods, raw evidence, limitations and remaining gaps.

## Phase 13: scalability and live LLM evaluation

This workstream extends the original workflow with measured solver workloads,
source-grounded extraction evaluation and retained reliability failures. The
13A-13C headings below are README navigation groups for the recorded work, not
additional official historical milestones. Reports retain their original
"Phase 2" workstream filenames.

### 13A: Z3 scalability benchmarking

The primary study executed **600 Z3 trials** across fixed-seed synthetic
10/30/50/100-ECU workloads: **225 feasible, 180 infeasible, 180 unknown and 15
watchdogs**. The greedy sequential baseline returned 420 valid schedules and
180 no-schedule outcomes. Solver timeout and watchdog results remain unresolved
outcomes, not infeasibility proofs. No feasible schedule was returned for the
primary positive 100-ECU cases, so large-scale scheduling success is not claimed.

The historical Windows parent monitor observed a venv launcher rather than the
worker interpreter. Parent memory readings and soft-limit enforcement are
unreliable; worker-reported self-peaks remain recorded. The monitor correction
was checked separately, without rerunning the complete primary matrix.

[Scalability methods and results](docs/PHASE2B_SCALABILITY.md) |
[Evidence audit](docs/PHASE2B_EVIDENCE_AUDIT.md) |
[Consolidated evaluation through the original real pilot](docs/PHASE2_EVALUATION_REPORT.md)

### 13B: reviewed datasets and synthetic Groq pilot

The owner approved three frozen synthetic development cases and their exact
source evidence. This was not independent automotive-domain expert validation.
Groq `openai/gpt-oss-20b` made **four successful HTTP 200 requests**, with no
retries and **12,170 reported tokens**.

Semantic precision, recall and F1 were **100% on five expected rules**, but
correct rule-to-evidence grounding was only **3/5 (60%)**, and complete expected
workflow outcomes were **1/3**. The two opposing order rules carried swapped
citations: their aggregate meanings matched while their individual evidence did
not. A false faithfulness rejection with an invalid issue-reference usage and
premature conflict blocking also remained visible. No case reached Z3.

These are synthetic development measurements, not independent real-world
accuracy. The frozen pilot was preserved through subsequent repairs and retests.

[Synthetic pilot results and approval](docs/PHASE2C_PILOT_REPORT.md) |
[Dataset review methodology](docs/DATASET_REVIEW_GUIDE.md)

### 13C: real-document evaluation, reliability and final retest

Five owner-reviewed embedded-firmware development cases covered a Flysky update
order, a narrow ExpressLRS version exclusion, two unsupported requirements and a
descriptive MCUboot statement. The corpus contains **two positive formal rules**;
it is not an automotive ECU accuracy benchmark or a held-out study.

| Measurement | Original incomplete pilot | Final bounded retest |
| --- | --- | --- |
| Cases | Five approved; three attempted, two NOT_RUN; two usable extraction drafts | All five attempted; five usable drafts |
| Groq requests | Four: three HTTP 200, one HTTP 400 | Eight: all HTTP 200; zero retries |
| Reported tokens | 6,337 across successful requests; failed-request usage unknown | 18,022 across all eight requests |
| Semantic precision / recall / F1 | 100% / 50% / 66.7% | 100% / 100% / 100% |
| Grounding precision / recall | 100% / 50% | 100% / 100% |
| Complete expected outcomes | 0/3 attempted cases | 4/5 |
| Planner handoff | No case reached Z3 | Two feasible zero-step plans |
| Persistent failure | False Flysky rejection; omitted exclusion; JSON-completion failure | Flysky false faithfulness rejection remains |

Reliability changes added bounded source-direction checks, clearer verifier
reference/disagreement diagnostics, generic fixed-version exclusion instructions
and a finite 4,096-completion-token retest profile. General variable-to-variable
major-version matching remains unsupported. Unresolved judgments stay blocked;
valid citations do not automatically approve a draft. No product-specific gold
answers were hardcoded, and historical predictions were not repaired in place.

The final retest used `extract-v3` / `verify-v3` and `openai/gpt-oss-20b`, with
serial rate-limit pacing and a ten-request ceiling. Flysky extraction and its
source evidence were correct, but the live verifier still incorrectly rejected
the direction. The ExpressLRS exclusion, unsupported controls and descriptive
control achieved their expected outcomes. No provider completion failure
occurred in the retest; the original HTTP 400 remains retained.

**The two feasible Z3 results were zero-step plans:** current and target versions
were equal in the approved synthetic inventory scaffolds. They establish a
verified handoff to the planner, not nonempty firmware-update scheduling or
operational compatibility validation. Overall workflow reliability is not 100%.

The pilots have different attempted-case coverage and changed prompts/token
configuration. They are not equivalent statistical samples, and the results do
not isolate which change caused an improvement. On the two cases with usable
extractions in both runs, the exclusion improved while Flysky's rejection
persisted. Do not pool synthetic and real-document scores.

[Original real-document pilot](docs/PHASE2C_REAL_DOCUMENT_PILOT.md) |
[Initial reliability review](docs/PHASE2C_RELIABILITY_REVIEW.md) |
[Final offline repairs](docs/PHASE2C_FINAL_RELIABILITY_REPAIR.md) |
**[Final versioned comparison and evidence](docs/PHASE2C_FINAL_RETEST_COMPARISON.md)**

The final comparison records **274 passing targeted regressions**, with zero
failures/errors and 13 dependency warnings, plus verified prior-pilot/corpus and
new evidence hashes. This count does not replace the historical broad 760-test
run. Further independent evaluation and the persistent verifier failure remain
limitations; no additional live evaluation is implied as complete.

## Phase 14: standards-concept engineering evidence

A tested deterministic exporter assembles versioned JSON and Markdown evidence,
a strict schema and SHA-256 manifests. It connects source sentences and spans to
inventory, compatibility states, planning, simulated faults, rollback findings
and the recorded human-review status. Missing review is explicit; exporting a
package never creates approval or removes violations. Existing-artifact hash
references do not masquerade as fresh MCUboot execution.

The mapping relates these artifacts to **UNECE R156 and ISO 24089 engineering
concepts**, including software/configuration identification, dependency
traceability, failure/restoration records and decision accountability. It is a
proposed concept traceability matrix, not a verified normative-clause checklist.
Detailed R156 text was not verified in the recorded research, and full licensed
ISO normative text was not used. Human normative review and organizational
evidence remain incomplete.

The sample retains **26/28 passing fault cases and two genuine bootability
invariant violations**, with missing human approval clearly recorded. Hashes
check consistency relative to a trusted manifest; they are not digital
signatures or proof of source truth. The exporter does not establish regulatory
compliance, certification, production safety or hardware assurance.

[Phase 14 concept mapping, tests and reproduction](docs/PHASE3_STANDARDS_EVIDENCE_REPORT.md) |
[Sample engineering evidence](examples/engineering_evidence_v1/report.md)

## Verification approach

Phase 1's 69 regression tests remain included. Phase 2 tests cover parallel
speedup, capacity, mutex groups, order, environment boundaries, downgrades,
unchanged ECUs, invalid active images, endpoint and intermediate incompatibility,
conflict evidence and subset minimality, result serialization, altered-plan
rejection, CLI behavior, and interrupted solver operations.

Twenty-four reproducible tiny campaigns are checked against exhaustive
start-time and activation-order enumeration, comparing both feasibility and
optimal duration. These cases use integer-minute durations and deadlines; for
a fixed ordering their integer difference bounds admit a lattice optimum.
This provides an independent scheduling oracle for those cases, not an
exhaustive validation of arbitrary campaign sizes or real systems.

The five hand-authored benchmarks in `tests/fixtures` remain:

| Fixture | Expected result |
| --- | --- |
| `compatible.json` | Compatible initial, intermediate, and target states. |
| `order_sensitive.json` | Gateway activation first works; brake activation first violates its dependency. Writes can still overlap. |
| `impossible_direct.json` | Compatible endpoints, but either first single-ECU activation fails. Parallel writes do not resolve this. |
| `recovery_trap.json` | Reverting the gateway alone breaks the updated brake dependency. |
| `invalid_input.json` | Validation rejects an unknown dependency ECU. |

## Remaining work and boundaries

Remote CI and live OIDC checks remain pending in the recorded release evidence.
Phase 13 records actual scalability trials and bounded live development pilots,
including the final five-case retest and its persistent false verifier rejection.
Broader independent accuracy, nonempty real-document update schedules, and
successful primary positive 100-ECU scheduling remain unestablished. Phase 14's
exporter is tested, while normative and organizational review remains incomplete.
The linked readiness/consolidation reports retain their dated earlier snapshots;
the final retest comparison is the later record for LLM evaluation results.
The project remains a simulation: selected endpoint agreement does not establish
full bootloader equivalence, hardware or real-vehicle validation. No production
readiness or regulatory-compliance claim is made.
