# Scalability benchmark implementation and execution

Workstream Phase 2B (project Phase 13B). **Live LLM evaluation is a separate, unstarted Phase 2C.** This study measures synthetic scheduling workloads, not vehicle-fleet data, hardware flashing or extraction accuracy.

## Scope and implementation

The benchmark lives in `eval/scalability/` and does not change production scheduling, compatibility, simulation, review or UI code.

| File | Responsibility |
| --- | --- |
| `workloads.py` | Fixed-seed, schema-valid synthetic inputs; constructive feasible witnesses and analytic contradiction checks; a sequential greedy baseline. |
| `worker.py` | One isolated Z3 or baseline execution; schema/API/external-validation/serialization timings; complete compressed result; LLM import guard. |
| `memory.py` | Windows OS peak-working-set observations, including native allocations; physical-RAM snapshot; labelled Unix fallback. |
| `run.py` | Frozen trial manifest, fresh serial processes, watchdog/soft memory guard, raw attempt records, source/evidence integrity checks and hashes. |
| `report.py` | Verified JSON/CSV aggregation and standalone Matplotlib PNG/SVG charts. |
| `test_scalability.py` | Generator, gold, baseline, supervision, memory and aggregation regression contracts. |
| `audit_supervision.py` | Real-process Windows launcher diagnosis, memory-stop probe and separate actual-Z3 supervision check. |
| `requirements-plot.txt` | Optional pinned Matplotlib 3.10.8; production dependencies are unchanged. |

The [approved evaluation plan](PHASE2_EVALUATION_PLAN.md) defines the study. Each input records total and changed ECU counts, seed, all constraint counts, realized dependency density, capacity, timeout, variant, witness/certificate and canonical input digest. Document-constraint counts exclude separately tracked policy/resource assumptions; an unauthorized-downgrade conflict can have zero document constraints and still have a policy unsat core.

### Workload and baseline semantics

Ten families cover independent, sparse, dense, mixed-version, resource-limited, chain, contradictory-cycle, mutex/order, environmental and downgrade cases at **10/30/50/100 ECUs**, using seeds **11/29/47**. Feasible gold uses an explicit sequential compatible witness, validated independently of Z3. Negative gold uses specific contradictions rather than the solver's own label.

The cyclic negative uses two mutually target-gated updates with valid endpoints and no legal first serialized activation; independent fillers supply the remaining inventory. Benign cycles are separate controls. Such local contradictions are not a benchmark of arbitrary large unsat cores. Requires-only chains constrain activation order, not write start; an explicit-order companion establishes the different finish/start semantics.

The baseline picks eligible updates in stable ID order and writes sequentially. It enforces supported permissions, environment, order, deadline and compatibility; mutex/capacity hold by sequential construction. It reports `NO_BASELINE_SCHEDULE` when it gets stuck, never an infeasibility proof. A parallel plan may exist when a sequential deadline cannot be met. Makespan ratios are restricted to pairs with valid returned plans; solver optimality remains explicit. Sequential construction and parallel makespan optimization are different objectives.

### Timing and memory interpretation

Generation plus gold checking is measured before trial execution and excluded from planner timings. Each fresh worker records schema parsing, public planning/baseline API time, additional external replay, serialization and parent-observed process duration separately. API time includes model construction, optimization and internal plan replay; it is **not pure Z3-check time**. Worker startup/imports are outside that API timer but remain in worker duration.

Windows `PeakWorkingSetSize` observes Python and native allocations together. Before-API, after-API and whole-worker peaks are retained; after-API high-water marks still include imports and schema objects. Peaks are not subtracted to fabricate a precise Z3-heap allocation. The intended parent limits are a **soft** 2 GiB stop and 45-second watchdog. **Final review found that the historical Windows runs sampled the venv launcher PID, not the worker interpreter. Their parent memory readings and soft-memory-limit enforcement are unreliable.** Worker self-observations remain usable; timeout-worker peaks cannot be recovered from launcher readings. See the supervision findings below. The production solver budget remains **10 seconds** except for declared supplementary sensitivity cases; it cannot preempt model construction or final replay independently.

Measurements are serial. The host is not dedicated, CPU/background load is not controlled, and the power scheme is an observation rather than a frequency lock. Hardware/package/source details are recorded in each run; `evidence/host-preflight.json` retains an additional read-only CPU/power observation. No performance guarantee is inferred for other machines, real networks or other topologies.

