# Research plan: formally checking multi-ECU OTA campaigns

**Status:** draft for author review, 2026-11-06. Baseline commit `0439e37`.
**Contains no experimental results for the paper.** Section 1.3 lists what was observed by
re-running existing code. Everything from section 4 onward is a proposal, and any expected
outcome is labelled as a hypothesis.

**Research question.** Can functional safety of a multi-ECU update campaign (version
dependencies, partial failure, rollback ending in a consistent state) be formally checked,
and do the model's predictions match real behaviour on a testbed?

**Bottom line.**

- The repo is a strong starting point, but it contains **no formal model** (no TLA+, UPPAAL or
  any other model-checker input).
- What it has is a tested executable semantics, a Z3 nominal planner, a single-fault simulator,
  and a differential harness against real MCUboot for **one ECU**.
- Contribution 4's method is therefore partly proven. Contributions 1 to 3 start from zero,
  though the semantics can be ported rather than invented.
- The largest risk is contribution 3: monolithic explicit-state checking will not reach 50 ECUs,
  so the paper depends on the abstraction argument in section 5.3.
- The second risk is circularity in contribution 4 (section 6, E5).

---

## 1. What the repo already does

### 1.1 Components relevant to the paper

| Area | Where | What it gives us |
| --- | --- | --- |
| Domain model | `src/ota_verifier/models.py`, `versions.py`, `compat.py` | ECUs, A/B slots, version specs, `requires` / `mutex` / `order` / `precondition` constraints, scoped downgrade authorizations |
| Nominal planner | `planner.py`, `scheduling.py` | Z3 schedule with ordered activation; every intermediate active-version state must be compatible; minimal conflict reports |
| Fault simulator | `simulator.py`, `simulation_models.py` | Deterministic A/B execution, one fault per run, 14 cases per updated ECU |
| Invariants | `invariants.py` | Four invariants: bootable image, compatible versions, authorized downgrade, rollback path |
| Recovery | `recovery.py` | Bounded BFS over slot switches back to the original images |
| Guarded policy | `guarded_simulator.py`, `boot*.py` | Trial boot, atomic confirmation, attempt budget, 16 cases per ECU |
| Oracles | `tests/test_exhaustive_*.py` | Independent small-state checks (2 to 3 ECUs) |
| Corpus | `benchmark/corpus.py`, `data/benchmark_v1.json` | 11 frozen hash-pinned campaigns, seed 42 |
| MCUboot differential | `validation/mcuboot/`, `docs/MCUBOOT_*.md` | Real MCUboot v2.4.0 C code over simulated flash, 12 scenarios, hashed evidence packages, fresh/replay labelling |

The LLM extraction, LangGraph review workflow, Streamlit app, SQLite persistence and OIDC layers
are engineering work that does not serve the research question. **Proposal: leave them out of the
paper and freeze them.** The deterministic core does not depend on them.

### 1.2 Conventions worth keeping

The repo already separates `MATCH / MISMATCH / UNSUPPORTED / INCONCLUSIVE`, never counts unknown as
a pass, labels replayed evidence, and hashes artifacts. These match your rules and carry over to
all new experiments.

### 1.3 Observed on 2026-11-06 (this machine, Python 3.14.4, z3-solver 4.16.0.0)

Commands were run with temp and cache output outside the repo. These are status checks, not paper
results.

| Check | Observed |
| --- | --- |
| `pytest -q tests` | 555 passed, 0 failed, 304.47 s |
| `benchmark.runner --mode core --split all --fail-on-findings` | exit 0; 11 of 11 campaigns pass their checks; 6 nonempty campaigns x 42 = 252 fault cases; corpus hash matches the pin |
| MCUboot report (recorded by you, not re-run by me; it needs the WSL native build) | 6 MATCH, 2 MISMATCH, 4 UNSUPPORTED, 0 INCONCLUSIVE |

