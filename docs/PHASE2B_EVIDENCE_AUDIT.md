# Phase 2B evidence audit

The scalability measurements exist and were executed; this conclusion is based on raw manifests, worker outputs and hash verification, not filenames alone. The audit is offline and does not rerun the approximately 103-minute primary experiment.

Primary evidence: `eval/scalability/evidence/primary-v1/`, with 120 distinct inputs, three topology seeds (11, 29, 47), ten families, sizes 10/30/50/100, five repetitions and 40 excluded warm-ups. Each measured input/repetition has Z3 and sequential-baseline attempts. Full configurations, realized densities, dependency counts, capacity, gold witnesses/contradictions and commands are frozen. Sparse/dense edge-selection probabilities are over witness-eligible directed pairs, not every possible directed pair; actual densities are recorded.

| Measured Z3 outcome | Count |
| --- | ---: |
| Feasible | 225 |
| Infeasible | 180 |
| Unknown | 180 |
| Process watchdog | 15 |
| **Total measured Z3** | **600** |

The baseline returned 420 valid schedules and 180 `NO_BASELINE_SCHEDULE` results. The latter is not an infeasibility proof. Seven families have constructive feasible gold; three have local contradiction certificates. No arbitrary large-core hardness is established. Of 225 feasible Z3 results, 185 proved makespan optimality and 40 did not. Of 180 returned cores, 132 established subset minimality and 48 did not; none is asserted minimum-cardinality.

| Total ECUs | Feasible | Infeasible | Unknown | Watchdog |
| --- | ---: | ---: | ---: | ---: |
| 10 | 105 | 45 | 0 | 0 |
| 30 | 90 | 45 | 15 | 0 |
| 50 | 30 | 45 | 75 | 0 |
| 100 | 0 | 45 | 90 | 15 |

The existing planner did not discover a feasible primary 100-ECU positive under these budgets. It did detect the deliberately constructed 100-ECU negative cases. This is a measured boundary, not general 100-ECU scheduling scalability.

The primary measurement used Windows 11 build 22631, CPython 3.14.4, Z3 4.16.0.0, eight logical CPUs and 16,705,122,304 bytes physical RAM, on a non-dedicated Balanced-power host. API timing includes construction/optimization/internal replay, not just Z3 check time. The nominal solver budget was 10 seconds, outer watchdog 45 seconds. The primary completion record reports 6,174.15 seconds before final artifact hashing. Generation/gold cost was recorded separately from API timing.

Medians/p95 are per family/size/status with explicit n; 15 observations comprise three seeds repeated five times, not 15 independent topologies. For independent 10-ECU inputs, feasible-return API median/p95 were 192.33/445.91 ms. At 30 ECUs they were 10,036.41/10,096.49 ms. Returned unknowns and watchdogs remain visible; they are not zero-latency samples. Review all cells in the [verified JSON](../eval/scalability/evidence/primary-summary-v1/summary.json), [CSV](../eval/scalability/evidence/primary-summary-v1/cells.csv) and [actual-measurement charts](../eval/scalability/evidence/primary-summary-v1/outcomes.png).

## Known monitoring defect retained

Historical Windows parent supervision sampled the venv launcher rather than the worker interpreter. Parent memory readings and enforcement of the intended soft 2 GiB bound are unreliable. Returned workers' own OS peak-working-set readings remain observationally usable; they include Python/import/native allocations and do not isolate Z3 heap usage. Maximum returned-worker after-API peak was 314.79 MiB. Dense 100-ECU timeout-worker peaks are unavailable.

The runner was corrected and a separate real-process audit demonstrated worker PID monitoring, actual allocation stopping and a dense 100-ECU watchdog outcome. That confirmation does not repair the historical samples or establish a corrected full matrix. No expensive rerun was needed for this audit. A future full corrected-monitor matrix requires a deliberate resource budget.

## Integrity and provenance

The final audit rechecks nine existing benchmark/analysis manifests: **7,768 artifact entries**, plus **108 existing MCUboot entries** in the two final packages. These counts include retained failed supervision audits; hash validity does not mean every execution succeeded. The exact recheck is recorded in `runs/completion-audit-v1/integrity.json`.

The authorized LLM User-Agent change occurred after timing measurements. Current production-source comparison therefore identifies `llm/client.py` drift; it does not identify a changed planner or simulator. The new independent exporter is also later code. Historical benchmark source snapshots and hashes, not today's tree, identify the measured implementation. Existing original integrity files are not rewritten.

Reproduce an analysis in a new directory (no solver rerun):

```powershell
$env:MPLCONFIGDIR = Join-Path (Get-Location) '.ota_state/scalability-mpl'
.\.venv\Scripts\python.exe eval/scalability/report.py --input eval/scalability/evidence/primary-v1 --output eval/scalability/evidence/review-summary-new
```

See [the full methodology](PHASE2B_SCALABILITY.md). Status: **PARTIALLY VERIFIED** performance evidence, with verified execution/hashes and explicit historical memory-supervision limitations.
