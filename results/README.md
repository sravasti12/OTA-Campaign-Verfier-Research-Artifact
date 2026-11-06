# Results

Every number in the paper must trace back to a file here, produced by a script in this repo.

| Folder | Contents | Rule |
| --- | --- | --- |
| `predictions/` | Model verdicts for validation experiments | Committed and tagged **before** the matching SIL or testbed run |
| `raw/<experiment>/<run-id>/` | Unedited CSV, JSON and logs, with a `manifest.json` | Never edited or overwritten; a new run gets a new folder |
| `processed/` | Tables and summaries | Generated from `raw/` by scripts only |

A manifest records the commit, uncommitted files, seed, environment, commands, exit codes and artifact hashes. A run whose
`dirty_files` is not empty must not be used in the paper.

Runs that hit a limit stay in the data as `DNF(time)` or `DNF(memory)`. Skipped stages make a run `incomplete`, never `passed`.

`raw/smoke/` is git-ignored: smoke runs check the toolchain and are not results.
