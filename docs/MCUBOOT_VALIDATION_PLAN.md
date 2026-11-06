# MCUboot recovery validation plan

Audit date: 2026-11-06. Scope: Phase 1A, repository inspection and official-source research.

Follow-up: Phase 1B was subsequently approved and executed. See [the executable environment report](MCUBOOT_REFERENCE_ENVIRONMENT.md) for actual results. Approval/status statements below retain the original Phase 1A audit context; Phase 1C remains unstarted.

**Status: audit complete; executable validation has not started. User approval is required before Phase 1B.** No MCUboot checkout, build, executable run, reference logs, or comparison results are delivered by this document. Commands and artifacts described below are future work. Production code is unchanged.

OTA Campaign Verifier remains a simulation. The proposed work evaluates bounded recovery behavior against an open-source bootloader implementation; it does not establish real-vehicle suitability or certification.

## 1. Existing architecture and audit scope

The repository contains two deterministic boot policies over immutable Pydantic campaign and vehicle records. Z3 produces a parallel-write schedule with serialized activation. Both planning and invariant checking use the shared compatibility rule in `compat.py`. Recovery searches existing images rather than manufacturing replacement firmware. LLM-assisted extraction, extraction verification, and explanation remain outside those decisions.

Paths in the inventory are relative to the repository root. Public entry points and their supporting transitions were inspected, together with the corresponding test modules and workflow documentation.

| Area | Implementation and responsibility |
| --- | --- |
| Firmware and vehicle records | `src/ota_verifier/models.py`: `Image`, `ECU`, `ECUState`, `VehicleState`, `Campaign`, constraints, and exact ECU/version downgrade authorizations. An image contains a version and Boolean validity, not firmware bytes. |
| Logical slots | `ab.py`: `slot_image`, `with_image`, `select_slot`, `original_images_active`. Selection changes an A/B pointer. Recovery's goal includes the original slot identity, version, and validity; inactive contents need not return to their original values. |
| Versions and policy | `versions.py` parses numeric versions/specifications; `policy.py` authorizes older destinations explicitly. `invariants.check_transition` checks both activation and newly valid installed images. A preexisting older inactive image is not itself a new installation. |
| Compatibility and planning | `compat.py`, `planner.py`, `scheduling.py`: shared requires semantics, Z3 scheduling, intermediate compatibility, mutex/precondition/order checks, concrete plan replay, timeout/unknown handling, and conflicting constraint evidence. Writes may overlap; activations are ordered. |
| Baseline simulation | `simulation_models.py`, `simulator.py`: `FaultSpec`, result/trace records, `enumerate_faults`, `simulate_plan`, `stress_test`, `_timeline`, `_execute`, `_inject`, `_failed`. |
| Baseline invariants and recovery | `invariants.py`: `check_state`, `check_transition`, `check_recovery_path`; `recovery.py`: `find_recovery`. Breadth-first search switches existing slots through compatible, authorized states. A bounded search can return unknown rather than falsely claiming no recovery. |
| Guarded boot state | `boot_models.py`: `BootMetadata`, `GuardedSnapshot`, options/results and recovery records. `boot.py`: `initial_boot_state`, `power_loss`, `guarded_boot`, `confirm_current`, `check_guarded_state`. Tracks confirmed/candidate/running slots, availability, health, and attempts. |
| Guarded execution and recovery | `guarded_simulator.py`: `enumerate_guarded_faults`, `simulate_guarded`, `stress_guarded`, `_restore_confirmed`, `_failed`. `boot_recovery.py`: `recovery_goal`, `find_guarded_recovery`, `check_guarded_recovery`. |
| Policy comparisons | `boot_comparison.py`: compares baseline and guarded policies on the same campaign, plan, options and shared fault cases; additional confirmation cases remain explicit. These reports are internal-policy comparisons, not MCUboot observations. |
| Workflow and evidence | `graph.py`, `workflow_models.py`, `workflow_examples.py`, `evidence.py`, `llm/`: orchestration, selected-policy review evidence, extraction/verification/explanation, human review. A reference harness must not silently change approval eligibility or reinterpret existing reports. |
| Interfaces and durable review | `app/`, `review_app.py`, `review_views.py`, `boot_review.py`, `persistence_review.py`, `shared_review.py`, `public_demo.py`, `persistence/`, `access.py`, `shared.py`: Streamlit, fixtures, SQLite, receipts, identity and review access. Database/process durability is separate from bootloader flash metadata. |
| Generation and evaluation | `data/`, `benchmark/`, `eval/`, CLI entry points, release validation, scripts and deployment/docs: campaign generation, deterministic evaluation, evidence presentation and release checks. They are supporting infrastructure, not embedded execution environments. |

