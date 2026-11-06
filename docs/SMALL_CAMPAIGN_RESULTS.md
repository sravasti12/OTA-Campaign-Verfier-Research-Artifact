# Small campaign: model-checking results

The model and property definitions are in [../specs/SMALL_CAMPAIGN.md](../specs/SMALL_CAMPAIGN.md).

**Evidence:** `results/raw/e0_small_campaign/20261106T140103Z-fc95dee/`, with `results.csv`, full TLC logs in `logs/`, and traces
in `traces/` as JSON and readable tables. This run was made in a fresh checkout of commit `fc95dee`, and its manifest lists no
uncommitted files.

Two earlier runs, `20261106T133224Z-c026fa9` and `20261106T133416Z-c026fa9`, were made with uncommitted files and are kept for
history only. All three gave identical results apart from wall-clock time, and byte-identical traces.

All three ran on the same Windows machine. Reproduction on another machine has not been tested.

Reproduce with:

```bash
python run_all.py --experiment e0_small_campaign
```

## Result

TLC 2.19 ran 63 checks: 4 designs, 5 properties and 3 fault budgets, plus 3 sanity checks. Every verdict at the highest budget
matched the expectation recorded before the first run, and every counterexample passed a separate Python replay that does not use TLC.

Verdicts at a budget of 2 faults, with the smallest budget at which each violation appeared:

| Design | S1 compatible | S2 way back | S3 all or nothing | S4 verified | L1 finishes |
| --- | --- | --- | --- | --- | --- |
| Correct | holds | holds | holds | holds | holds |
| `LocalRollback` | **violated** (1 fault) | holds | **violated** (1 fault) | holds | holds |
| `EarlyErase` | holds | **violated** (0 faults) | holds | holds | **violated** (1 fault) |
| `SkipVerify` | holds | holds | holds | **violated** (1 fault) | holds |

The correct design was fully explored at each budget:

| Fault budget | States generated | Distinct states |
| --- | --- | --- |
| 0 | 218 | 96 |
| 1 | 1,077 | 674 |
| 2 | 2,080 | 1,224 |

**Sanity checks.** A property can pass simply because the model never does anything. So TLC was also asked to find, in the correct
design, a commit, an abort, and a real rollback of an ECU. It found all three, so the correct design's passes are not empty.

## Counterexamples in plain language

Each table row in the trace files is one step. "Spare" means the version held in the ECU's other slot.

### Flaw 1: `LocalRollback`, breaks S1 (compatibility)

Trace: `traces/LocalRollback__S1__F1.md`, 9 states, 1 fault.

1. Gateway downloads, verifies and activates version 2.
2. Brake does the same. This is allowed, because gateway is already on version 2. Both are now in their trial period.
3. Gateway fails its health check. That is the only fault.
4. The coordinator rolls back only the ECU that failed, so gateway returns to version 1.

**Result:** brake runs version 2 while gateway runs version 1, which the dependency forbids. Brake was healthy and did nothing wrong.
The harm came from fixing the failed ECU alone.

The mix is also permanent in this design: brake is outside the rollback scope, so the campaign ends as aborted with the vehicle
still incompatible. This is the "roll back A without B" case you asked about.

The correct design avoids it by reverting brake first, because brake depends on gateway.

### Flaw 1: `LocalRollback`, breaks S3 (all or nothing)

Trace: `traces/LocalRollback__S3__F1.md`, 6 states, 1 fault.

1. Gateway activates version 2.
2. Brake's download fails before it has changed anything.
3. Brake is the only ECU blamed, and it has nothing to undo, so the rollback finishes at once.

**Result:** the campaign is declared aborted with gateway still on version 2 and the others on version 1.

This is a different failure from the one above. This mix is compatible, because the dependency only constrains brake. S1 holds here
and S3 does not. So whether this state counts as a bug depends on what "consistent" means, which is why `PLAN.md` keeps strict and
weak versions of this property. The vehicle is left in a state nobody planned, while the campaign record says it was aborted.

### Flaw 2: `EarlyErase`, breaks S2 (a way back is kept)

Trace: `traces/EarlyErase__S2__F0.md`, 4 states, **no faults**.

1. Gateway downloads and verifies version 2.
2. Gateway activates it and erases version 1 to free flash. Its spare slot is now empty.

**Result:** gateway is on an unproven version with nothing to go back to. No fault is needed: every run of this design breaks S2.

### Flaw 2: `EarlyErase`, breaks L1 (the campaign finishes)

Trace: `traces/EarlyErase__L1__F1.md`, 11 states, 1 fault.

1. Brake's download arrives corrupt. Nothing notices yet.
2. Gateway and infotainment both activate version 2, pass their health checks, and erase their old images.
3. Brake's verification rejects the corrupt image, correctly, and the campaign starts rolling back.
4. Gateway and infotainment have nothing to roll back to.

**Result:** the campaign stays in "rollback" forever. It can never commit, because a rollback is under way. It can never abort,
because two ECUs cannot revert. The trace ends in that stuck state.

Note that the fault was handled correctly. The design failed because of a decision made earlier, which had looked harmless on the
successful path.

### Extra variant: `SkipVerify`, breaks S4 (only verified images run)

Trace: `traces/SkipVerify__S4__F1.md`, 4 states, 1 fault.

1. Gateway's download arrives corrupt.
2. Verification passes it anyway.
3. Gateway activates it.

**Result:** gateway runs a corrupt image. This variant is simple, and exists only to show S4 can fail, so that S4's pass on the correct
design means something.

## What the results show

1. **`LocalRollback` cannot be seen without a fault.** With 0 faults it passes all five properties, so nominal testing would not find it.
2. **One property can hide a problem.** `EarlyErase` "holds" S3 only because the stuck campaign never ends. S3 says nothing about a
   campaign that never finishes. It takes S3 and L1 together to rule that out.
3. **Different properties catch different bugs.** Each of the 5 properties was violated by at least one design.

## Limits

- This is one 3-ECU campaign, at most 2 faults, with the simplifications listed in
  [SMALL_CAMPAIGN.md](../specs/SMALL_CAMPAIGN.md). In particular it has no timeouts, retries or message loss, and rollback switches are atomic.
- A pass means no violation exists within this model. It says nothing about real ECUs. Nothing here has been compared with a simulator or
  testbed yet.
- We wrote the flaws ourselves, and predicted the outcome. These runs show the model and checker behave as designed. They do not show how
  often such bugs occur.
- Liveness traces are not guaranteed shortest. `EarlyErase` L1 took 11 states at budget 1 and 7 at budget 2. Safety traces come from
  breadth-first search, so they are shortest for this model.
- `SkipVerify` generates more states than the others at 0 faults (277 against 218) with the same 96 distinct states. Its `Verify` guard has two
  true branches, so TLC counts that step twice. This does not affect verdicts.
- Wall-clock times are in `results.csv` but are dominated by Java start-up, so they say nothing about scalability.