The 555 differs from the README's 548 and the MCUboot report's 582. The report's run also included
the `validation/mcuboot` tests. The README figure is probably older, but I did not confirm that.
Do not quote any of these in the paper without regenerating them.

### 1.4 Problems found that affect the paper

Status after week 1: items 1, 2, 3, 6 and 7 are addressed in the repo. Item 1 stays open until a
push shows CI passing on GitHub. Items 4 and 5 remain open; they are handled by per-property
reporting and the week 8 campaign generator.

1. **CI has never run.** `.github/workflows/ci.yml` sits in the parent folder, outside the git root
   (`ota_verifier/`), so it is not in the GitHub repo. Its `working-directory: ota_verifier` would
   also be wrong once moved.
2. **Broken link.** The README links `docs/OTA_Campaign_Verifier_Project_Report.pdf`. Only the
   `.html` exists.
3. **The 252 fault cases are not 252 independent cases.** `core-parallel` and `core-rollback-trap`
   are built with identical arguments apart from ID and tags, so 42 cases are duplicates.
4. **The campaign-level verdict does not discriminate.** Every nonempty campaign reports `violations`
   because baseline `boot_failure` marks the active image invalid by construction (the README says
   so). Comparisons must be made per property, not per campaign.
5. **The corpus is tiny.** Benchmark campaigns have 3 ECUs and the guarded recovery oracle uses 2.
   Nothing has been run near 5 ECUs, let alone 50.
6. **`runs/` is git-ignored**, so it cannot hold the raw results your rules require. A tracked
   `results/` is needed.
7. **No single run script**, and `make` does not exist on Windows here (section 3).

---

## 2. What is missing for each contribution

### Contribution 1: formal model and property catalogue

Fault coverage against the events you listed:

| Your event | Repo today | Gap |
| --- | --- | --- |
| Download fail | **Missing** | No transfer stage exists; a write starts with the image implicitly available |
| Install fail | Partial | `write_corruption`, `verification_failure`, `activation_failure`, `boot_failure` |
| Power loss | Partial | Stage boundaries only, one per run, no outage duration, no torn operation |
| Timeout | **Missing** | Deadlines exist only in the planner; no ack, late-response or hung-ECU semantics |
| Rollback | Partial | A fault-free logical search with perfect global knowledge. It is instant, and **cannot itself fail or be interrupted** |

Also missing:

- A coordinator as a modelled process. Today a global Python function decides everything, so
  messages, lost acks, and durable versus volatile campaign state do not exist.
- Multiple faults, including a fault during rollback. This is where partial-failure bugs are most
  likely to live.
- Retries.
- Liveness (does the campaign terminate?). Current invariants are safety-only.
- A distinct commit point. The repo checks "restore the originals" but has no notion of when rollback
  stops being the right goal.
- A written catalogue with precise definitions.

### Contribution 2: model checking and flawed designs

Nothing exists: no specs, no TLC runs, no counterexamples, and no flawed-design set. The fixtures
(`recovery_trap`, `impossible_direct`) are useful seeds only.

### Contribution 3: scalability

Nothing exists: no generator for larger campaigns, no measurements, no abstraction or compositional
argument. The MCUboot report explicitly excludes scalability.

### Contribution 4: validation

Exists: a one-ECU differential against real bootloader code, including a useful methodology. Its own
report lists what it does not establish: no multi-ECU coordination, no hardware flash tearing, no
arbitrary repeated faults, only two operation-counter cuts. Missing: a multi-node SIL, a trace format,
trace checking against the spec, a fault-injection harness, the Pi testbed, and any model-versus-observed
comparison at campaign level.

---

## 3. Environment: what can and cannot be done here

Observed on this machine: Intel i7-1165G7, 8 logical CPUs, 16,705,122,304 bytes RAM (WSL sees 7 GiB).

