# Scaling results (E3)

**Evidence:** `results/raw/e3_scaling/20261106T141615Z-ce3eefb/`, copied to `results/scaling.csv`. Summary by size: `results/processed/scaling_summary.csv`. Plot: `results/scaling.png` and `.svg`.

Run from a clean checkout of commit `ce3eefb`, on one Windows laptop (8 logical CPUs), with TLC 2.19, 1 worker, seed 42, a 4 GB heap and a fault budget of 1.

Reproduce with:

```bash
python run_all.py --experiment e3_scaling
python experiments/plot_scaling.py
python experiments/summarize_scaling.py
```

## Where checking stops being practical

"Practical" here means **TLC finishes the whole state space within the time limit on this laptop**. That is my definition, not a standard one. Three generated graphs were run at each size.

| ECUs | Finished | Limit (s) | Median distinct states | Median time (s) | Peak memory (MB) |
| --- | --- | --- | --- | --- | --- |
| 5 | 3 of 3 | 1200 | 23,979 | 4.94 | 365 |
| 6 | 3 of 3 | 1200 | 47,120 | 6.58 | 629 |
| 7 | 3 of 3 | 1200 | 275,083 | 13.10 | 1,540 |
| 8 | 3 of 3 | 1200 | 4,500,928 | 274.89 | 1,914 |
| 9 | **2 of 3** | 1200 | 9,050,115 (finished runs only) | 662.59 (finished runs only) | 2,218 |
| 10 | **0 of 3** | 1200 | none | none | 2,189 |
| 20 | **0 of 3** | 300 | none | none | 1,686 |
| 50 | **0 of 3** | 300 | none | none | 1,540 |

- **Direct checking of S1 to S4 stops being practical at 9 to 10 ECUs.** All graphs finish at 8, two of three at 9, none at 10.
- With a 5-minute budget, the limit would be 8 ECUs, and only just: the slowest run took 294.85 s.
- **Time was the limit, not memory.** Peak memory stayed at 2,218 MB or less under the 4 GB heap.
- The medians at 9 ECUs leave out the graph that did not finish, so they understate the true cost.
- N = 20 and 50 had only 300 s, so they show that TLC did not finish in 5 minutes, not that it never would. Runs that stopped report no state totals, so no state count at those sizes is claimed.
- **The graph matters as much as the size.** Fewer dependencies mean more reachable interleavings: at 7 ECUs, the graph with 1 edge had 1,172,561 states, and the graph with 6 edges had 190,288. Three graphs per size is too few to fit a growth rate, so none is reported.

**L1 (liveness)** was run only at 3 to 6 ECUs, and all 12 runs finished, with L1 holding. Nothing is claimed for L1 above 6 ECUs.

## The reduction: pair abstraction

Instead of checking N ECUs together, check two ECUs against an environment that may fail at any time. The argument is in [PAIR_ABSTRACTION_SOUNDNESS.md](PAIR_ABSTRACTION_SOUNDNESS.md).

| Claim | Status |
| --- | --- |
| S1 to S4 for any N, acyclic dependencies and any fault budget | **Hand-written proof.** Not machine-checked in full |
| L1 for any N | **Argument only, not a proof** |
| Real vehicles | No claim. This is about the TLA+ model |

**Cost.** The correct design needs two pair models. They have 197 and 148 distinct states, and took 1.93 s and 3.57 s. This does not grow with N. At 9 ECUs, the median monolithic run has about 45,940 times as many states as the larger pair model.

**Checks by machine, which support the proof but do not replace it:**

| Check | Result |
| --- | --- |
| Refinement: every monolithic step maps to a pair step | 36 of 36 runs hold |
| Negative control: the same check with `EnvFail` disabled | Violated, as it must be, so the check can fail |
| Pair prediction against monolithic verdict, N = 3, 4, 5 at 2 faults, all 4 designs | 144 comparisons: 109 both hold, 35 both violated |
| Unsound results (pair says safe, monolithic finds a violation) | 0 of 144 |
| Spurious alarms (pair warns, monolithic is safe) | 0 of 144 |

The abstraction is an over-approximation, so spurious alarms are possible in general. Zero here applies only to these 144 comparisons, on these graphs and flaws.

## Caveats

- **Manifest:** `dirty_files` lists one entry, `results/scaling.csv`, the run's own output. No code was uncommitted. The manifest check was changed in `a11f7a0` to ignore that output. By the letter of `results/README.md` this run has a non-empty list, which is why it is declared here.
- **Timing noise:** my development work overlapped this run's N = 5 and 6 monolithic timings. State counts are unaffected, but times at those sizes are less reliable than the others. Each configuration ran once, so there is no timing variance.
- **Limits differ from `PLAN.md`:** the plan said 4 hours and 10 GiB. This run used 300 s and 1,200 s with a 4 GB heap, to fit the laptop. A longer limit or a server would move the boundary. Q4 in `PLAN.md` (server access) is unanswered.
- **Fault budget:** scaling used 1 fault. More faults would likely lower the boundary, but that was not measured beyond N = 5.
- **Peak memory** is the JVM's resident size, which depends on heap and garbage collection, so it is not a precise measure of what the search needs.
- **One machine, one tool.** No symbolic checker (Apalache) or multi-worker TLC was tried.
