# Phase 4: document extraction, verification, and evaluation

This phase connects untrusted release notes and ECU documentation to the existing
deterministic simulation. It does not add execution approval, LangGraph, a web
interface, or LLM explanations. The inventory, initial state, targets, durations,
and downgrade permissions remain authoritative structured input.

## Offline demos

All commands below run from the project directory after installing `.[dev]`.
They use scripted fixture responses, require no credentials, and make no network
calls. They demonstrate behavior, not measured model accuracy.

Clear documentation reaches deterministic planning:

```powershell
.\.venv\Scripts\python -m ota_verifier.documents_cli examples/documents/clear-0.case.json --fixture --plan --max-parallel 2
```

Ambiguous documentation blocks planning (exit 6):

```powershell
.\.venv\Scripts\python -m ota_verifier.documents_cli examples/documents/ambiguous-4.case.json --fixture --plan
```

A deliberately omitted dependency is caught by the scripted independent reviewer:

```powershell
.\.venv\Scripts\python -m ota_verifier.documents_cli examples/documents/dependency_only-1.case.json --fixture --profile omission --plan
```

The `reversed` profile similarly demonstrates detecting a reversed dependency.
The `false_approval` profile intentionally models both extraction and review
making the same omission. Local provenance checks cannot determine sentence
meaning; the hidden-ground-truth evaluation detects unsafe accepted plans.

Run reference evaluation, including downstream fault-outcome comparisons:

```powershell
.\.venv\Scripts\python eval/run_eval.py --mode fixtures
```

Expose correlated false approvals and exit 4 if any unsafe acceptance is found:

```powershell
.\.venv\Scripts\python eval/run_eval.py --mode fixtures --profile false_approval --fail-on-false-acceptance
```

`--no-stress` skips fault comparisons but still checks every candidate plan
transition against gold. `--output runs/new-evaluation.json` creates a new report
and refuses to overwrite existing evidence. `runs/` is ignored by git. Reports
contain full cases and run evidence, rather than only aggregate percentages.

The delivered fixture examples are generated using seed 0 and six scenarios.
To generate a fresh directory with other reproducible wording/whitespace:

```powershell
.\.venv\Scripts\python -m ota_verifier.data.generate --output-dir runs/generated-seed42 --seed 42 --count 12
```

Generation chooses formal rules before rendering text. Each `.case.json` holds
hidden gold and canned reference responses; `.request.json` contains only the
authoritative inventory and source documents. Live extraction accepts only the
source-only request schema. Labeled case files are accepted only with `--fixture`.

## Live providers

Install dependencies, copy `.env.example` to `.env`, and configure:

- `LLM_PROVIDER`: `ollama`, `gemini`, or `groq`.
- `LLM_MODEL`: required installed/provider-supported model identifier.
- `LLM_VERIFIER_MODEL`: optional separate model; otherwise the same model gets
  a second independent request and verification prompt. Shared models can share
  errors; a second call is not proof of extraction correctness.
- `GEMINI_API_KEY` or `GROQ_API_KEY` for the corresponding hosted service.
  Local Ollama normally needs only `OLLAMA_BASE_URL`.
- `LLM_SCHEMA_MODE=schema` requests provider schema-constrained output. Explicit
  `json` mode is available for models without that capability; local schema and
  evidence checks remain mandatory in either mode.
- `LLM_TIMEOUT_SECONDS` and `LLM_MAX_TOKENS` bound individual requests.

Configuration is loaded only when explicitly creating a live client. Environment
variables override `.env`; dotenv interpolation is disabled. There is no import-
time credential access, provider fallback, model download, or silent JSON repair.
API keys are excluded from serialized client settings and audit headers are
never recorded. The abstraction uses standard-library HTTP plus `python-dotenv`,
not separate provider SDKs.

```powershell
.\.venv\Scripts\python -m ota_verifier.documents_cli examples/documents/clear-0.request.json --plan --output runs/new-live-run.json
.\.venv\Scripts\python eval/run_eval.py --mode live --seed 42 --count 6 --output runs/new-live-evaluation.json
```

These commands make real configured provider calls. The implementation's test
suite uses fixtures/mocked transports; live model quality, account access, and
service availability have not been measured in this workspace. Provider/model
schema compatibility is checked by the service; an unsupported request blocks
handoff instead of silently changing mode or provider.

