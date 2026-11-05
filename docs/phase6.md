# Phase 6: guarded trial boot and recovery-policy comparison

Phase 6 compares the original simulator with a guarded trial-boot policy. It is
an extension of the simulation model, not a hardware bootloader implementation.
The original baseline engine, fault schema, 14-case matrix, compatibility rule,
and downgrade authorization policy are preserved.

## Try the comparison

Start the existing local app:

```powershell
.\.venv\Scripts\python -m streamlit run app/streamlit_app.py
```

Open `http://localhost:8501` and:

1. Select **Authorized rollback comparison** and click **Load example**.
2. Enable **Compare guarded trial boot** and choose the maximum trial attempts.
3. Click **Analyze revision**.
4. Open **Faults** to inspect paired outcomes, both traces, and guarded-only
   confirmation cases.

The synthetic example explicitly includes an original-version rollback
permission for every ECU in its source-only inventory JSON. These permissions
are inspectable input data; neither the LLM nor the review decision grants them.
It produces **42 common cases**, **48 total guarded cases**, and **6 guarded-only
confirmation cases**. Three boot-failure cases improve under the declared model:
the baseline retains violations while guarded boot passes its complete sweep.
The baseline remains the primary analysis/review gate. A guarded passing result
cannot overwrite baseline violations or unlock approval for that baseline.

The default remains baseline-only. Comparison controls are draft inputs; editing
them makes previous results stale and requires explicit reanalysis. The options,
raw comparison reports, assumptions, and explanation evidence are included in the
review snapshot hash and exported bundle. Disabling comparison omits the new
optional fields from serialized inputs/artifacts, preserving the earlier baseline
snapshot shape. Completed analysis/model calls are not repeated on UI rerenders.

If a live workspace predates the updated graph, the app offers its old bundle
for download and an explicit **Keep previous workspace and start Phase 6** action.
The previous service remains in session memory; no review data is silently reset.
As before, session memory does not survive browser-session loss or process restart.

For a headless deterministic comparison:

```powershell
.\.venv\Scripts\python -m ota_verifier.cli examples/authorized_boot_campaign.json --max-parallel 2 --compare-boot-policies --trial-attempts 2
```

The CLI returns exit 4 when either policy has observed violations, 5 for an
inconclusive assessment if neither has violations, and 0 if both pass. Planning
infeasibility/unknown remain exits 2/3 and do not trigger comparison. Exit 4 on
the provided example is expected because the baseline still fails its boot cases.

## Agreed boot semantics

A `GuardedSnapshot` separates:

- **Image integrity:** the existing `Image.valid` flag, independently of boot health.
- **Observed boot health:** unknown, passed, or failed for each stored slot.
- **Last effective installed image:** the core `VehicleState.active_slot` projection.
- **Running slot and availability:** unavailable ECUs have `running_slot=None`.
- **Confirmed slot:** the durable selection used first after a simulated power loss.
- **Trial candidate and attempt counter:** a candidate is not yet a running image.

A failed candidate never becomes effective. Keeping the original image after an
unsuccessful attempt therefore retains the current version; it is not an implicit
downgrade authorization. Once a trial passes health checking, its version becomes
effective immediately, before confirmation. Returning to an older image from that
point requires exact ECU/version permission, whether or not confirmation occurred.

Availability is explicit and separate from the four invariants. An unavailable
ECU has no running image; its last effective version still participates in every
compatibility check. The simulator never resets that version to an older value
just because power was lost. A dependent cannot newly boot while its applicable
required ECU is unavailable. Compatibility remains defined only in `compat.py`;
the availability gate is an additional operational check.

These semantics model withholding a candidate from effective operation until its
health check passes. They do not claim that a failing boot attempt itself cannot
occur, that availability is uninterrupted, or that a real ECU can implement this
isolation without additional engineering.

## Stages and persistence

The guarded timeline retains erase, write, verify, activate, and boot, then adds
**confirm**. Start, midpoint, rounded write duration, and ordered completion rules
match the supplied nominal plan.

| Boundary | Guarded behavior |
| --- | --- |
| Erase/write | The inactive target remains integrity-invalid and health-unknown; the old image remains effective/running. |
| Verify | Integrity becomes valid; boot health is still unknown. Corruption blocks trial boot. |
| Activate | Select a trial candidate and mark the ECU unavailable. The last effective version and confirmed pointer do not change. |
| Successful boot | Record passed health, check compatibility/authorization/dependency availability, then expose the candidate as effective and running. |
| Confirm | Atomically persist the healthy running candidate as confirmed and clear trial selection. |
| Failed boot health | Record a failed health result with intact image integrity, spend the bounded trial budget, then retain/restart an allowed confirmed image. The failed candidate is never exposed. |

The `boot_failure` fault represents one persistent unhealthy-candidate cause.
Repeated failed attempts consume its configured budget; they are not additional
independent injected faults. The budget is 1–10 attempts, default 2.

Across a simulated power loss, confirmed selection, attempt count, and observed
slot-health facts survive. Runtime availability and candidate selection do not.
All in-progress writes are invalidated, while verified images are retained.
All ECUs become unavailable until an allowed boot occurs. Power restoration uses
the same supplied battery/ignition environment.

Confirmed-slot writes are atomic. Power loss **before confirm** retains the old
pointer; power loss **after confirm** retains the new pointer. Counter state is
not reset by an outage. Here durability means persistence across a modeled power
loss within one run, not database persistence or recovery after a Python crash.

