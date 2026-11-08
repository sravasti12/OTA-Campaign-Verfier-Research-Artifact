# Incomplete run: do not cite

This SIL sweep, from commit `239d040` (tag `e5-predictions-frozen-v0`), stopped after 1,556 of 6,360 runs with exit code 4. It printed no Python traceback and wrote no manifest. The cause is unknown. The Windows event log shows other applications hanging and crashing at the same time, so the process may have been killed from outside.

It is kept because the rules say runs are never discarded. It is not evidence.

`observations.jsonl` has a known defect: its `campaign` field holds the end state, which overwrote the campaign name. Lines can be matched to `results/predictions/e5/predictions.jsonl` only by line order. This was fixed in `19423e3`.

This note was added afterwards, by hand. Every other file in this folder is as the run left it.