| Tool | Status | Consequence |
| --- | --- | --- |
| Java | 18.0.2 on Windows; **no Java in WSL Ubuntu-24.04** | TLC can run on Windows now (TLA+ tools need Java 11+). Install a JDK in WSL for Linux runs |
| TLC / `tla2tools.jar` | Pinned to stable v1.7.4 (TLC 2.19) in `tools/versions.json`; fetched by `tools/fetch_tools.py` with SHA-256 check | v1.8.0 was rejected because it is a pre-release that gets republished. If a later experiment needs a 1.8-only feature, the pin must change deliberately |
| UPPAAL | Not installed | See section 4 |
| `make` | Only in WSL | Provide `run_all.py` as the real entry point, plus a thin Makefile |
| cargo, gcc | Present in WSL | The MCUboot harness can be rebuilt |
| Docker | Installed, **daemon not running** | You need to start Docker Desktop if the SIL uses containers |
| Raspberry Pis, relays | **Not available to me** | I cannot run or fake E7. I can write the harness; you must run it and commit raw logs |
| Sustained compute | Laptop only | Long runs need you to leave it on. Timings are specific to this machine and will be reported that way |

---

## 4. Tool decision

**Recommendation: TLA+ with TLC as the primary checker. Apalache as a secondary tool for large-n
inductive checks. UPPAAL only if a timing claim becomes central.**

- TLC is open source and runs here, which suits a re-runnable artifact. Anyone can reproduce it.
- UPPAAL's free licence is limited to non-commercial use at degree-granting academic institutions and
  needs an online licence lease. That weakens reproducibility and may not apply to you (question Q2).
- TLA+ has a published route to contribution 4: checking implementation traces against a spec with TLC
  (Cirstea et al. 2024; Howard et al.).
- **Cost of this choice:** TLC is untimed. Timeouts become nondeterministic events, so we can prove
  "a late ack cannot cause an inconsistent state" but not "rollback completes within X seconds".
  Campaign duration claims would need UPPAAL or measurement, and the paper must say so.

---

## 5. Proposed design

### 5.1 Model

Processes: one coordinator, N ECU agents, a fault environment.

- **ECU state:** two slots (version, integrity), active pointer, trial/confirmed flag, phase
  (`idle, downloading, staged, verified, activating, trial, confirmed, failed`).
- **Coordinator state:** durable campaign log, volatile progress, campaign phase
  (`prepare, activate, commit, rollback, done, aborted`).
- **Fault events:** `DownloadFail`, `InstallFail` (corrupt / verify / activate / boot),
  `PowerLoss` (one ECU, or vehicle-wide), `Timeout` (including the late-ack case), and faults
  during rollback.
- **Fault budget F** is a model constant: F = 0, 1, 2 at minimum.
- **Single source of truth:** the existing `Campaign` JSON is translated to TLC constants. Spec,
  simulator and SIL all consume the same campaign file.

### 5.2 Property catalogue (draft, to be finalised in week 3)

| ID | Name | Informal statement | Existing? |
| --- | --- | --- | --- |
| S1 | ActiveBootable | Every ECU running an image runs a valid one | Yes |
| S2 | CompatAlways | Every reachable active-version vector satisfies all `requires` | Yes |
| S3 | AuthorizedChange | Any move to an older version is covered by an authorization | Yes |
| S4 | NoUnverifiedActivation | Nothing activates before verification succeeds | Implicit |
| S5 | KnownGoodRetained | Before campaign commit, each updated ECU keeps a valid old image | Implicit |
| S6 | MutexRespected | Mutex-grouped ECUs never write concurrently | Planner only |
| S7 | PreconditionGuard | No flashing unless ignition and battery conditions hold | Planner only |
| S8a | TerminalAtomic (strict) | Every terminal state is all-new or all-old | Partly |
| S8b | TerminalConsistent (weak) | Every terminal state is compatible and bootable, mixed versions allowed | New |
| S9 | CommitIrreversible | After commit, no ECU rolls back automatically | New |
| S10 | DurableRecovery | After power loss, the coordinator can determine a safe continuation from durable state only | New |
| L1 | CampaignTerminates | Under fairness and bounded faults, a terminal state is reached | New |
| L2 | RollbackCompletes | Once rollback starts, it finishes (under bounded faults) | New |
| L3 | NoRetryLivelock | Retries cannot continue forever | New |