## Protocol and pilot evidence

| Profile | Declared trials |
| --- | --- |
| Smoke | 10 size-10 inputs; one Z3 and one baseline execution each. |
| Pilot | 10 families x 4 sizes at seed 11; 40 Z3 and 40 baseline executions. |
| Primary | 120 unique inputs x 5 repetitions; **600 measured Z3 + 600 measured baseline trials**, preceded by 40 separately recorded Z3 warm-ups. |
| Supplementary | Eight paired/control variants at four sizes, plus four timeout-sensitivity inputs; 36 Z3 and 36 baseline executions. Separate from primary statistics. |

All profile manifests are frozen before measurement. Primary cases are shuffled with fixed order seed 20261106. All outcomes—including unknown, timeout, memory termination and not-run—remain in JSONL and per-trial records. Warm-ups are excluded from measured statistics but never erased. Medians and nearest-rank p95 have explicit sample counts; fifteen observations per primary family/size are descriptive, not a strong population-tail estimate.

The smoke run completed all 20 executions: 14 feasible, 3 Z3-infeasible and 3 baseline-no-schedule outcomes, with no correctness findings.

The initial `pilot-v1` is retained, including **two dense 100-ECU watchdog terminations**, one for Z3 and one for the baseline. The baseline repeatedly rechecked unaffected constraints. Before primary measurements, the baseline was refined to index affected requires and reuse `compat.requirement_holds` with current-version lookup. By induction from a compatible state, unaffected dependencies stay true; complete final plan replay still checks every intermediate state. No production compatibility implementation or planner was altered.

The complete `pilot-v2` rerun used the refined baseline. Its Z3 outcomes were **15 feasible, 12 infeasible, 12 unknown and 1 watchdog timeout**; the baseline returned **28 valid schedules and 12 no-schedule outcomes**. Both pilots had zero truth/validation findings and unchanged protected source/MCUboot evidence. Different baseline versions are not pooled into primary statistics. `pilot-v1/source_snapshot/` preserves the earlier implementation; subsequent profiles capture their own source snapshots automatically.

These pilot outcomes already show a bounded-planning limitation: larger inputs can remain unknown or exceed the process watchdog. The benchmark does not modify the planner to conceal that limitation.

## Reproduce

Use the existing project environment from the repository root:

```powershell
# Optional charts only; native OS memory measurement has no additional dependency.
.\.venv\Scripts\python.exe -m pip install -r eval/scalability/requirements-plot.txt

.\.venv\Scripts\python.exe eval/scalability/run.py --profile smoke --output eval/scalability/evidence/my-smoke
.\.venv\Scripts\python.exe eval/scalability/run.py --profile pilot --output eval/scalability/evidence/my-pilot
.\.venv\Scripts\python.exe eval/scalability/run.py --profile primary --output eval/scalability/evidence/my-primary
.\.venv\Scripts\python.exe eval/scalability/run.py --profile supplementary --output eval/scalability/evidence/my-controls

.\.venv\Scripts\python.exe eval/scalability/report.py --input eval/scalability/evidence/my-primary --output eval/scalability/evidence/my-primary-summary
.\.venv\Scripts\python.exe eval/scalability/report.py --input eval/scalability/evidence/my-controls --output eval/scalability/evidence/my-controls-summary --no-plots

# Real allocation and actual Z3 supervision audit, separate from timing statistics.
.\.venv\Scripts\python.exe eval/scalability/audit_supervision.py --input eval/scalability/evidence/my-primary/inputs/dense-n100-s11-primary-t10000.json --output eval/scalability/evidence/my-supervision-audit
```

Choose new output directories; evidence is not overwritten. The parent defaults to 45 seconds per process, 2048 MiB soft memory monitoring and a six-hour per-profile experiment wall budget, including generation. `--watchdog-seconds`, `--memory-limit-mib` and `--wall-seconds` are explicit recorded overrides. If a correctness/worker finding or experiment budget stops the run, remaining scheduled attempts are recorded as `NOT_RUN`. Do not run profiles concurrently when comparing their timing.

The exact measured package versions are recorded in `environment.json` and `requirements-measured.txt`, separately from the repository's broad dependency ranges. Recreate the same Python/platform and install the project as well as compatible pinned dependencies; the snapshot is not a portable OS image. Source snapshots, dirty-tree state and hashes record what actually executed rather than asserting a clean checkout.