Boot, health checks, retries, confirmation, and recovery are logical events with
no modeled elapsed duration. The comparison does not optimize reboot latency,
measure downtime, model torn metadata writes, or establish real-time scheduling.
There are no multiple-independent-fault sequences in this phase.

## Fallback and coordinated recovery

After failure, the campaign stops and remaining writes are canceled. Unavailable
ECUs first try their persisted confirmed slots in a dependency-compatible order.
Every proposed boot must pass image health/integrity, version compatibility,
authorization, and availability checks. A rejected automatic fallback is recorded
as a blocker and is never emitted as an executed version transition.

The controller then searches for a path to the previously selected recovery goal:
**original effective images, original confirmed slots, and all ECUs available**.
The bounded search may explicitly boot other stored, known-healthy images to
coordinate recovery. It does not invent, repair, reflash, or assume health for an
unknown/failed image. Every executed recovery action records unavailability,
healthy exposure, and confirmation as distinct trace events.

The four invariant meanings remain:

1. Images exposed as running must have valid integrity and successful health.
2. Every observed effective-version configuration satisfies the shared dependencies.
3. New valid older installations and effective downgrades require explicit permission.
4. A failed step has a proved permitted path back to the original running images.

Reboot unavailability is not disguised as an invalid running image or a compatible
running service. It is separately visible. Rejected proposals are diagnostic
blockers, while invariant findings describe actual observed states/transitions.
Historical findings are retained after recovery. A proven missing path violates
invariant 4; an exhausted search is unknown, not proof of failure or a pass.
Known historical violations still dominate an overall assessment even if another
part of recovery is inconclusive.

The stronger original-image recovery goal can fail even if a compatible partial-
update safe stop would be possible. That policy choice remains unchanged.

## Honest comparisons

Shared causes are paired by ECU, fault kind, stage, and before/after boundary.
Each policy applies that cause according to its own state machine. These are
stage-relative logical comparisons, not identical physical timing experiments.

The report retains all raw baseline and guarded cases and distinguishes:

- **Improved:** baseline violations become a fully passing guarded case.
- **Regressed:** a baseline pass becomes guarded violations.
- **Changed findings:** the coarse verdict stays the same but findings/recovery differ.
- **Unchanged:** verdict, invariant signatures, and recovery status agree.
- **Inconclusive:** either paired assessment is inconclusive; no proven improvement
  or regression is claimed for that pair.

The 14 baseline cases per updated ECU are all present in guarded coverage. The
extra two power-loss boundaries around confirmation are reported separately,
giving 16 guarded cases per ECU. New boundaries are never dropped to make a
success rate look better. No-op campaigns explicitly have zero cases and do not
demonstrate an improvement. Validators recompute paired outcomes and counts,
reject missing cases, and check declared trial budgets against recorded attempts.

An important negative example has two ECUs each requiring the other to be
available during boot. After global power loss, neither can boot first under the
sequential availability guard. This is reported as a cold-start regression rather
than silently enabling atomic/cohort boot. The baseline has no availability model,
so this identifies an extra operational requirement, not a measured hardware
performance regression. Missing downgrade permissions, unusable fallback images,
and bounded-search uncertainty are also retained as negative/inconclusive outcomes.

## API

```python
from ota_verifier.boot_comparison import compare_boot_policies
from ota_verifier.boot_models import GuardedOptions
from ota_verifier.guarded_simulator import simulate_guarded
from ota_verifier.models import Campaign, FeasibleResult
from ota_verifier.planner import plan_campaign
from ota_verifier.simulation_models import FaultSpec
from pathlib import Path

campaign = Campaign.model_validate_json(
    Path("examples/authorized_boot_campaign.json").read_text(encoding="utf-8")
)
planned = plan_campaign(campaign)
assert isinstance(planned, FeasibleResult)
comparison = compare_boot_policies(campaign, planned.plan,
                                   guarded_options=GuardedOptions(max_trial_attempts=2))
assert comparison.baseline.assessment == "violations"
assert comparison.guarded.assessment == "passed"

fault = FaultSpec(ecu_id="gateway", stage="boot", kind="boot_failure")
run = simulate_guarded(campaign, planned.plan, fault)
```

The guarded simulator and policy comparison do not call Z3, replan, or call LLMs.
Planning remains a separate deterministic step. The optional graph comparison
node reuses its already-computed baseline report and adds guarded results before
explanation/review. Advisory explanations preserve the primary analysis status
and cite separate comparison, guarded-assessment, and assumption facts.

## Verification

```powershell
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m pytest -q tests/test_guarded_boot.py tests/test_boot_comparison.py tests/test_exhaustive_guarded_recovery.py tests/test_boot_workflow.py tests/test_boot_review_app.py tests/test_boot_cli.py
```

The original baseline tests remain intact. New tests check failed-trial retention,
health/integrity separation, successful unconfirmed exposure, atomic confirmation
boundaries, retained counters, concurrent power loss, permission blocks,
dependency availability, unsafe fallback rejection, coordinated recovery,
unknown search results, negative cold-start cases, complete fault coverage,
forgery-resistant report consistency, snapshot binding, CLI behavior, live-workspace
retention, and real Streamlit interactions. Ten small recovery cases are compared
with an independent exhaustive state graph and Floyd–Warshall shortest paths.
All checks are offline; no live model or hardware validation is claimed.
