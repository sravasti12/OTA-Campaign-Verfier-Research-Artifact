# Phase 9: explicit campaign policy selection

This phase addresses a review problem: a better result under a different boot
policy must not be mistaken for approval of the original campaign assumptions.
The reviewer now explicitly selects which simulation policy a new revision uses.
All compatibility, planning, faults, recovery, and invariant checks remain
unchanged deterministic code. LLMs still only extract, verify extraction, and
explain recorded evidence.

## Policies and review rules

| Review mode | Overall status and approval source | Evidence retained |
| --- | --- | --- |
| Legacy baseline review | Original v1 rules: baseline must pass; an enabled guarded comparison must also pass | Original snapshot shape and review rules |
| Baseline policy (`baseline-v1`) | Complete baseline nominal execution and fault sweep | Baseline; optional guarded comparison retains its own results |
| Guarded trial boot policy (`guarded-trial-v1`) | Complete guarded nominal execution and fault sweep, including confirmation faults | Both complete baseline and guarded reports, paired regressions, and assumptions |

Selecting guarded policy always runs the comparison, even without the separate
comparison checkbox. Its trial options must be supplied explicitly. If separate
comparison options are supplied, they must match the selected guarded options.
Baseline selection forbids guarded options inside its policy identity; guarded
comparison can instead be requested separately.

A passing guarded policy can be reviewed and approved as a simulation proposal
while baseline violations remain recorded. The baseline assessment is never
rewritten. A failing baseline selection cannot be approved because its comparator
passed. An incomplete, blocked, infeasible, unknown, or violating selected policy
cannot receive approval. Zero-update passing evidence still means zero injected
fault cases, not demonstrated update fault tolerance.

Selecting a policy does not grant original-version rollback authorization or
weaken compatibility, image integrity, availability guards, or invariants.
Guarded dependency-availability cycles remain regressions; bounded recovery
search exhaustion remains inconclusive. Atomic confirmation, instantaneous
trial/reboot timing, single-fault coverage, and all other prior modeling limits
still apply. No new outage or resource-budget physics is claimed.

## Try the UI

```powershell
.\.venv\Scripts\python -m streamlit run app/streamlit_app.py
```

1. Load **Authorized rollback comparison**. Its original-version permissions are
   explicitly synthetic input data.
2. Under **Policy to review**, select **Guarded trial boot policy**. Inspect the
   maximum trial-attempt option, then click **Analyze revision**.
3. The main metric identifies the selected policy. The **Faults** tab retains
   baseline violations alongside passing guarded results and all 48 guarded
   cases, including 6 confirmation cases, for this three-ECU example.
4. Review the deterministic policy summary and assumptions, then record a
   simulation-proposal decision if appropriate.
5. Change the selection to **Baseline policy**. This is an unanalyzed draft
   change; it cannot reuse the old approval. Analyze a new revision: baseline
   violations block approval, and the old decision remains in history.

The default legacy choice avoids silently changing existing workspaces. Opening
saved evidence restores its policy selection and trial options. A workspace
holding an older compiled graph offers an explicit upgrade while retaining the
prior workspace and its export. The persistent library remains optional.

## Python API

```python
from ota_verifier.boot_models import GuardedOptions
from ota_verifier.graph import WorkflowService
from ota_verifier.workflow_examples import example_input, fixture_dependencies
from ota_verifier.workflow_models import PolicySelection, WorkflowInput

request, case = example_input("authorized_rollback")
service = WorkflowService()
bundle = service.start(
    WorkflowInput(
        request=request,
        selected_policy=PolicySelection(
            id="guarded-trial-v1",
            guarded_options=GuardedOptions(max_trial_attempts=2),
        ),
    ),
    fixture_dependencies(case),
)
assert bundle.snapshot.artifacts.status == "simulation_passed"
assert bundle.snapshot.artifacts.simulation.assessment == "violations"
assert bundle.snapshot.artifacts.comparison.guarded.assessment == "passed"
assert bundle.current_decision is None  # Analysis is never automatic approval.
```

Use `PolicySelection(id="baseline-v1")` for explicit baseline review. Omit
`selected_policy` only to retain legacy rules. Use the existing `revise` method
to change policy or options; saved snapshots are never edited in place. The same
input and review APIs work with `PersistentWorkflowService`.

## Versioning, hashes, and persistence

Explicit selections use `workflow-v2` snapshots and `review-bundle-v2` exports.
Legacy input omits the new field when serialized and retains `workflow-v1` and
`review-bundle-v1`. Mismatched schema versions are rejected; historical evidence
is not reinterpreted under new approval rules. Service builders choose the
correct versions; callers constructing snapshots/bundles directly must provide
the appropriate explicit version.

The snapshot hash covers policy identity, policy options, inventory, permissions,
extraction, nominal plan, both reports where required, assumptions, facts, and
explanation. Decisions bind that hash and revision. Changing policy or trial
options creates a new hash and invalidates applicability of earlier decisions.
A required policy fact appears in deterministic and advisory summaries; advisory
text cannot choose the policy or change its outcome.

SQLite stores policy-aware inputs, snapshots, and decisions using the existing
transactional decision recorder. Version manifests identify the actual v1/v2
evidence schema. Revision diffs include policy and option changes. Reopening
completed legacy evidence remains supported; pending runs and new decisions
created with an older implementation require a fresh revision, as specified by
the existing runtime-fingerprint rule. No storage-table migration is needed.
Reviewer identities remain self-reported, and hashes are not signed audit proof.

CLI boot-policy comparison and the Phase 8 benchmark retain their existing
comparison/diagnostic semantics; neither can record an approval. This phase's
policy selection is exposed through the workflow API and Streamlit review UI.

## Verification

```powershell
.\.venv\Scripts\python -m pytest -q tests/test_policy_selection.py tests/test_policy_selection_app.py
.\.venv\Scripts\python -m pytest -q
```

Tests cover policy-specific approvals, preserved baseline violations, legacy
rules, contradictory options, missing or truncated evidence, option/hash changes,
old approvals, explicit rollback permissions, availability regressions, search
limits, durable resumption, manifests, and interactive review transitions. All
model responses are labeled fixtures; no live provider calls are needed.

This remains a simulation with no vehicle integration or certification evidence.
Phase 10 now implements optional single-host shared review and operational
controls; see [Phase 10](phase10.md). No additional numbered phases are planned.