Each successful API result has a `.result.json.gz` with the actual full solver/baseline result. `.progress.json` retains the last stage if a worker dies. A watchdog result during construction is not relabelled `unknown`, and baseline failure is not relabelled `infeasible`. `.supervised.json` and `trials.jsonl` retain the parent command, exit code and censored memory observations. SHA-256 indices and byte-preserving Git attributes support artifact review without newline conversion.

## Correctness checks and remaining stages

Before the refined pilot, the new harness plus selected existing planner/exhaustive/plan-validation/LLM-isolation checks passed: **173 tests, 0 failures/errors, 13 dependency deprecation warnings**. A declined elevated test invocation was not treated as a test result; the successful run used the sandbox and a new project-local pytest temporary directory without changing pytest configuration.

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.ota_state/scalability-tests-new eval/scalability/test_scalability.py tests/test_planner.py tests/test_exhaustive_planner.py tests/test_plan_validation.py tests/test_llm_pipeline.py
```

Performance results are synthetic scheduling measurements only. Existing fixture evaluation is not live LLM inference, and no model/provider calls are made by this harness. Live corpus admission, provider configuration and inference require separate Phase 2C approval. The consolidated Phase 2D report and README results update remain separate later work.

## Actual primary results — 6 November 2026

The primary profile completed all **1,240 scheduled executions**, including 40 warm-ups and **600 measured trials per algorithm**, in 6,174.15 seconds before final artifact hashing. Input generation/gold checking took 16.69 seconds, outside API timers. All returned feasible plans passed complete intermediate-state replay; no returned feasible/infeasible status contradicted its independently constructed gold label. This does not resolve unknown or terminated trials.

| Total ECUs | Z3 feasible | Z3 infeasible | Z3 unknown | Z3 watchdog | Feasible with proved makespan / unproved | Baseline valid / no schedule |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | 105 | 45 | 0 | 0 | 95 / 10 | 105 / 45 |
| 30 | 90 | 45 | 15 | 0 | 75 / 15 | 105 / 45 |
| 50 | 30 | 45 | 75 | 0 | 15 / 15 | 105 / 45 |
| 100 | 0 | 45 | 90 | 15 | 0 / 0 | 105 / 45 |
| **Total** | **225** | **180** | **180** | **15** | **185 / 40** | **420 / 180** |

Each family/size cell contains three seeds and five repetitions: 15 observations, not 15 independent topologies. The three negative families contribute all 180 infeasible trials; the seven positive families have constructive witnesses. Z3 produced valid plans in **225/420 known-feasible trials**, versus **420/420** for the sequential heuristic on these workloads. **The study does not support a claim that the current planner efficiently schedules general 100-ECU campaigns under these budgets.** The easier local contradictions were still identified at that size. The supplementary half-no-op case is distinct from an all-changed 100-ECU campaign.

| Z3 family | 10 ECUs | 30 ECUs | 50 ECUs | 100 ECUs |
| --- | --- | --- | --- | --- |
| Independent | 15 feasible | 15 feasible | 15 feasible | 15 unknown |
| Sparse | 15 feasible | 15 feasible | 15 unknown | 15 unknown |
| Dense | 15 feasible | 15 feasible | 15 unknown | 15 watchdog |
| Mixed versions | 15 feasible | 15 feasible | 15 unknown | 15 unknown |
| Resource | 15 feasible | 15 unknown | 15 unknown | 15 unknown |
| Requires chain | 15 feasible | 15 feasible | 15 unknown | 15 unknown |
| Contradictory cycle | 15 infeasible | 15 infeasible | 15 infeasible | 15 infeasible |
| Mutex/order | 15 feasible | 15 feasible | 15 feasible | 15 unknown |
| Environment | 15 infeasible | 15 infeasible | 15 infeasible | 15 infeasible |
| Downgrade | 15 infeasible | 15 infeasible | 15 infeasible | 15 infeasible |

Selected **feasible-return** API latencies follow. Each row has n=15; nearest-rank p95 is the maximum of these fifteen observations. The complete JSON also separates latency by returned status; the overview chart includes returned unknown and infeasible calls too, not only feasible calls.

| Family / ECUs | Median API ms | p95 API ms | Proved makespan optima |
| --- | ---: | ---: | ---: |
| Independent / 10 | 192.33 | 445.91 | 15 |
| Independent / 30 | 10,036.41 | 10,096.49 | 15 |
| Independent / 50 | 10,056.40 | 10,102.80 | 15 |
| Dense / 10 | 443.13 | 675.86 | 15 |
| Dense / 30 | 9,806.67 | 10,482.13 | 15 |
| Requires chain / 30 | 3,610.18 | 4,723.37 | 15 |
| Resource / 10 | 10,018.54 | 10,032.39 | 5 |

Some proved-optimal makespans still consume the time budget attempting deterministic tie-breaking. The API includes construction/replay, so its elapsed time can exceed the solver budget. Among 180 unknowns, the recorded reasons were `canceled` (139) and `Planning timeout budget exhausted` (41). All 15 measured watchdogs were dense 100-ECU cases whose last progress stage was `planning`; that marker alone cannot localize the exact internal subroutine.

Of 180 returned conflict diagnostics, **132** reported subset-minimal cores; **48 did not establish minimality** within the budget. Subset-minimal is not minimum-cardinality. No minimal-core claim is made for unknown or terminated trials.

Completed Z3 workers reported a maximum after-API peak working set of **314.79 MiB**. This excludes watchdogs and includes imports/native allocations. Dense 100-ECU memory is **unavailable**, not a low-memory result. Complete per-cell memory, latency, core and optimality statistics are in [the JSON summary](../eval/scalability/evidence/primary-summary-v1/summary.json) and [CSV](../eval/scalability/evidence/primary-summary-v1/cells.csv).

There were 225 valid paired schedules. Median sequential/Z3 makespan ratios were 3.67 (10 ECUs, n=105 pairs), 17.40 (30, n=90) and 11.74 (50, n=30); there were **no comparable primary 100-ECU pairs**. These are workload-conditioned simulated schedule ratios, not planner-runtime speedups or overall success rates. They omit unresolved Z3 cases; some included Z3 plans have unproved optimality. The sequential baseline is computationally much cheaper here but deliberately forgoes parallel writes.

Charts, also available as SVG alongside each PNG:

- [Returned API latency](../eval/scalability/evidence/primary-summary-v1/api_latency.png)
- [Completed-worker memory](../eval/scalability/evidence/primary-summary-v1/memory.png)
- [All measured Z3 outcomes](../eval/scalability/evidence/primary-summary-v1/outcomes.png)
- [Valid paired makespan ratios](../eval/scalability/evidence/primary-summary-v1/makespan_ratios.png)

## Supplementary results

All 72 scheduled executions completed in 476.55 seconds before final hashing, with 11.86 seconds of input generation/gold checking. Z3 returned **21 feasible, 4 infeasible, 9 unknown and 2 watchdog** results; the baseline returned **32 valid schedules and 4 no-schedule** results. There is only one observation per control, so no repetition-based tail claim is justified.

- Tight deadlines were infeasible at every size; relaxed versions returned plans at 10/30/50 and unknown at 100.
- Benign cycles, allowed-environment and authorized-downgrade controls returned plans at 10/30/50 and unknown at 100. Cyclicity alone is not infeasibility.
- Explicit-order chains returned plans at 10/30 and unknown at 50/100, distinct from requires-only write-overlap semantics.
- Half-no-op inputs returned plans at all four inventory sizes; the 100-ECU case had only 50 changed ECUs. Rounding controls returned plans at 10/30/50 and unknown at 100.
- Dense 100-ECU cases hit the 45-second watchdog with both 1-second and 30-second solver budgets. Resource 100-ECU cases were unknown under both budgets. Increasing the solver budget alone did not resolve these four observations.

[Control JSON](../eval/scalability/evidence/supplementary-summary-v1/summary.json) and [CSV](../eval/scalability/evidence/supplementary-summary-v1/cells.csv) retain variant and timeout as grouping dimensions. They are not pooled into the primary charts.

## Supervision findings and preserved limitations

Post-measurement review found a **benchmark-harness defect**, not a production planner defect. Windows venv `python.exe` redirects to another interpreter PID. The historical parent sampled about a launcher's working set while the worker's own OS counter observed the actual allocation. Thus the historical parent 2 GiB guard was ineffective for worker memory, and its censored memory readings are not valid worker estimates. Historical artifacts are preserved, including their original completion flags; those flags mean the then-implemented protocol finished, not that this later-discovered monitor defect was absent. New summaries explicitly mark the historical parent scope `UNVERIFIED_LEGACY_LAUNCHER`.

The runner now starts the real base interpreter with `__PYVENV_LAUNCHER__` pointing at the existing venv. Real execution verified the same venv/package resolution and matching supervised/worker PIDs. Regression tests exercise actual allocation, PID identity, watchdog handling and partial JSON output. The worker records its PID for future review.

The independent [supervision audit](../eval/scalability/evidence/supervision-audit-v2/audit.json) reproduced the launcher mismatch, observed no completion marker after launcher termination, stopped a real 64 MiB allocation using a 32 MiB guard, and ran the actual dense 100-ECU Z3 input with corrected monitoring. That planner run still hit the watchdog; its supervised PID matched the worker progress PID. This is a separate confirmation attempt, **not a repaired historical sample or a replacement benchmark**. The termination probe supports absence of continued work in that checked environment, not a universal process-tree guarantee.

The first audit attempt failed because the allocation probe was killed during a non-atomic JSON write. It is retained in `supervision-audit-v1/`; the supervisor now records partial-output errors without losing the termination outcome. The successful second audit and all original timeout rows remain visible. No production code changed. A fresh full matrix with corrected supervision is still required before claiming a reliably enforced worker-memory envelope; no such full rerun is claimed here. Historical completed-worker self-peaks/API timings are retained as observational measurements, with this limitation disclosed.

## Environment, regression and integrity evidence

Recorded environment: Windows 11 build 22631, 64-bit CPython **3.14.4**, Z3 native **4.16.0.0**, eight logical CPUs, 16,705,122,304 bytes physical RAM. The processor identifier is `Intel64 Family 6 Model 140 Stepping 1, GenuineIntel`; a friendly CPU-model query was denied, so no model name is invented. The observed power plan was Balanced. This is a non-dedicated host with uncontrolled background load. Each profile retains package versions, executable paths, dirty-tree state and a source snapshot; the measured Git base was `fc95deec6df7c1dc65c14671ad041384f18917a4`, not a claim of a clean checkout.

The final relevant suite passed **359 tests, 0 failures/errors, 13 warnings in 105.88 seconds**. Warnings are LangSmith's `asyncio.iscoroutinefunction` deprecation under Python 3.14, preserved in [the log](../eval/scalability/evidence/regression-final.log). [The exact argument list](../eval/scalability/evidence/regression-command.json) covers the new benchmark tests plus existing planner/exhaustive planning, plan validation, simulator/models, invariants, recovery/exhaustive recovery, guarded boot/recovery, boot workflow/comparison, LangGraph, LLM client/pipeline/evidence and public demo tests. It is a selected regression suite, not a claim that every repository test ran.

```powershell
$testArgs = Get-Content eval/scalability/evidence/regression-command.json -Raw | ConvertFrom-Json
# Replace the original machine's executable path, and choose a fresh temp directory.
$testArgs[0] = '.\.venv\Scripts\python.exe'
$testArgs[4] = '--basetemp=.ota_state/scalability-tests-review'
$pytestArgs = $testArgs[1..($testArgs.Length - 1)]
& $testArgs[0] @pytestArgs