S8a and S8b are both kept because "consistent state" has two defensible meanings. The repo uses the
strict one. Reporting both avoids guessing and makes the difference itself a finding.

"Functional safety" here means design-level safety properties of the update protocol. It is **not**
ISO 26262 compliance evidence, and the paper must not imply that.

### 5.3 Scaling strategy (the core technical bet)

An unreduced product of N ECUs with L local states has up to L^N states. Even L = 2 at N = 50 gives
2^50, about 1.1e15, which is out of reach for explicit-state checking. That is arithmetic, not a
measurement. **Expect monolithic TLC to stop far below 50 and report that plainly as DNF.**

Model levels, each compared against the one before:

- **M0, faithful:** full interleaving, the reference.
- **M1, commuting writes:** writes touch only inactive slots, so they do not change the active vector.
  Collapse them with a reduction argument.
- **M2, symmetry:** ECUs of the same role are interchangeable (TLC `SYMMETRY`). Dependency edges limit
  this. TODO: confirm TLC's documented restrictions on symmetry with liveness before relying on it for
  L1 to L3.
- **M3, compositional:** the vehicle-specific argument below.

Candidate theorems. **All are unproven hypotheses until week 9.**

- **T1, edge decomposition.** `requires` constraints are binary, so compatibility is a conjunction over
  dependency edges. S2 over a whole vehicle should reduce to checking each edge's projection against an
  abstract coordinator, which is polynomial in the number of edges.
- **T2, reverse-prefix rollback.** If a plan is valid, every activation prefix is compatible. Undoing
  activations in reverse therefore revisits only states already known compatible. If old images are
  retained and each ECU's rollback is authorized, a rollback path should always exist, so the expensive
  global search reduces to a linear per-ECU check. The existing benchmark is consistent with this
  (`core-authorized-recovery` shows 0 unavailable rollbacks), but that is one data point and not evidence
  for the theorem.
- **T3, cutoff for star and zonal topologies.** For a gateway with N interchangeable leaf ECUs, there may
  be a small k such that checking k leaves implies all N. Cutoffs are known for specific system classes
  (Emerson and Namjoshi 1995), and the problem is undecidable in general, so this needs an actual proof
  for our class, and it may fail.

**A likely interesting finding (hypothesis):** T2 suggests where safety breaks. Per-ECU bootloader auto-revert
is locally correct (MCUboot does it, and the repo has native evidence), but independent reverts do not follow
reverse activation order. If ECUs confirm out of order, a vehicle-wide power loss might leave an incompatible mix
even though every ECU behaved correctly. That links the single-ECU evidence to the multi-ECU question, and is
flawed design D5 below.

---

## 6. Experiments

**Rules for all experiments.**

- Each has one script in `experiments/`, fixed seeds, and raw output in `results/raw/` as CSV or JSON,
  with tool versions, git commit and machine details stored alongside.
- Every paper number comes from generated `paper/numbers.tex`. A check fails the build on any
  hand-typed result.
- A run that hits its limit is recorded as `DNF(time)` or `DNF(memory)`, never dropped or extrapolated.

### E1. Model agreement with the existing simulator

Does the TLA+ baseline reproduce the tested Python semantics?

- **Input:** 11 frozen campaigns (10 after removing the duplicate), single-fault configuration.
- **Metrics:** per-campaign, per-property verdict agreement; list of disagreements with triage
  (spec bug, simulator bug, intended difference).
- **Baseline:** existing simulator and exhaustive oracles.

### E2. Bug finding on flawed designs (contribution 2)

Each design has a paired **fixed** version, which must pass. This measures false alarms.