### Baseline transitions and fault boundaries

`_timeline` creates erase at write start, write at an integer midpoint, then verify, activate and boot at completion. Finishing events precede new starts at the same timestamp; activation order resolves completion ties.

1. Erase marks the inactive target invalid and starts a write.
2. Write is a logical event, without byte programming.
3. Verify marks the staged image valid unless a corruption/verification fault prevents it.
4. Activate selects the verified slot.
5. Boot completes a logical stage; no application instructions execute.

There are 14 injected cases per updated ECU: power loss before/after all five stages, plus write corruption after write, verification failure before verify, activation failure before activate, and boot failure before boot. One fault is injected per run. Power loss invalidates every concurrent write. Baseline boot failure marks the already-selected active image invalid. Failed runs halt the campaign and search for recovery to the original active images, retaining historical invariant violations even after successful recovery.

### Guarded transitions and fault boundaries

The guarded timeline adds confirmation, giving 16 cases per updated ECU. Activation makes the ECU unavailable and records a candidate. Boot attempts check image validity and health; only a successful health check makes the candidate effective. Dependent boots are blocked when their required ECU is unavailable. Confirmation atomically changes the durable confirmed selection. Nominal execution confirms automatically after boot.

Power loss clears running/candidate selections and makes all ECUs unavailable while retaining confirmed metadata and the last effective versions. `_failed` clears candidates, tries persisted confirmed selections through `_restore_confirmed`, then searches for an authorized compatible path to the original images. It executes proven recovery actions and checks that replay matches the recorded proof. Boot-health failure and image integrity are separate in this policy. Attempts are simulated within a run, not measured from real application resets.

### Existing tests relevant to the comparison

| Tests | Established project behavior |
| --- | --- |
| `test_models.py`, `test_versions.py`, `test_simulation_models.py` | Record validation, slot/version consistency and legal fault specifications. |
| `test_planner.py`, `test_exhaustive_planner.py`, `test_plan_validation.py` | Parallel schedules, intermediate compatibility and independent replay. |
| `test_simulator.py` | Parallel inactive writes, completion ordering, all concurrent writes affected by power loss, corruption detection, activation failure, retained boot-failure history, authorized recovery and complete bounded sweeps. |
| `test_invariants.py` | Invalid active images, shared dependency checks, install/activation downgrade authorization, and rejection of forged recovery evidence. |
| `test_recovery.py`, `test_exhaustive_recovery.py` | Original-slot goal, recovery ordering/traps, permission combinations, absent/invalid image handling and unknown on search limits. |
| `test_guarded_boot.py` | Effective trial before confirmation, failed trials retaining the old version, confirmation power-loss boundaries, durable selections, availability, health/integrity separation, attempt budgets and no LLM/replanning calls. |
| `test_exhaustive_guarded_recovery.py` | Guarded recovery compared with an exhaustive availability graph. |
| `test_boot_comparison.py`, `test_boot_cli.py`, `test_boot_workflow.py`, `test_boot_review_app.py`, policy-selection tests | Same-input policy comparisons, inconclusive results, evidence integrity and presentation/review behavior. |

These tests validate the project's own contracts. They are not evidence of agreement with MCUboot. No fresh test-suite pass count or MCUboot execution result is claimed by this documentation-only audit.

## 2. Selected reference implementation

