# Phase 8: measurable quality and reproducibility

This phase addresses a practical engineering question: what does the simulation
verifier detect, how are failures measured, and can someone reproduce the result?
The planner, compatibility semantics, fault model, invariants, and review gate are
unchanged. Phase 8 adds a benchmark and regression evidence around them.

## Run the offline benchmark

From `ota_verifier`, after the normal editable installation:

```powershell
.\.venv\Scripts\python -m ota_verifier.benchmark.runner --mode fixtures --split all --fail-on-findings --output runs/my-reference-report.json
```

The default is explicitly scripted fixtures on the held-out split. The installed
`ota-benchmark` command and `eval/run_benchmark.py` provide the same entry point.
Existing `ota-eval` and `eval/run_eval.py` retain their Phase 4 behavior.
Output files are created exclusively: an existing report is never overwritten.
The command writes full JSON to stdout and, optionally, the chosen output file.

Run only the deterministic campaign benchmark with no model clients:

```powershell
.\.venv\Scripts\python -m ota_verifier.benchmark.runner --mode core --fail-on-findings
```

Exercise deliberately incorrect canned outputs:

```powershell
.\.venv\Scripts\python -m ota_verifier.benchmark.runner --profile false_approval --fail-on-findings
```

The last command returns exit code 4 because it detects extraction errors that
the scripted second pass accepts. The other profiles are `omission`, `reversed`,
and `malformed`; they expose rejected valid inputs, incorrect semantics, or
schema rejection. `--fail-on-findings` returns 4 for failed benchmark expectations,
accepted semantic errors, downstream false acceptances/false infeasibility,
inconclusive decisions, wrong/missing gold citations, or blocked supported cases.
Without that flag, a successfully generated diagnostic report exits 0 even if
checks fail. Invalid arguments use argparse exit code 2.

**Benchmark checks passing does not mean the campaigns are safe.** Correctly
finding an expected violation is a successful benchmark check. Baseline boot
failures remain violations, including when original-version rollback is allowed.

## Frozen corpus and recorded baseline

`src/ota_verifier/data/benchmark_v1.json` contains the reviewed synthetic v1
artifact, with seed 42 and a pinned canonical SHA256. Loading detects unversioned
changes. Hashing canonical parsed content avoids line-ending differences.

* Eleven deterministic cases cover overlapping writes, capacity limits, deadline
  failure, a feasible stable dependency cycle, an infeasible intermediate-version
  cycle, order cycles, mutexes, environmental preconditions, unauthorized rollback,
  explicitly authorized recovery, and a zero-update campaign.
* Six development extraction cases use the original wording generator. Six
  held-out cases use distinct source phrasing and exact regenerated evidence
  offsets. Supported requirements, ambiguity, and unsupported Wi-Fi requirements
  are represented in both splits. Gold formal rules exist before text rendering.
* Evaluation sends only the source-only request to extraction. Hidden gold,
  reference responses, expected outcomes, and planner labels are not in prompts.
  Held-out means separate benchmark wording; it makes no claim about a model's
  training data or broad industry representativeness.

`eval/baseline_v1.json` records the complete-core and both-splits reference fixture
counts and metrics. Tests compare new reports against it. Measured locally:

| Measurement | Reference fixture result |
| --- | --- |
| Core cases matching labels and exhaustive oracle | 11 / 11 |
| Core injected cases / expected injected cases | 252 / 252 (not all independent; see note below) |
| Extraction cases ready / expected blocked | 8 / 4 |
| Per-type semantic precision and recall | 1.0 for each of four types |
| Exact evidence-span accuracy, precision, recall | 1.0 |
| Schema rejection | 0 / 12 extraction responses |
| Ambiguous or unsupported acceptance | 0 / 4 cases |
| Faithfulness false acceptance | Undefined: no reviewed bad drafts in the reference profile |

`core-parallel` and `core-rollback-trap` are the same campaign under two names, so 42 of the 252
cases repeat others. The frozen corpus is kept as it is for regression; research experiments use
the de-duplicated [`campaigns/research_v1.json`](../campaigns/README.md).

These are harness regression results using supplied answers, **not live-model
accuracy measurements**. Negative profiles intentionally show worse outcomes.
The zero-update campaign contributes no injected cases and proves no update
fault tolerance. Explicit rollback permissions remove rollback blockers in the
labeled recovery case but do not erase its invalid-image findings.

To generate a candidate artifact separately:

```powershell
.\.venv\Scripts\python eval/build_corpus.py --output runs/candidate-corpus.json
```

That command refuses overwrite and reports the candidate hash. It does not
replace the frozen corpus or baseline. Changes to wording, labels, scope, or
scoring require deliberate review and, when appropriate, a new artifact/schema
version; do not regenerate labels merely to make a regression pass.

## Oracle and metamorphic checks