| ID | Flaw | Expected to violate (hypothesis) |
| --- | --- | --- |
| D1 | Activates a dependent before its dependency | S2 |
| D2 | Local rollback: only the failed ECU reverts | S2, S8a |
| D3 | Rollback in forward order instead of reverse | S2 |
| D4 | ECU confirms before the campaign commit | S8a, S9 |
| D5 | Uncoordinated per-ECU auto-revert | S2, S8b |
| D6 | Old image erased before the new one is verified | S5, S1 |
| D7 | Campaign log not durable | S10, S8a |
| D8 | No timeout on ECU acks | L1 |
| D9 | Late ack after timeout: coordinator rolls back while the ECU activates | S2, S8b |
| D10 | Unbounded retry | L3 |
| D11 | Anti-rollback or missing authorization blocks recovery | L2, S8a |

**Baselines**

| Label | Method |
| --- | --- |
| B1 | Endpoint check: only final versions compared |
| B2 | Existing Z3 nominal planner |
| B3 | Existing exhaustive single-fault sweep (14 or 16 cases per ECU) |
| B4 | Random fault injection in the SIL, 20 fixed seeds, same wall-clock budget as TLC |
| TLC | Model checking at F = 0, 1, 2 |

**Metrics per (design, property, method)**

- Detected or not.
- Time to first violation and distinct states at detection (TLC).
- Counterexample length, and number of faults in it (the minimum faults needed).
- For B4: detection rate over seeds with a Wilson 95% interval, and runs to first detection.
- False alarms on fixed designs.
- Property-kill matrix: every property must be violated by at least one design, or it may be vacuous.
- TLC action coverage: every action must fire.

Counterexamples are stored as JSON and rendered as sequence diagrams by script.

**Threat:** we wrote these flaws ourselves, so detection does not measure real-world bug density. Each must be
traced to a documented practice or specification clause where possible, and the paper reports them as
design-pattern case studies rather than a detection rate.

### E3. Scalability (contribution 3)

- **Sizes:** N = 5, 10, 20, 50 as required, plus 2, 3, 4, 6, 7, 8, 12, 15 so that growth can be fitted before the
  first DNF.
- **Topologies:** star (gateway), chain, zonal tree, and random layered DAG (5 fixed seeds).
- **Fault budget:** F = 0, 1, 2.
- **Levels:** M0, M1, M2, M3 and Apalache on the inductive S2 check.
- **Limits:** 4 hours wall-clock and 10 GiB heap per run, one TLC worker for the main series, plus a 4-worker
  sensitivity run. Once a configuration hits DNF at size N, larger sizes are logged `skipped-after-DNF`. Limits may
  change after the week-5 pilot, and any change is recorded.
- **Repetitions:** 3 for runs under 30 minutes, otherwise 1 and flagged. Report median and range.
- **Metrics:** distinct states, states generated, search depth, wall-clock, peak memory, verdict, and DNF reason.
- **Baselines:** M0 is the reference. The existing simulator sweep and Z3 planner times are reported at the same
  sizes for context, labelled as checking less.

### E4. Abstraction soundness

The speedups in E3 mean nothing without this.

- **Verdict agreement** between M0 and each reduced level on every instance M0 completes, and on all of D1 to D11.
- **Exhaustive small-instance check** of T1 and T2 on all dependency graphs up to a size set by the week-5 pilot.
- **Counterexample concretization:** each abstract counterexample replayed in M0. Report the spurious rate.
- **Stated limit:** N above M0's reach rests on the proofs, not on measurement. The paper will say so.

### E5. Model versus SIL (contribution 4)

**SIL design.** Separate OS processes per ECU, plus a coordinator, with file-backed flash, a real network channel,
SIGKILL for power loss, and proxy-based delay or drop for timeouts.

**Circularity control.** If the same person writes the model and the SIL from the same idea, agreement proves little.
Mitigations:

- Predictions are generated and **git-tagged before any SIL run**, in `results/predictions/`.
- The SIL does not import `ota_verifier` semantics.
- E6 and E7 add components nobody here wrote.

