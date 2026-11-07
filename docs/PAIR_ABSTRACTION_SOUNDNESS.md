# Pair abstraction: soundness

| Claim | Status |
| --- | --- |
| Theorem 1: S1 to S4 on any N reduce to two pair models | **Proof**, written by hand. Not machine-checked in full; see "What was checked by machine" |
| L1 (the campaign finishes) for any N | **Argument only, not a proof.** The abstraction says nothing about L1 |
| Any claim about real vehicles | **None.** Everything here is about the TLA+ model as written |

The proof was written before the scaling experiment was run.

## Why a reduction is possible

Checking the whole vehicle at once multiplies the states of every ECU. But S1 to S4 each talk about at most two ECUs at a time, and each ECU's
steps depend on the others in only a few ways: the dependency guards, and the shared campaign state. So we can look at two ECUs and treat the rest
of the vehicle as an unpredictable environment that may fail at any moment.

## Definitions

**Full model.** `C(E, D, F, Flaw)` is `specs/tla/OTACampaign.tla`, with ECU set `E`, `|E| >= 2`, dependency set `D`, fault budget `F`, and design `Flaw`.
`D` is acyclic: in particular, no pair `{a, b}` has edges in both directions.

**Pair model.** `A(P, D_P, Flaw)` is `specs/tla/OTAPair.tla`, with `P = {a, b}` a subset of `E`, and `D_P` the edges of `D` with both ends in `P`.
It has no `faults` variable and no fault budget. It also has one extra action:

`EnvFail`: if `campaign = "run"`, set `campaign` to `"rollback"`, changing nothing else.

**Abstraction function.** For a full-model state `s`, `alpha(s)` is the pair-model state with:

- `active`, `inactive`, `stage`, `corrupt`: those of `s`, restricted to `P`
- `campaign`: that of `s`
- `culprit`: `culprit(s)` intersected with `P`
- `faults`: dropped

## Lemma 1: initial states

`alpha` maps the initial state of `C` to the initial state of `A`.

*Proof.* Both set `active` to 1, `inactive` to 0, `stage` to `idle`, `corrupt` to false, `campaign` to `"run"`, and `culprit` to empty. Restricting to `P` preserves this. ∎

## Lemma 2: steps

If `s -> t` is a step of `C`, then `alpha(s) -> alpha(t)` is a step of `A` or `alpha(s) = alpha(t)`.

*Proof.* By cases on the action of `C`. Let `z` be an ECU outside `P` and `e` an ECU inside `P`.

**Actions on an ECU outside `P`:**

| Action of `C` | Effect visible through `alpha` | Step of `A` |
| --- | --- | --- |
| `Download(z)`, `Verify(z)`, `Activate(z)`, `Confirm(z)`, `Rollback(z)`, `DownloadCorrupt(z)` | None. They change only `z`'s entries and `faults` | Stutter |
| `DownloadFail(z)`, `TrialFail(z)`, `VerifyReject(z)` | `campaign` goes from `"run"` to `"rollback"`. `culprit` gains `z`, which `alpha` removes | `EnvFail`. Its guard holds because these actions require `campaign = "run"` |

**Actions on an ECU inside `P`:**

| Action of `C` | Why `A` can match it |
| --- | --- |
| `Download(e)`, `Verify(e)`, `VerifyReject(e)`, `Confirm(e)` | Same guard and same effect on the visible variables. The guards read only `e`'s entries, `campaign` and `Flaw` |
| `DownloadFail(e)`, `DownloadCorrupt(e)`, `TrialFail(e)` | As above. `C` also requires `faults < F`; `A` has no such guard, so `A`'s guard is weaker. `culprit` gains `e` in both |
| `Activate(e)` | `C` requires `active[d] = 2` for every `<<e, d>>` in `D`. `A` requires this only for edges in `D_P`, a subset. Weaker guard, same effect |
| `Rollback(e)`, correct design | `C` requires `active[x] = 1` for every `<<x, e>>` in `D`. `A` requires this only for `D_P`. Weaker guard. Scope is all ECUs in both, and `e` is in both |
| `Rollback(e)`, `LocalRollback` | `C` requires `e` in `culprit`. As `e` is in `P`, `e` is in `culprit` intersected with `P`. There is no order guard in either |

**Actions on no single ECU:**

| Action of `C` | Why `A` can match it |
| --- | --- |
| `Commit` | `C` requires every ECU in `E` healthy, which includes `P`. `A` requires only `P`. Weaker guard, same effect |
| `FinishRollback`, not `LocalRollback` | `C` requires `active = 1` on all of `E`, which includes `P`. Weaker guard |
| `FinishRollback`, `LocalRollback` | `C` requires `active = 1` on `culprit`. `A` requires it on `culprit` intersected with `P`, a subset. Weaker guard |
| `PowerLoss` | `C` requires `faults < F`, which `A` does not. Both require `campaign` to be `"run"` or `"rollback"`. The update is per ECU, so it restricts to `P` exactly. `culprit` is unchanged in both |

Every action of `C` is covered. ∎

## Lemma 3: reachability

If `s` is reachable in `C`, then `alpha(s)` is reachable in `A`.

*Proof.* Induction on the length of the behaviour, using Lemmas 1 and 2. ∎