# Verify frozen files without rerunning benchmarks or generating another summary.
.\.venv\Scripts\python.exe -c "import sys; from pathlib import Path; sys.path.insert(0,'eval'); from scalability.report import verify; from scalability.run import verify_mcuboot; verify(Path('eval/scalability/evidence/primary-v1')); verify(Path('eval/scalability/evidence/supplementary-v1')); verify_mcuboot()"
```

[Verification record](../eval/scalability/evidence/verification.json) and [study hash index](../eval/scalability/evidence/STUDY_SHA256SUMS.json) record **7,768 verified benchmark/analysis artifact entries and 108 existing MCUboot artifact entries** across the listed manifests. Hash verification is evidence preservation, not fresh MCUboot execution. Production source hashes match the primary manifest. All **45** returned optimal independent plans match their analytic longest-write lower bound; this does not assert optimality for other families. Both pilots used identical campaign/options for **40** inputs; their baseline implementations remain separate.

The strongest supported result is a reproducible measurement of the planner's **current boundary**, including failures, rather than an unqualified scalability claim. Future planner optimization could investigate model-construction cost, symmetry/tie-breaking and bounded heuristic fallback, but none was implemented in this phase. These synthetic topologies and easy local negative certificates do not establish performance on real ECU networks, arbitrary unsat cores or live LLM extraction. **Phase 2B stops here; Phase 2C requires separate approval.**