**Unit of comparison:** (campaign, design, fault script). Scripts come from three sources: replayed TLC counterexamples,
systematic boundary scripts, and seeded random schedules (K fixed in advance, 30 repetitions for timing-sensitive
scripts).

**Metrics**

- Confusion matrix of predicted against observed violations, per property.
- Agreement and Cohen's kappa with Wilson 95% intervals.
- Counterexample replay rate.
- **False negatives:** any observed violation the model called impossible. These are the most important cases.
- Trace conformance rate: share of SIL traces accepted by TLC as behaviours of the spec.
- Each divergence triaged as model bug, SIL bug, or abstraction gap.
- `UNSUPPORTED` reported separately and never counted as agreement.

**Baselines:** B1 and the existing simulator as weaker predictors.

### E6. Multi-instance MCUboot

Extend the existing harness to N real bootutil instances over simulated flash, driven by a campaign coordinator. This gives
independent C code on the safety-critical rollback path, and is the direct test of D5. Metrics as in E5, plus coverage of
operation-counter cut points (the current evidence has two cuts).

### E7. Raspberry Pi testbed (needs your hardware; I cannot run this)

- **Hardware:** Pis as ECUs with real A/B partitions, using an existing update client (candidate: RAUC; decide in week 13),
  with Ethernet between nodes.
- **Power loss:** a relay-controlled power cut, not a software reboot.
- **Metrics:** E5 metrics plus per-stage durations and failed-boot counts.
- **Threat:** a Linux Pi is not an automotive ECU. Results show protocol behaviour under real power loss and real flash, not
  automotive-grade conformance.

---

## 7. Proposed folder structure

New items only; existing folders are unchanged.

```text
ota_verifier/
  PLAN.md
  run_all.py                 # single cross-platform entry point
  Makefile                   # thin wrapper, usable in WSL
  specs/
    tla/                     # OTACampaign.tla, ECU, Coordinator, Faults, Properties
    designs/                 # D1..D11 and their fixed pairs
    PROPERTIES.md            # the catalogue, with formal definitions
  src/ota_verifier/formal/   # Campaign JSON -> TLC constants, counterexample parsing
  campaigns/                 # topology generator (fixed seeds) and frozen campaigns
  sil/                       # coordinator, ECU agents, fault proxy (no ota_verifier imports)
  testbed/                   # Pi provisioning, relay control, log collection
  experiments/               # e1_*.py ... e7_*.py, one per experiment
  tools/                     # pinned tool versions and checksums; jars fetched, not committed
  results/
    predictions/             # frozen before any SIL or testbed run
    raw/<experiment>/<run-id>/
    processed/               # derived only by scripts
  paper/
    numbers.tex              # generated; the only source of result numbers
    figures/                 # generated
    refs.bib                 # verified entries only; unverified ones marked TODO
```

---

## 8. Week-by-week plan

This assumes 20 weeks from Monday 9 November 2026 at roughly part-time research pace. It depends on Q1 and Q3 below.