Ollama accepts a JSON schema in `format`. [Ollama structured-output documentation](https://ollama.com/blog/structured-outputs)
The Gemini adapter uses the Generate Content REST API's JSON MIME/schema settings.
[Gemini Generate Content structured outputs](https://ai.google.dev/gemini-api/docs/generate-content/structured-output)
Groq schema mode uses `json_schema` with `strict=true`; this capability is limited
to supported models. [Groq structured outputs](https://console.groq.com/docs/structured-outputs)
Provider contracts are covered by mocked request/response tests, not live tests.

## Handoff and evidence

The pipeline in `llm/pipeline.py` performs:

1. An extraction-only LLM call with the known inventory and complete documents.
2. Strict JSON/Pydantic validation, including forbidden extra fields, duplicate
   JSON keys, invalid numeric versions, and nonfinite JSON numbers.
3. Deterministic checks for IDs, known ECU references, exact source ownership,
   full citation segments, and source text/offset agreement.
4. A separate verification-only LLM call examining original documents and the
   draft, checking unsupported claims, reversed relationships, wrong versions,
   ambiguous/unmodeled conditions, and omitted requirements.
5. Deterministic validation of the review schema, exact document/constraint
   coverage claims, finding references, source evidence, and final verdict.
6. A `ready` campaign only if all checks pass. Otherwise the run is `blocked`
   with review findings, and exposes no campaign to automatic planning.

A faithful extraction can contain contradictory constraints. Those reach Z3
and may produce an unsat core; neither LLM decides compatibility or feasibility.
Unclear or unmodeled requirements instead need clarification before a complete
supported campaign can be constructed. Review findings are never automatically
removed and a missing condition is never filled with a guessed default.

Source offsets are half-open Python Unicode character indices into exact
stored text. Code supplies segments and offsets so the model can copy them;
quotes must cover one full supplied segment. Segmentation splits at newlines
or punctuation followed by whitespace and preserves numeric versions such as
4.2. It is a deterministic citation convention, not a linguistic sentence parser;
abbreviations may split. PDF/OCR ingestion, cross-segment evidence for one rule,
retrieval/chunking, and freeform ECU inventory extraction are not implemented.
The explicit 100000-character input bound rejects oversized text without
truncation. Chosen model context/output limits may impose smaller bounds.

Run records preserve exact source documents, text hashes, inventory/environment/
authorizations input hash, prompt versions, provider/model identity, prompts,
requested schema, credential-free request JSON/hash, raw response text, finish
reason, parsed draft, review verdict, and gate findings. Transport failures
without usable response text record a sanitized blocker rather than an invented
verdict. Malformed/truncated responses preserve available response evidence.

`verified_campaign(run)` rechecks hashes, recorded request prompts, raw/parsed
response agreement, source evidence, review coverage, and authoritative inventory
before planning a saved run. Hashes detect accidental changes; they do not
provide authentication or prevent deliberate forgery. `ready` means the
extraction gate passed, not that the campaign is fault-tolerant, approved by a
human, or authorized to execute.

CLI exit codes: 0 ready; 1 input/configuration/output error; 6 blocked extraction.
With `--plan`, 2 means planner infeasibility and 3 means solver unknown. Planning
and simulation APIs themselves make no LLM calls.

## Evaluation definitions

The six scenario families cover clear multi-document constraints, a dependency-
only campaign, conflicting order, impossible intermediate activations, ambiguous
wording, and an unsupported Wi-Fi precondition. Context noise and whitespace vary
reproducibly. This is a small synthetic benchmark with limited language diversity,
not a dataset of real campaign documents or a claim of field performance.

- **Semantic precision/recall** compare constraint multisets after numeric
  version normalization, ignoring generated IDs and source wording. Mutex member
  order is ignored. This is exact normalized matching, not general logical
  equivalence. Duplicate extractions count as false positives.
- **Correct abstention** is evaluated for ambiguous/unsupported documents.
  Their semantic metrics are null and excluded from micro precision/recall:
  hidden intent or an unmodeled condition is not uniquely recoverable from text.
- **Accepted semantic error** means a ready extraction has missing/extra/wrong
  formal constraints, regardless of whether that particular plan happens to work.
- **False acceptance** means a ready extraction ignored a gold review blocker,
  produced a feasible schedule violating gold at any transition, or missed a
  fault-case invariant violation that gold checking finds. The reported rate's
  denominator is the number of ready extraction handoffs, with raw counts shown.
- **False infeasibility** means extracted constraints block planning although
  gold constraints admit a plan. It is separate from unsafe plan acceptance.
- **Inconclusive decisions** retain solver/recovery uncertainty separately;
  unknown results are not counted as proof of validity or infeasibility.
- **Fault-outcome differences** compare candidate and gold per-fault verdicts,
  recovery availability, and invariant findings only when the nominal schedule
  is valid under gold. Invalid nominal plans are flagged before fault simulation.

For gold validation, only step constraint-reference metadata is rebound to gold
IDs. Schedule times, ordering, selected slots, versions, projected states, resource
limits, and deadlines stay untouched. This avoids falsely scoring different
constraint IDs as safety failures or correcting an unsafe extracted schedule.

Fixture-mode reference results have four ready and two blocked cases with zero
unsafe acceptances. Omission/reversal profiles demonstrate blocking erroneous
extractions. False-approval fixtures deliberately expose three unsafe handoffs.
These figures describe the canned harness inputs; **they are not LLM accuracy
measurements**. Live evaluation is opt-in and uses the same deterministic metrics.
