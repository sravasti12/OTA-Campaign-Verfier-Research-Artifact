# Phase 7: durable local review workspace

This phase addresses an operational problem in the simulation: a browser or
Python restart should not discard campaign evidence, require completed model
calls to be repeated, or lose a recorded review decision.

## Use the UI

Install the updated dependencies and start the existing local app:

```powershell
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m streamlit run app/streamlit_app.py
```

Open **Persistent run library** in the sidebar and select **Open SQLite
workspace**. The default database is `.ota_state/reviews.sqlite`, ignored by Git.
New analyses in that workspace persist across app restarts. Existing memory
runs remain in the original session; opening SQLite does not copy them.

Choose a saved run and **Open saved run** to read its latest evidence. An
interrupted analysis offers **Resume saved analysis**. Opening a completed run,
browsing revisions, exporting evidence, and recording a decision do not invoke
models. Select **Analyze revision** to explicitly create a new revision.

The revision expander shows retained revisions, implementation/runtime metadata,
versioned exports, and literal differences against the current revision.
Selecting historical evidence does not change the current approval target.

## Python API

```python
from pathlib import Path
from ota_verifier.persistence.service import PersistentWorkflowService
from ota_verifier.workflow_examples import example_input, fixture_dependencies
from ota_verifier.workflow_models import WorkflowInput

request, case = example_input("no_updates")
with PersistentWorkflowService(Path(".ota_state/demo.sqlite")) as service:
    bundle = service.start(WorkflowInput(request=request), fixture_dependencies(case))
    run_id = bundle.run_id

# A new process needs no provider credentials to read completed evidence.
with PersistentWorkflowService(Path(".ota_state/demo.sqlite")) as service:
    assert service.get(run_id).snapshot_hash == bundle.snapshot_hash
    envelope = service.export(run_id)
```

`begin(..., pause_after="extract")` creates an intermediate checkpoint;
`resume(run_id)` continues it. `revise` retains old inputs, snapshots, and
review decisions. `get_revision` reads historical evidence. `partial_evidence`
exports committed checkpoint data when a complete snapshot is unavailable.
`compare_revisions` in `persistence.diff` compares documents, inventory,
permissions, extracted constraints, options, plans, findings, outcomes, and
policy-comparison summaries. This is a literal diff, not semantic equivalence.

The zero-update example demonstrates the review workflow, with zero injected
fault cases. It is not evidence of fault tolerance for an update campaign.

## Storage and recovery rules

* SQLite stores the run registry, immutable revisions, public client recipes,
  response receipts, snapshots, decisions, and LangGraph checkpoints in one file.
  `SqliteSaver` supplements the unchanged default `MemorySaver` workflow.
* WAL, full synchronous writes, short SQL transactions, and an OS execution lock
  serialize local mutations across processes. No transaction spans a model call.
  The OS releases the execution lock if its owning process terminates.
* A response receipt commits request intent before a model call and its available
  output before the graph node returns. After a crash, exact completed receipts
  are replayed without contacting the provider. An inflight or uncertain request
  stops resumption; it might have completed remotely. There is no claim of
  exactly-once provider execution. Create a new revision to explicitly retry.
* SQL decisions are authoritative and unique per revision, with idempotency keys
  unique within a run. Current revision, evidence hash, and approval eligibility
  are checked transactionally. If a process dies after decision commit but before
  the graph checkpoint commits, reopening still shows the committed decision.
  Uncommitted SQL writes roll back. Competing decisions cannot both commit.
* New revisions invalidate the current applicability of earlier decisions while
  preserving their original evidence and timestamps. A prior decision never
  authorizes changed documents, permissions, options, or results.
* Version envelopes record schemas, prompt versions, policy labels, relevant
  implementation hashes, Python, SQLite, and dependency versions. Pending
  resumption and new decisions require the same recorded implementation/runtime.
  Supported old completed evidence remains readable; create a new revision after
  an upgrade. Unsupported schemas and corrupt hashes/checkpoints fail explicitly;
  no implicit migration or overwritten evidence is attempted.
* Provider recipes contain an explicit public-settings allowlist. Configured API
  keys remain outside the database and checkpoints. A resumed uncached role reads
  credentials from the current environment through `llm/client.py` and checks
  that public settings match. Fixtures remain explicitly labeled canned data.

## Scope and limits

This remains a simulation. The deterministic planner, compatibility rule, fault
model, invariants, and approval eligibility are unchanged. Policy comparison
cannot override failing baseline evidence or grant downgrade permissions.

The workspace is for trusted, local users. Reviewer identity is self-reported;
there is no authentication, signed audit trail, database tamper resistance, or
multi-host execution guarantee. Hashes detect accidental changes, not malicious
rewriting of both data and hashes. Source documents and responses are retained
in plaintext. Protect the database as local project data. Use SQLite's backup API
or close all database connections before making a filesystem backup; an active
WAL database must not be backed up by copying its main file alone.

An interrupted deterministic node may run again from its prior checkpoint.
Completed model receipts prevent request replay; an unknown provider outcome
requires human-directed revision. Loss of the database itself is not recovered.
The code fingerprint deliberately blocks pending runs after implementation
changes; schema migrations are future explicit work.

## Verification

```powershell
.\.venv\Scripts\python -m pytest -q tests/test_persistence.py tests/test_persistence_app.py
.\.venv\Scripts\python -m pytest -q
```

Tests use fixtures or mocked transports, never live provider requests. They
exercise independent-process restarts, abrupt process termination around model
and SQL effects, simultaneous review attempts, stale revisions, corruption,
version mismatch, credential exclusion, foreign databases, lock release, and
Streamlit reopening/resumption. Existing deterministic and memory-workflow tests
remain part of the full regression suite.


Phase 9 adds optional explicit policy selection with v2 review evidence; the
legacy approval rules described above remain available for v1 revisions. See
[Phase 9](phase9.md) for policy-specific review and schema behavior.