| Week | Focus | Deliverable |
| --- | --- | --- |
| 1 | Repo hygiene: fix CI location, README link, de-duplicate corpus, `results/`, `run_all.py`, pin TLC | CI green on GitHub; `run_all.py --smoke` works |
| 2 | Systematic literature search; finish the TODOs in section 10 | `paper/refs.bib`, related-work table, novelty decision |
| 3 | Formal definitions; finalise property catalogue | `specs/PROPERTIES.md` |
| 4 | TLA+ baseline for 2 to 3 ECUs, single fault | Spec passes TLC; E1 started |
| 5 | Full fault set, F up to 2, liveness; scalability pilot | E1 complete; pilot sets limits for E3 |
| | **Gate A (end of week 5):** do spec and simulator agree? | If not, fix before proceeding |
| 6 | Flawed designs D1 to D6 with fixes | First counterexamples |
| 7 | D7 to D11; baselines B1 to B3 | E2 partly complete |
| 8 | Campaign generator; M0 scaling runs; M1 | E3 M0 series |
| 9 | Prove or refute T1 and T2; M2 | Written proofs or counterexamples |
| 10 | M3 and T3 attempt; Apalache trial | Reduced models |
| | **Gate B (end of week 10):** does a sound abstraction reach N = 50? | If not, narrow the claim (section 9) |
| 11 | E3 full runs, E4 | Scalability and soundness tables |
| 12 | SIL coordinator and agents, trace format | SIL runs nominal campaigns |
| 13 | SIL fault injection; freeze and tag predictions; order Pi hardware by now | `results/predictions/` tagged |
| 14 | E5 runs; B4 for E2; trace checking | Confusion matrices |
| 15 | E6 multi-instance MCUboot | Native evidence |
| 16 | Divergence triage; model fixes logged, with E2 to E5 re-run where affected | Triage log |
| 17 | E7 harness and bring-up (you run it) | Testbed campaigns pass nominally |
| 18 | E7 fault runs | Raw testbed logs committed |
| 19 | Paper draft from generated numbers | Full draft |
| 20 | Clean-machine reproduction; artifact package; internal review | Tagged release, submission-ready |

Weeks 17 and 18 are the least certain. If hardware is late, the paper can still stand on E5 and E6, with the testbed reported
as limited or as future work. That is a weaker answer to your research question, so it is worth ordering hardware early.

---

## 9. Risks

| Risk | Likelihood | Response |
| --- | --- | --- |
| T1 to T3 fail or need strong assumptions | Medium to high | Publish the assumptions; claim N only where proven, and report the measured limit |
| A paper already covers this (search so far is not exhaustive) | Medium | Week 2 search before spec work deepens; repositioning stays cheap at that point |
| Reviewers see the flawed designs as strawmen | Medium | Tie each to a documented practice; report as case studies |
| Model and SIL agree only because of shared assumptions | High without controls | Frozen predictions, no shared code, E6 and E7 |
| Fault budget F = 2 hides deeper bugs | Medium | State bounded results as bounded; test larger F on small N |
| Laptop limits and noise | High | Fix hardware, record it, use state counts as the portable metric, run on a server if you have one (Q4) |
| Late model changes invalidate earlier results | Medium | `run_all.py` re-runs everything; results carry a spec hash |

---

## 10. Related work: verification status

**Novelty so far.** Published formal OTA work found in this first pass targets **security** (Uptane, UniSUF; Tamarin, ProVerif,
CSP, Kind 2). I found no paper model-checking functional safety of multi-ECU campaigns with rollback, validated on a testbed.
**This came from a short search, so it does not establish novelty.** Week 2 must settle it.