The bounded oracle enumerates interval starts and activation permutations
without Z3, production scheduling helpers, or the production plan validator.
It intentionally shares `compat.py`, preserving the single compatibility rule.
Its scope is at most three ECUs, valid initial images, monotonic 1-to-2 updates or
no-ops, one/two-minute write durations, and integral-minute deadlines. Unsupported
inputs raise an error instead of being approximated. Within these bounds, each
fixed ordering yields integer difference constraints and an optimum on the
finite minute lattice.

Additional tests check that inventory/constraint reordering and constraint-ID
renaming preserve feasibility and optimum; relaxing write capacity cannot worsen
optimal duration; relaxing a tight deadline recovers feasibility; and recovery
permissions do not change nominal scheduling. Existing exhaustive recovery,
guarded-recovery, and planner tests remain active. A core-mode test explicitly
forbids all fixture and provider model methods.

## Metric definitions

Semantic matching normalizes versions, ignores constraint IDs and source wording,
and counts duplicate constraints as multiset errors. Counts are accumulated per
case before aggregation, so an omission in one case cannot cancel a hallucination
in another. Ambiguous/unsupported cases are scored for abstention, not recall
against an unjustified unique interpretation.

| Metric | Numerator / denominator |
| --- | --- |
| Per-type precision | Semantically matched constraints / extracted constraints of that type |
| Per-type recall | Semantically matched constraints / gold constraints of that type |
| Evidence-span accuracy | Exact gold semantic-and-span matches / semantically matched constraints |
| Evidence-span precision | Exact gold semantic-and-span matches / extracted constraints |
| Evidence-span recall | Exact gold semantic-and-span matches / gold constraints |
| Schema rejection | Responses failing strict draft JSON/schema validation / received extraction responses |
| Faithfulness false acceptance | Faithful judgments on bad drafts / reviewed bad drafts |
| Unsupported or ambiguous acceptance | Such cases reaching ready / such labeled cases |
| Valid-case blocking | Supported cases blocked / supported cases |

A bad draft has missing/extra/wrong gold semantics or belongs to a required
abstention case. Faithfulness false acceptance measures the second model's
judgment separately from the final gate. Empty denominators produce `null`, not
perfect accuracy. Missing extraction response counts distinguish transport or
boundary failures from malformed JSON. Citation failures are not schema errors.
Exact evidence metrics compare document IDs and character offsets as well as
normalized meaning; correct semantics with a wrong citation fails the benchmark.

Reports retain per-case downstream false acceptance, false infeasibility,
planning unknowns, missed fault violations, and the underlying extraction/call
records. Latency is per attempted model role, including failures. It is wall time,
not an assertion of provider or cross-machine performance. No unmeasured latency
or throughput threshold is enforced.

## Optional live evaluation

Live calls occur only with explicit `--mode live`. Configure the existing
`.env` variables and choose distinct models for extraction and verification if
available; keys remain outside reports:

```powershell
.\.venv\Scripts\python -m ota_verifier.benchmark.runner --mode live --split heldout --output runs/my-live-report.json
```

Only `llm/client.py` creates provider requests. The deterministic benchmark and
scoring code never ask a model to decide compatibility or safety. Scripted
profiles cannot be combined with live mode; fixture-origin call records cannot
be reported as live results. Provider/model declarations must match available
call evidence. Public provider configuration, prompts, raw responses, and attempted
call timings are retained. Model errors are evidence of failed attempts, not
silently repaired outputs. Offline tests exercise this path using mocked
transports; no live provider measurement was performed for this phase.

Reports contain corpus identity, benchmark code fingerprints, runtime/dependency
versions, policy/prompt labels, and a semantic digest. Timings and runtime metadata
are deliberately outside that digest. Actual prompts, raw outputs, plans,
findings, and scores remain inside it. Identical fixture runs on the same
implementation produce the same digest; changed providers or dependencies may
change outcomes and should be compared rather than assumed equivalent. Provider
model versions may drift even when the public model name stays constant.

## CI and verification

The repository-root `.github/workflows/ci.yml` configures Python 3.11, 3.12, 3.13,
and 3.14 on Windows and Linux. Each job installs the project, runs the entire
offline test suite, evaluates the frozen reference corpus, and uploads the report
and full `pip freeze` environment. No API credentials or live jobs are configured.
Dependency ranges remain in `pyproject.toml`; the manifest/environment record
what was measured rather than claiming a cross-platform dependency lock.

```powershell
.\.venv\Scripts\python -m pytest -q tests/test_benchmark.py
.\.venv\Scripts\python -m pytest -q
```

Local verification uses Windows/Python 3.14.4. The CI matrix is configured but
has not been executed from this workspace; other platforms/versions are not yet
claimed as validated. This remains a simulation, with no vehicle integration or
certification evidence.