## Lemma 4: renaming

`A` uses ECU names only through equality and set membership, so renaming the two ECUs preserves all its behaviours and properties. Since `D` is
acyclic, every pair has one of two shapes up to renaming: **none**, with no edge, or **edge**, with one edge `<<a, b>>`.

## Theorem 1

Fix `Flaw`. Suppose TLC reports that S1 to S4 hold in both pair models, `A({a, b}, {}, Flaw)` and `A({a, b}, {<<a, b>>}, Flaw)`. Then S1 to S4 hold in
every reachable state of `C(E, D, F, Flaw)`, for **every** finite `E` with `|E| >= 2`, every acyclic `D`, and every `F`.

*Proof.* Let `s` be reachable in `C`.

- **S1.** Take any `<<x, d>>` in `D` and let `P = {x, d}`. By Lemma 3, `alpha(s)` is reachable in the edge-shaped `A`, where `CompatAlways` holds by Lemma 4.
  So `active[x] = 2` implies `active[d] = 2`, in `alpha(s)` and therefore in `s`.
- **S2 and S4.** Take any `e` in `E`, and any `P` containing `e`, which exists as `|E| >= 2`. The pair property for `e` transfers in the same way. `campaign` is preserved by `alpha`.
- **S3.** Suppose `campaign(s)` has ended. For any two ECUs `a` and `b`, the pair property at `P = {a, b}` gives `active[a] = active[b]`. Equality on every pair
  means all ECUs have the same version, and versions are 1 or 2. ∎

The result covers every fault budget because `A` allows unlimited faults.

## The other direction does not hold

The abstraction **adds** behaviour, so a violation in a pair model may not exist in the full model. A pair verdict of "holds" is a guarantee. A pair verdict of "violated" is only a
warning that needs checking against the full model. For example, `Rollback` in a pair model ignores dependents outside the pair.

The experiment measures this as the spurious rate in `agreement.csv`.

## What was checked by machine

The proof itself was not machine-checked, and no proof assistant such as TLAPS was used. These checks reduce the risk of a mistake in it:

1. **Refinement check.** On small generated campaigns, TLC checked that `C` refines `A` through `alpha`, for every ECU pair and all four designs. This is Lemmas 1 and 2 tested
   mechanically on those instances. It also guards against `OTAPair.tla` and `OTACampaign.tla` drifting apart, which matters because `OTAPair.tla` repeats their shared actions by hand.
2. **Negative control.** The same refinement check, with `EnvFail` turned off, must fail. This shows the check can detect a broken abstraction.
3. **Agreement.** Pair predictions are compared with full-model verdicts on small campaigns, across all designs. Any case of "pair holds, full model violated" would refute the theorem.

These checks cover finite instances only. For larger N, the result rests on the hand proof.

## Assumptions the proof depends on

Changing any of these means the proof must be redone:

- **`campaign` is one shared, atomically updated variable.** Every ECU sees the same value at once. A real coordinator talks to ECUs by message. Adding message delay or loss adds
  behaviours this proof does not cover, and is likely to break S3's argument first.
- **Every property is about at most two ECUs.** A property such as "at most 3 ECUs are unavailable at once" does not decompose this way.
- **Every dependency is between two ECUs.** Compatibility rules naming three ECUs would need triples.
- **Versions go only from 1 to 2.**
- **`D` is acyclic.** A two-way dependency would be a third shape, which would need its own pair model. The theorem as stated excludes it.
- **TLC and the model are correct.** The theorem is about this TLA+ text.

## L1 (argument only, not a proof)

**This section is an argument. It has not been proved or machine-checked for general N.** The pair abstraction cannot support it, for two reasons: simulation preserves safety and not liveness,
and `A` has no fairness and has unlimited faults.

The reasoning for the correct design, with a finite fault budget and acyclic `D`:

1. Faults are bounded, so some point exists after which there are none.
2. While `campaign = "run"`, each ECU's stage only moves forward, unless a fault intervenes. Fairness makes each enabled step eventually happen.
3. An ECU waiting to activate waits only for its dependencies. As `D` is acyclic, the ECU earliest in dependency order is never blocked. So either all ECUs become healthy and `Commit` is enabled,
   or a corrupt image is rejected and rollback starts.
4. While `campaign = "rollback"`, S2 ensures that each ECU on version 2 holds version 1. Since `D` is acyclic, some ECU on version 2 has no dependent on version 2, so a rollback step is enabled.
   Each step reduces the number of ECUs on version 2. When it reaches 0, `FinishRollback` is enabled.

Step 4 relies on S2, which Theorem 1 does establish. Step 3 is the informal part. Note that acyclicity is needed: with a dependency cycle, `Activate` can deadlock, and L1 fails.

TLC checks L1 directly only for the small sizes in `scaling.csv`.

## Prior work

The approach is a standard one: an over-approximating abstraction that preserves safety, and reasoning about components in a stand-in environment, in the spirit of compositional model checking
(Clarke, Long and McMillan, LICS 1989). Results that a small fixed size suffices for a whole family relate to cutoffs (Emerson and Namjoshi, POPL 1995), though the proof here is direct and does not
use those theorems. Whether the same reduction has been published for update campaigns remains an open question for the week 2 literature search.