The nearest prior art found on A/B atomicity is a public, non-peer-reviewed single-device TLA+ project
([navadiashrey/ab-firmware-update-tla](https://github.com/navadiashrey/ab-firmware-update-tla)). It should be acknowledged.

**Status key**

- **VERIFIED:** bibliographic details seen in a primary or index source. The abstract was read only where stated.
- **TODO:** do not cite until checked.

| Reference | Use | Status |
| --- | --- | --- |
| Yu, Manolios, Lamport. Model Checking TLA+ Specifications. CHARME 1999, LNCS 1703, pp. 54-66 | TLC | VERIFIED |
| Konnov, Kukovec, Tran. TLA+ Model Checking Made Symbolic. OOPSLA 2019, PACMPL 3, art. 123, doi:10.1145/3360549 | Apalache | VERIFIED |
| Clarke, Long, McMillan. Compositional Model Checking. LICS 1989, pp. 353-362, doi:10.1109/LICS.1989.39190 | Compositional reasoning | VERIFIED |
| Emerson, Namjoshi. Reasoning About Rings. POPL 1995, pp. 85-94 | Cutoffs | VERIFIED (via reference lists) |
| Cirstea, Kuppe, Loillier, Merz. Validating Traces of Distributed Programs Against TLA+ Specifications. arXiv:2404.16075 | Trace validation | VERIFIED (arXiv); TODO final LNCS details |
| Howard, Kuppe, Ashton, Chamayou, Crooks. Smart Casual Verification of CCF's Distributed Consensus and Consistency Protocols. arXiv:2406.17455 | Trace validation | VERIFIED (arXiv); TODO confirm NSDI 2025 |
| Hagen, Lundqvist, Phu, Wang, Strandberg, Schiller. Towards a Formal Verification of Secure Vehicle Software Updates. Computers & Security, 2025, doi:10.1016/j.cose.2025.104751 | Closest security work | VERIFIED (abstract read) |
| Shoker, Alves, Esteves-Verissimo. ScalOTA. arXiv:2307.02032 | OTA scalability | VERIFIED (abstract read); no venue stated |
| Schmid et al. Formal Verification of a Fail-Operational Automotive Driving System. arXiv:2101.07307 | Automotive safety model checking | VERIFIED (abstract read) |
| Lorch, Larraz, Tinelli, Chowdhury. A Comprehensive, Automated Security Analysis of the Uptane Automotive OTA Update Framework. RAID 2024, pp. 594-612, doi:10.1145/3678890.3678927 | Closest Uptane work | Details from index records; **TODO read full text**, resolve an author attribution conflict seen in one survey |
| Kuppusamy, Brown, Awwad et al. Uptane: Securing Software Updates for Automobiles. escar 2016 | Uptane | **TODO** complete author list |
| Davis, Hirschhorn, Schvimer. eXtreme Modelling in Practice. PVLDB 13(9):1346-1358, 2020 | Spec-to-code conformance | **TODO** seen only as a citation in other papers |
| Kirk, Nguyen, Bryans, Shaikh et al. CSP formalisation of Uptane. QRS 2021; JLAMP 130, 2023 | Model-based security testing | **TODO** exact titles and authors |
| Boureanu 2023, Uptane 2.0 in Tamarin | Security | **TODO** seen only via a survey |
| AUTOSAR Adaptive UCM (doc 888) and Vehicle UCM (doc 1090), R24-11 / R25-11 | Rollback requirements | Documents exist; **TODO read normative text** |
| AUTOSAR EXP Firmware Over-The-Air, R20-11 | Campaign rollback | **TODO** PDF text not read |
| UN Regulation No. 156; ISO 24089:2023 | Context | Existence confirmed via secondary sources; **TODO read primary text** |
| "Trusted Verification of OTA Secure Software..." (NDSS AutoSec 2021) | Possibly related | **TODO** title and authors unconfirmed |
DataMod 2024 paper noting a lifecycle verification gap (author unknown; the PDF file name says "figge") | Gap statement | **TODO** read and confirm title and authors |
| "OTA Update Assurance for Energy and Charging Functions in SDVs" | Possibly related | **TODO** read; ResearchGate listing only |
| Behrmann, David, Larsen. UPPAAL tutorial | Only if UPPAAL is used | **TODO** not found in search |

---

## 11. Open questions

Only the ones where a wrong guess would be costly. Work proceeds on the stated default until you answer.

| ID | Question | Why it matters | Default |
| --- | --- | --- | --- |
| Q1 | What is your target journal and submission deadline? | Sets the schedule, length, and whether the testbed is required | 20 weeks; journal open (for example JSS, SoSyM, or Formal Aspects of Computing; requirements unchecked) |
| Q2 | Are you at a degree-granting institution, and is timing analysis important to you? | Decides whether UPPAAL is legally usable and whether untimed TLA+ is enough | TLA+ only; no timing guarantees claimed |
| Q3 | How many Raspberry Pis can you get, and by when? Is a relay board available? | E7 design and contribution 4's strength; lead times can block weeks 17 and 18 | 4 Pis and a relay board by week 13 |
| Q4 | Do you have access to a server or HPC with more RAM? | Sets where the E3 limit falls, and whether results reflect the laptop or the method | This laptop only |
