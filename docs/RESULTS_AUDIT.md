# Results audit, 2026-11-07

A hostile-reviewer pass over everything planned for the paper. **Nothing has been fixed yet.** It covers the research artifact only (E0, E3, E5, the pair abstraction and the testbed plan), not the LLM and planner workstreams in `eval/`.

State audited: `main` at `fd10fba` (pushed to origin), and the local detached commits `a11f7a0` and `239d040` (tag `e5-predictions-frozen`, not pushed).

**Not done:** the full from-scratch re-run in a fresh terminal (step 1 of your plan). It takes about 3 hours for E3 alone, and E5 cannot currently finish (C1).

## Where each planned number comes from

| Planned item | Script | Raw file | Status |
| --- | --- | --- | --- |
| E0 verdict table and state counts | `experiments/e0_small_campaign.py` | `results/raw/e0_small_campaign/20261106T140103Z-fc95dee/results.csv` | Clean run, on main. Doc numbers typed by hand (M4) |
| E0 counterexample traces | same | `.../traces/` | On main |
| Scaling table and plot | `experiments/e3_scaling.py`, `plot_scaling.py`, `summarize_scaling.py` | `results/raw/e3_scaling/20261106T141615Z-ce3eefb/scaling.csv` | On main. Manifest names a commit not on origin (C2) and is not clean (H2) |
| Pair cost, refinement, agreement | `experiments/e3_scaling.py` | `pair_checks.csv`, `refinement.csv`, `agreement.csv` in the same run | On main |
| Model predictions | `experiments/e5_predict.py` | `results/predictions/e5/predictions.jsonl`, `results/raw/e5_predict/20261106T170040Z-a11f7a0/` | **Not on main**, local only (C2) |
| Model against SIL confusion table | `experiments/e5_sil.py` | none | **Does not exist** (C1) |
| Hardware results | none | none | **Testbed not built** (C3) |

## Problems, most severe first

### Critical: the paper cannot be written on these until fixed

**C1. No validation result exists.** The full SIL sweep stopped after 1,556 of 6,360 runs with exit code 4. There was no Python traceback, and no manifest, `comparison.csv` or `confusion.csv` was written. The cause is unknown. Exit code 4 is not one the scripts use, and the Windows event log shows other applications hanging and crashing at the same time (22:50 to 22:53), so the process may have been killed from outside. Contribution 4 has no citable number until a complete run exists.

- For information only, not a result: the 1,556 completed runs (`small` and part of `n5_s1`) all match the predictions, with 0 misses, 0 false alarms, and identical action paths and end states. This was computed by hand from a partial file, so it must not appear in the paper.

**C2. A reader cannot check the provenance chain from the public repo.**

- The E3 manifest names commit `ce3eefb`, and the predictions were frozen in `239d040`. **Neither is on origin.** `main` is one squashed commit, `fd10fba`, so "predictions were committed before the SIL run" cannot be verified from GitHub.
- The source code on `main` matches `239d040` for `experiments/`, `sil/`, `specs/`, `src/ota_verifier/formal/` and `run_all.py`. Only `experiments/summarize_scaling.py` was added. So the code itself has not drifted.
- The predictions and the `e5_predict` raw run are only on the local tag `e5-predictions-frozen`, held in a worktree in a temporary folder. The commits live in the repo's object store, so deleting the folder would not lose them. But nothing outside this laptop has them.

**C3. There is no hardware testbed.** `docs/RASPBERRY_PI_TESTBED.md` is a plan only, untested. The paper must report a software-in-the-loop validation and list the testbed as future work.

### High

**H1. A bug makes the raw SIL observations ambiguous.** In `experiments/e5_sil.py` line 92, the observation's `campaign` field (the end state) overwrites the campaign name. So each line in `observations.jsonl` says `committed` or `aborted` instead of `small` or `n5_s1`. `comparison.csv` is unaffected, because it takes the name from the prediction. But the raw file can only be joined to predictions by line order, not by key.

**H2. The E3 manifest is not clean by the repo's own rule.** `dirty_files` lists `results/scaling.csv`, the run's own output. No code was uncommitted, but `results/README.md` says such a run must not be used. Either re-run (about 3 hours) or document the exception before using it.

**H3. The validation is close to circular.** The same author wrote the model, the SIL and the fault scripts. The SIL follows the same written schedule as the scripted model. And the SIL can inject only the fault kinds the model already has. The 100% path agreement in the partial run suggests this is a differential test of two implementations of one design, not independent evidence. A reviewer will say the SIL cannot find a fault class the model lacks, such as torn writes or message loss. Options: an independent update client (the RAUC route), fault kinds outside the model, or stating it plainly as a threat to validity.