Use **MCUboot v2.4.0**, commit **`6d3b3d2c38ab20c242e5b9abb04d050086383eb2`**, with the official Rust simulator in `sim/` executing the C bootutil library.

The official remote was queried during the audit with `git ls-remote`: the annotated tag object is `2a4733cc15dfb1ff2d4c0d08c0c13f1e621f863d`, and the peeled commit is the commit above. Verify both checkout HEAD and recursive submodule revisions during setup. Do not substitute `main`, a floating tag, or the current documentation website for this source snapshot. [Pinned source tree](https://github.com/mcu-tools/mcuboot/tree/6d3b3d2c38ab20c242e5b9abb04d050086383eb2).

| Setting | Selected value |
| --- | --- |
| Upgrade strategy | Swap using scratch; primary execution region, secondary staging region, separate scratch area. |
| Cargo features | `sig-rsa,validate-primary-slot`, with default features disabled. |
| Image authentication | RSA-2048 with SHA-256; upstream simulator test keys, explicitly test-only. No encryption. |
| Images | One image pair for one ECU; initial image 1.0.0+0, candidate 2.0.0+0. Fixture bytes and hashes must be recorded. |
| Primary checking | Enabled via `MCUBOOT_VALIDATE_PRIMARY_SLOT`. |
| Exclusions | No overwrite-only, move, offset, direct-XIP, RAM-load, multiimage, bootstrap, downgrade-prevention or hardware rollback-protection features. |
| Alignment/geometry | Simulator build's default maximum alignment is 8. Phase 1B must select one legal upstream flash geometry and pin actual programming alignment, sector layout, erased value, image capacity and scratch capacity separately. |

The pinned simulator build script selects scratch when alternate strategies are absent, maps these features to the C definitions, and compiles RSA support through mbedTLS. This is a deliberately bounded reference configuration, not a recommendation for deployment. [Feature definitions and C compilation](https://github.com/mcu-tools/mcuboot/blob/6d3b3d2c38ab20c242e5b9abb04d050086383eb2/sim/mcuboot-sys/build.rs), [Cargo features and dependencies](https://github.com/mcu-tools/mcuboot/blob/6d3b3d2c38ab20c242e5b9abb04d050086383eb2/sim/Cargo.toml).

### Strategy distinctions

Scratch swap preserves the former image while exchanging sectors through scratch; move and offset use different spare-space layouts and progress handling. Overwrite-only copies over the primary image and does not provide the same old-image test/revert contract. Direct-XIP selects executable images in place; RAM-load copies an image into RAM. Those alternatives are not interchangeable comparison targets. The project's pointer selection resembles an in-place abstraction, but that alone does not make it a direct-XIP implementation. The reference deliberately uses scratch swap to examine resumable copying and revert behavior. [Pinned design: upgrade strategies](https://github.com/mcu-tools/mcuboot/blob/6d3b3d2c38ab20c242e5b9abb04d050086383eb2/docs/design.md).

### Reference semantics and execution boundary

The public swap tables distinguish a pending test upgrade, a permanent upgrade, and an unconfirmed completed test upgrade requiring revert. Trailer magic, `image_ok` and `copy_done` participate in those decisions; application confirmation updates flash metadata. Confirmation is not a generic durable A/B selection pointer. [Swap decisions and public confirmation functions](https://github.com/mcu-tools/mcuboot/blob/6d3b3d2c38ab20c242e5b9abb04d050086383eb2/boot/bootutil/src/bootutil_public.c).

Image acceptance involves actual header/TLV, digest and signature processing. The RSA configuration expects RSA-2048-PSS signature data; a Python `valid` flag cannot establish cryptographic equivalence. [Image validation implementation](https://github.com/mcu-tools/mcuboot/blob/6d3b3d2c38ab20c242e5b9abb04d050086383eb2/boot/bootutil/src/image_validate.c).

Scratch swap has flash-resident progress handling that can be examined after interruption. [Scratch swap implementation](https://github.com/mcu-tools/mcuboot/blob/6d3b3d2c38ab20c242e5b9abb04d050086383eb2/boot/bootutil/src/swap_scratch.c).

The official simulator calls real C `context_boot_go`. Its C flash write/erase wrappers decrement an operation counter and interrupt **before** the selected operation through `longjmp`; this is not an arbitrary torn write inside an operation. It does not execute the selected application on a simulated CPU. A successful return establishes bootloader selection, not runtime application health. [Simulator invocation and interruption wrappers](https://github.com/mcu-tools/mcuboot/blob/6d3b3d2c38ab20c242e5b9abb04d050086383eb2/sim/mcuboot-sys/csupport/run.c).

## 3. State-transition comparison and model mismatches

| Transition/property | Existing simulator | MCUboot reference / comparison treatment |
| --- | --- | --- |
| Stage candidate | Inactive `Image(version, valid=False)`, then Boolean verification | Real signed image bytes in secondary; compare accept/reject outcome only after declaring the validity mapping. |
| Activate | Baseline pointer switch; guarded candidate and unavailability | Bootloader swap and selection; no direct equality of slot pointers or operation counts. |
| Trial image | Guarded health must pass before effective selection | Image is selected for handoff before application health can be established; health gating is a project abstraction. |
| Confirm | Atomic confirmed-slot update immediately after nominal boot | Explicit application-side confirmation metadata operation, followed by another boot to observe persistence. |
| Unconfirmed reset | Fault handling clears candidates and orchestrates recovery | Next boot can revert a completed unconfirmed test upgrade. Compare image identity at declared checkpoints, not internal transitions. |
| Interruption | Coarse before/after stages; no flash journal | Counter-based cuts before individual writes/erases; persisted progress supports swap continuation. |
| Invalid candidate | Boolean invalidity or verification failure | Rejection through real format/hash/signature checks. Separate corruption classes in fixtures. |
| Boot failure | Baseline invalidates active image; guarded records failed health | Bootutil cannot diagnose a later application crash. Withholding confirmation and resetting is a limited external approximation. |
| Original-image recovery | Requires original logical slot and authorized compatible switches | Old image returns to primary after revert; physical slot identity differs. Normalize by image bytes/hash and version. |
| Confirmed-image reset | Failure path still aims to restore campaign originals | Confirmed candidate ordinarily remains selected. Whole-run final-state equality would be misleading. |
| Downgrade | Explicit ECU/version permission, including rollback after a successful trial | Automatic unconfirmed revert is bootloader policy. Reference has no matching reviewer authorization concept. |
| Compatibility/availability | Fleet dependencies, unavailable peers, compatible intermediate states | Single-image bootloader reference has no vehicle-wide compatibility, ignition, battery or scheduling model. |
| Attempts and durability | Modeled health/attempt metadata and atomic confirmation | Do not assume a matching durable attempt counter or identical flash atomicity contract. |

Additional mapping rules:

- Use distinct names for logical project slots A/B and reference regions primary/secondary/scratch. Maintain image identities independently of their addresses.
- Restrict comparison fixtures to versions representable in MCUboot's header fields. Do not silently reuse all arbitrary-length project version tuples as binary image versions.
- A valid boot image and an available, healthy application are different observations. An unavailable ECU's retained effective version remains part of the project's compatibility model.
- Supply explicit original-version downgrade authorization in comparison fixtures that require it. Record this fixture policy; never grant it implicitly in production code. Add an unauthorized case classified as a policy difference.
- Baseline 14-case and guarded 16-case sweeps are not MCUboot flash-interruption coverage measures. Timing, write bandwidth, transport/download failures, sector wear, torn flash operations and repeated faults remain outside the initial comparison.

## 4. Supported and unsupported scenarios

All scenarios below are **planned, not executed**. Start with one ECU, compatible original/candidate images, a confirmed original, and recorded image/flash fixtures. Capture checkpoints before the project's automatic recovery can obscure the fault outcome.

| ID | Initial state and real-reference experiment | Existing-model counterpart and expected limit |
| --- | --- | --- |
| S1 | Original in primary, valid candidate in secondary; request test upgrade; boot; explicitly confirm candidate; boot again. | Nominal guarded run exposes trial then confirmation. Compare candidate selection and persistence; project currently has no independent subsequent-reset scenario driver. |
| S2 | Same fixtures; test boot; omit confirmation; invoke the next boot and observe revert. | Power loss before confirmation plus authorized original recovery is a partial counterpart. Automatic restoration is not proof of identical MCUboot reset semantics. |
| S3 | Cut before each supported flash write/erase during upgrade; retain flash, discard volatile context, invoke boot again. | Compare coarse stage-fault recovery at documented checkpoints only. A cut before staging and a cut during swap are different experiments. |
| S4 | Good original plus candidate with separately corrupted payload, hash/signature data, or malformed header; request upgrade and boot. | `write_corruption`/verification-failure cases establish abstract rejection. Record precise reference error and selected image; do not claim the project implements authentication. |
| S5 | Complete test selection, simulate an external application reset without confirmation; also exercise an applicable interrupted activation operation. | Guarded health failure is not an exact equivalent. Application crash detection and pre-handoff health checks are unsupported by this harness. Reuse S2 for the limited reset consequence. |
| S6 | Confirm candidate; discard volatile context; boot repeatedly using retained flash and inspect metadata. | Compare durable confirmation separately from full failed-run recovery. Expected mismatch: project recovery may intentionally restore originals after a post-confirmation fault. |
| S7 | Cut inside swap progress, resume with the same flash; record completed trial handoff; reset again without confirmation; separately interrupt revert. | Existing model has no scratch/status-journal state. Check shared endpoint properties where meaningful and report journal/resume behavior as reference-only coverage. |

Initially unsupported: real firmware instruction execution, watchdog/RTOS health monitoring, actual hardware power tearing, cryptographic key lifecycle, antirollback/security counters, encrypted images, direct-XIP/RAM-load/overwrite equivalence, multi-image atomic upgrades, multi-ECU coordination by MCUboot, and exhaustive arbitrary repeated faults. Invalidating both images can be a later negative case; a bootloader rejecting all images is not evidence that a valid fallback exists.

## 5. Proposed executable environment (Phase 1B, approval pending)

Use upstream `sim/` first, rather than adding Zephyr/QEMU and board builds immediately. Upstream documents Rust stable, recursive submodules and Cargo tests that compile MCUboot modules. Native Windows feasibility still needs a toolchain/build preflight; this audit does not establish that native compilation works. Use WSL2 only if an evidenced native toolchain/platform blocker makes it necessary. [Official simulator instructions](https://github.com/mcu-tools/mcuboot/blob/6d3b3d2c38ab20c242e5b9abb04d050086383eb2/sim/README.rst).

After approval:

1. Inspect available Git, Rust/Cargo and C compiler versions without altering the Python environment. Attempt the selected upstream build on Windows. If blocked, record the exact failure before choosing a documented WSL distribution/toolchain.
2. Create an isolated upstream checkout at the pinned commit; initialize and record recursive submodule commits. Preserve license/notice information.
3. Pin the Rust toolchain, resolved Cargo dependency lock, compiler and environment versions actually verified. Determine whether an upstream lock exists; if resolution is required, retain the generated lock and its hash. Do not describe broad Cargo version ranges as pinned dependencies.
4. Provide repeatable PowerShell setup/run scripts, plus WSL instructions only if used. Verify HEAD, lock/toolchain files and exact feature definitions before running. A proposed build invocation from `sim/` is `cargo test --locked --no-default-features --features sig-rsa,validate-primary-slot`; it requires an established lock first and is not yet a tested command here.
5. Enumerate actual tests and retain their execution counts. A misspelled Cargo filter can pass with zero tests; zero executed tests must fail the reference acceptance gate.
6. Add minimal observation instrumentation in an isolated wrapper/test around upstream APIs. Keep bootutil decisions unchanged; record every instrumentation patch and its hash. Upstream pass/fail output alone is insufficient for state comparison.
7. Produce one repeatable working test-upgrade/confirmation example with before/after flash state and raw command logs. Retain executable hash, feature/build records and evidence of the real C invocation.

If a real executable cannot be established, retain the attempted commands, errors and blocker report, and stop Phase 1B. Do not proceed using mocked outputs or a Python implementation of the documentation.

## 6. Independent comparison methodology (Phase 1C)

Add an isolated validation package, provisionally `validation/mcuboot/`, without changing planner, simulator, compatibility or approval contracts. Keep setup scripts separate from ordinary Python tests. New opt-in integration tests may skip with an explicit environment reason locally, but a required validation job must fail when the reference is absent or no real scenarios execute.

Each scenario manifest should identify source/configuration hashes, image identities and bytes, initial flash state, explicit authorization policy, stimulus sequence, reset count, cut operation index, expected checkpoints and supported comparison properties. Replay identical manifests deterministically. Distinguish actual bootloader operations from externally simulated application confirmation/reset stimuli.

Capture at every meaningful checkpoint:

- Primary/secondary/scratch contents or reproducible snapshots, image hashes and parsed versions.
- Raw trailer bytes plus decoded magic, image confirmation, copy completion, swap type and progress fields where available. Unsupported observations must be marked unavailable rather than inferred from a pass result.
- Bootutil return value, selected image/address, operation counter, interruption location, reset sequence, stdout/stderr and process exit code.
- Project campaign/plan/policy/options, full trace, failure checkpoint, authorization decisions, recovery proof and historical findings.

Build two independent adapters: one reads actual MCUboot observations; the other calls existing project entry points and reads traces. Neither may call an LLM or use MCUboot output to fabricate project predictions. Do not reuse project recovery as the reference oracle.

Compare normalized properties such as selected image identity, candidate rejection, unconfirmed-image revert and confirmed-image persistence. Report each property as **match**, **unexpected mismatch**, **documented abstraction/policy difference**, **unsupported**, **inconclusive**, or **not executed**. Retain the raw states behind every classification. Never count an unsupported property, missing executable or expected abstraction as a validated match. Whole-trace equality is inappropriate for physical swap versus pointer selection.

Preserve existing tests. Add adapter tests for image-versus-slot identity, omitted confirmation, authorization differences, metadata decoding, missing observations, zero executed tests, and nonzero reference failures. Run existing recovery tests and then the complete suite when executable integration code is added. Keep reference integration results separate from ordinary project unit-test counts.

## 7. Milestones and completion gates

| Milestone | Deliverables and gate | Current status |
| --- | --- | --- |
| 1A | Repository/source audit, exact MCUboot reference, mappings, scope and this plan; no production modifications. | Complete as documentation/research only. |
| User approval | Explicit approval to begin environment setup/build work. | Required; not granted by this document. |
| 1B.1 | Native preflight; reproducible checkout, feature manifest, dependencies/toolchain lock; documented WSL fallback only if needed. | Not started. |
| 1B.2 | Real bootutil execution, nonzero upstream tests, instrumented example and authentic versioned logs/snapshots. Stop on an unresolved executable blocker. | Not started. |
| 1C.1 | Independent manifests/adapters; S1, S2, S4 and S6 with property-level comparisons and explicit mismatches. | Not started. |
| 1C.2 | S3/S7 flash-operation interruption sweeps and bounded S5 approximation; raw evidence and coverage denominator. | Not started. |
| Review | Regression suite, reproducibility rerun, evidence report and documented remaining gaps. No expansion of deployment or safety claims. | Not started. |

Before advancing, review whether limitations warrant a later, explicitly approved simulator extension (for example, an event driver that can withhold confirmation across resets). Do not repair a documented difference merely to force a passing comparison. The first result should be an honest account of what the current model predicts correctly, what it abstracts, and what remains unvalidated.

## 8. Research entry points

The [official documentation site](https://docs.mcuboot.com/) and [official repository](https://github.com/mcu-tools/mcuboot) were consulted. The commit-pinned links above are the reproducibility references; website/main contents can change independently. No third-party behavioral implementation is used as the proposed oracle.