**H4. The pair-abstraction proof has not been checked by anyone else.** `docs/PAIR_ABSTRACTION_SOUNDNESS.md` is a hand proof, supported by 36 refinement runs and 144 agreement checks at small N. L1 is argument only. The paper must say "proof sketch" unless someone checks it, or it is mechanised in TLAPS.

**H5. A line-ending setting can break the predictions hash.** `.gitattributes` protects `results/raw/**` but not `results/predictions/**`. On a Windows checkout with `autocrlf`, `predictions.jsonl` would change bytes, and its SHA-256 would no longer match `predictions_sha256.txt`.

**H6. One run per configuration, on one machine.** E3 has no repeat, so timings have no variance. My development work overlapped its N = 5 and 6 timings, though state counts are unaffected. Nothing has run on Linux or in CI: CI runs only the smoke test, and I have not confirmed it passes on GitHub.

### Medium

**M1. The confusion table will overstate agreement unless it is broken down.**

- In the partial run, `match_safe` outnumbers `match_violation` by 7,327 to 453. An accuracy figure would mostly reflect easy safe cases.
- The 6,360 scripts give only 4,428 distinct (campaign, design, policy, path, verdict) combinations, so many runs are duplicates.
- `n5_s1` has no dependency edges, so S1 cannot be violated there.

Report by property and design, count distinct paths, and flag vacuous cells.

**M2. The model is narrower than "multi-ECU OTA" suggests.** The paper must state these limits, not imply more:

- Each ECU has only two versions (1 to 2), and dependencies are "if A is on v2, B is on v2", not version ranges.
- S3 is checked only once the campaign ends, not at intermediate states.
- S2 means the old image is kept, not that it is bootable.
- S4's "corrupt" is a flag in the model and a SHA-256 mismatch in the SIL.
- Power loss hits the whole vehicle at once.
- The coordinator's state is atomic and durable.
- There is no network or message loss, and no timeouts.
- L1 needs weak fairness and a bounded number of faults.
- There is no attacker model or signature checking.

**M3. The scaling claims rest on choices.**

- "Practical" is my definition: finishing in 1,200 s on this laptop.
- N = 20 and 50 got only 300 s.
- The medians at N = 9 leave out the graph that did not finish.
- Only 3 graphs per size, so no growth rate can be fitted.
- Limits differ from `PLAN.md`: 4 h and 10 GiB were planned.
- The fault budget is 1 in scaling, and 2 only at N ≤ 5.

**M4. Numbers in docs are copied by hand.** `docs/SCALING_RESULTS.md` and `docs/SMALL_CAMPAIGN_RESULTS.md` tables were typed from the CSVs. Nothing regenerates or checks them, so they can drift. The paper's tables should be generated by a script, or tested against the CSVs.

**M5. Novelty is not established.** The week 2 systematic search was not done. The closest work, the RAID 2024 Uptane analysis, is unread, and section C of `related_work.md` has 12 unverified entries. Hagen 2025 is checked from the abstract only. Weiß 2025 and Dharavath 2026 are not in `related_work.md` yet.

**M6. The README on `main` does not describe the research artifact.** It covers the planner, LLM and MCUboot work. There is no section on how to reproduce E0, E3 or E5. `main` also mixes in unrelated evaluation workstreams, which a reviewer could confuse with the paper's evidence.

### Low

**L1.** Two E0 runs with uncommitted files are kept, labelled as history. They are fine if never cited.

**L2.** Peak memory is the JVM's resident size, so it depends on heap settings. Use it as an indication only.

**L3.** The author email on `fd10fba` reads `bosesravasti8@gamil.com`, which may be a typo for `gmail.com`. Check this if commit authorship matters for the paper's artifact statement.

**L4. Hard-coded values.** Sizes, seeds, limits and fault budgets are constants in the experiment scripts and are recorded in the outputs. That is fine, but the paper must quote them. Randomness is seeded: graphs use `random.Random(f'{size}:{seed}')` and TLC uses seed 42. No unseeded randomness was found in E0, E3 or E5. The SIL uses no randomness.

## Properties against what the paper may claim

| Property | What the model checks | Safe wording for the paper |
| --- | --- | --- |
| S1 | For every dependency (a, b): if a runs v2, then b runs v2, in every state | "No ECU runs the new version while a dependency runs the old one" |
| S2 | Before commit, every ECU running v2 keeps v1 in its other slot | "The previous image is retained until commit". Not "rollback always succeeds" |
| S3 | At abort or commit, all ECUs are on v1, or all on v2 | "At campaign end", not "atomic" |
| S4 | No ECU runs an image flagged corrupt | "Only images that passed verification run". Not a security claim |
| L1 | Under weak fairness and a bounded number of faults, the campaign reaches commit or abort | "Terminates under fairness and bounded faults" |
