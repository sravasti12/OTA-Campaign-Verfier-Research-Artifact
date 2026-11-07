# Phase 2C — Groq activation and connectivity smoke

Date: 6 November 2026. **Latest result: the separately approved explanation-only retry succeeded with HTTP 200 and unchanged evidence/validation. All three LLM stages now have successful live evidence across two workflow attempts. The original smoke's HTTP 429 and two genuine baseline bootability violations remain unchanged.** This is not a fresh complete graph rerun or a passing fault-safety result. Full accuracy evaluation remains unstarted. Earlier attempts remain below as historical evidence.

## Historical configuration — Llama 3.3 attempt

The user-created `.env` was initially in the workspace parent of the application project. It was not tracked, but was not Git-ignored at that location. It was moved into `ota_verifier/.env`, where the existing `.gitignore` protects it. Final checks confirmed ignored and untracked status. Its contents and API key were not displayed or placed in evidence.

Validated settings: provider `groq`, model `llama-3.3-70b-versatile`, API key present. Set the existing `LLM_SCHEMA_MODE` option to `json`: Groq's [model documentation](https://console.groq.com/docs/model/llama-3.3-70b-versatile) lists JSON Object Mode, which the existing adapter supports. This is not a claim that this model supports strict server-side JSON Schema enforcement; strict local response validation remains necessary. Model access for this particular account could not be confirmed by the failed request.

Production code was not changed and no dependencies were installed. Launch the full app from the application project directory so its relative `.env` lookup finds this configuration.

## Historical attempts — Llama 3.3

Both attempts used the existing `LLMClient` with its actual default `http_transport`, without fixture clients, injected responses or mocked transports. The request asked for the small JSON object `{"status":"ok"}`, with a 64-token output limit and 30-second timeout. Credentials were supplied only through the existing client boundary.

| Attempt | Start UTC | Start Asia/Kolkata | Elapsed ms | Actual result |
| --- | --- | --- | ---: | --- |
| Sandbox | 2026-11-06 16:42:26.838756 | 2026-11-06 22:12:26.838756 | 106.283 | Existing client reported connection failure/timeout; no usable model response |
| Approved network escalation | 2026-11-06 16:45:36.280683 | 2026-11-06 22:15:36.280683 | 261.824 | HTTP 403; no usable model response |

These are failed-request latencies, not inference-performance measurements. The HTTPS target was `https://api.groq.com/openai/v1/chat/completions`. HTTP 403 alone does not establish whether the denial came from Groq account/security policy or an intervening gateway. The existing adapter sanitizes the HTTP error and does not retain its response body or request ID, so the precise cause is unresolved. Do not infer an invalid key, exhausted billing, or unsupported model solely from this status.

**Zero successful inference calls.** No further request followed the HTTP 403. The conditional end-to-end smoke test was skipped rather than substituted with fixtures or deterministic fallback results.

## Evidence and next steps

Local sanitized evidence is saved under ignored `runs/`:

- `runs/groq-smoke-20261106T164226Z/connectivity.json`
- `runs/groq-smoke-20261106T164536Z/connectivity.json`
- `runs/groq-smoke-20261106T164536Z/summary.json`, including both results and SHA-256 hashes of their evidence files.

Check the Groq console for project/key permission and account/model availability, and check whether the machine's network/security gateway permits this endpoint. Keep credentials private. After the denial is resolved, authorize one new connectivity request. Only if that succeeds should the small real extraction/faithfulness/explanation workflow run. Corpus admission and the full Phase 2C evaluation remain separate and unstarted.

## Resumed smoke — `openai/gpt-oss-20b`

The user changed the project configuration and authorized one new connectivity request. The original failed attempts above and their evidence files are unchanged.

### Readiness and adapter compatibility

The existing `ClientSettings.from_env()` loaded `LLM_PROVIDER=groq`, `LLM_MODEL=openai/gpt-oss-20b` and `LLM_SCHEMA_MODE=json` from the application working directory. The API key was present but not displayed. Git checks again confirmed `.env` was ignored and untracked. No environment settings were changed during this resumed attempt.

Groq's [GPT-OSS 20B model documentation](https://console.groq.com/docs/model/openai/gpt-oss-20b) lists JSON Object Mode and JSON Schema Mode. The existing adapter uses Chat Completions with `max_completion_tokens`, temperature zero, and either `json_object` or strict `json_schema` according to configuration. The configured JSON Object Mode is a documented format for this model; local strict parsing/validation remains required. No new SDK or model-specific production code was needed to construct this request. The failed HTTP response does not establish account access or successful execution of either output mode.

### Actual single request

| Property | Observed value |
| --- | --- |
| Configured provider/model | Groq / `openai/gpt-oss-20b` |
| Start UTC | 2026-11-06 16:59:37.972188 |
| Start Asia/Kolkata | 2026-11-06 22:29:37.972188 |
| Elapsed request time | 110.184 ms |
| HTTP status | **403** |
| Response content type | `text/plain; charset=UTF-8` |
| Response server header | `cloudflare` |
| Response body | `error code: 1010` |
| HTTP attempts this resumed smoke | **1**; no retries |
| Successful inference calls | **0** |
| End-to-end workflow | Not attempted because connectivity failed |

The request was executed outside the network-restricted sandbox with approval. It used the unmodified existing `LLMClient` and its actual default `http_transport`. A temporary smoke-runner `HTTPErrorProcessor` observed the real HTTP status and allowlisted response headers/error body; it did not replace responses, alter request headers/body, inject a model transport or change production code. The JSON connectivity request allowed up to 256 output tokens and a 30-second timeout. The token bound includes the model's possible reasoning budget; it is not a benchmark claim. No paid plan, subscription or billing change was enabled. Billing/token consumption for the denied request was not observable, and zero charge is not asserted.

The adapter rejected the HTTP error before JSON parsing. Consequently, there was no model JSON to parse or validate, no completed LLM call record, and no evidence of model inference. No extraction, faithfulness or explanation calls followed the failure. Error-body capture was bounded to 4,096 bytes and checked against the locally loaded key before saving; request authorization headers were not recorded.

### Diagnosis and proposed next action — approval required

[Cloudflare's official error 1010 documentation](https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-1xxx-errors/error-1010/) identifies a client/browser-signature denial and notes that default Python `urllib` user agents can trigger such checks. The actual `server: cloudflare` header and 1010 body support that diagnosis for this attempt. They do **not** prove an invalid key, exhausted quota, unavailable model or unsupported JSON schema. No body was captured in the historical Llama attempt, so this diagnosis must not be retroactively treated as proved for that earlier request.

Code inspection shows the existing adapter sets `Content-Type` and authorization, but no explicit application `User-Agent`; urllib supplies its library default. A minimal proposed production change is to identify this API client truthfully, for example:

```python
headers = {
    'Content-Type': 'application/json',
    'User-Agent': 'OTA-Campaign-Verifier/1.0',
}
```

This patch has **not** been applied. It would require an offline header regression check and separate approval for one new connectivity attempt. It is a compatibility hypothesis, not a demonstrated fix, and does not guarantee that the service will allow the request. If a truthful application identifier remains blocked, contact Groq with the saved request time/Cloudflare ray identifier rather than attempting to evade the access restriction. No production changes or additional network tests are authorized by the failed smoke itself.

### New local evidence

The ignored directory `runs/groq-gptoss-smoke-20261106T165938Z/` contains `connectivity.json`, the exact credential-free `connectivity_runner.py`, and `SHA256SUMS.json`. The JSON includes the real HTTP status, configured model, timestamp, latency, allowlisted headers and sanitized error body. Both saved-file hashes were verified after capture. Full Phase 2C evaluation remains unstarted, pending successful smoke tests and explicit approval.

## Approved application User-Agent compatibility test — successful

The user approved the minimal production change and exactly one further live request, conditional on passing offline checks. The previous subsection's proposed change is now historical: the approved implementation uses the actual project version, **0.1.0**, from `pyproject.toml`.

### Changes and offline checks

`src/ota_verifier/llm/client.py` now defines and attaches the fixed header:

```text
User-Agent: OTA-Campaign-Verifier-Evaluation/0.1.0
```

This truthfully identifies the application/evaluation client. No browser identity, rotating identifier, proxy, alternate endpoint or retry was used. The existing Groq request body, JSON mode, authorization construction and response validation were unchanged. The shared header construction also supplies this identity to the other implemented providers.

`tests/test_llm_client.py` checks the header at both the injected transport boundary and the final urllib request, with network I/O mocked. All three providers are covered. Synthetic bearer credentials for Groq/Ollama and the Gemini API-key header remain intact, with no unintended alternate authorization header. Credential-exclusion checks remain in place. Offline records exercising the adapter are mocked test evidence, not live inference.

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.ota_state/groq-ua-tests-v1 tests/test_llm_client.py tests/test_llm_evidence.py tests/test_llm_pipeline.py tests/test_graph.py
```

Actual result before the live request: **97 passed, 0 failures/errors, 13 warnings in 21.95 seconds**. Warnings are the existing LangSmith `asyncio.iscoroutinefunction` deprecation. No planner, compatibility, simulation or workflow production behavior was changed. No dependency installation was needed.

### Single live request and stopping point

| Property | Actual result |
| --- | --- |
| Provider/model | Groq / `openai/gpt-oss-20b` |
| Start UTC | 2026-11-06 17:08:31.558109 |
| Start Asia/Kolkata | 2026-11-06 22:38:31.558109 |
| HTTP status | **200** |
| Elapsed request time | **672.934 ms** |
| Sanitized error code | None; successful response |
| Parsed response | `{"status":"ok"}` |
| Live call record | `origin=live`, `provider=groq` |
| Requests in this approved test | **1**, with no retries |
| End-to-end / full evaluation | **Not attempted** |

The request used the existing `LLMClient` and actual default `http_transport`, with the same response-observation-only smoke harness as the prior attempt. No fixture or mocked response was supplied. HTTP 200 was observed from the HTTPS Groq API target, and the normal Groq envelope parsing completed. Pydantic validated the returned content against the strict local connectivity schema. The configured mode remained `json` (JSON Object Mode); this test does not establish strict server-side schema-mode compatibility or extraction accuracy. The 256-token output limit and 30-second timeout were retained. Latency includes HTTP round trip and local processing; it is a single smoke observation, not a performance benchmark.

The result is consistent with the application-header change resolving the observed compatibility problem in this attempt, but a single before/after request does not establish a universal cause or guarantee. Earlier Cloudflare 1010 evidence is retained without relabeling it as successful inference. No account billing configuration was changed; the response does not establish that the account was charged or uncharged.

The application `.env` remained Git-ignored and untracked, and was not modified during this test. Keys were never displayed or saved in request evidence. Local artifacts under ignored `runs/groq-gptoss-smoke-20261106T170832Z/` are:

- `connectivity.json`: timestamp, status, latency, truthful identity, sanitized response headers, and the actual credential-free call record.
- `connectivity_runner.py`: the exact smoke harness used.
- `verification.json`: offline test outcomes, changed source hashes, Git-protection checks, and explicit scope/call counts.
- `SHA256SUMS.json`: all three artifact hashes, verified after capture.

All API activity stopped after this successful connectivity response, as requested. The next possible stage is a separately approved, small real extraction/verification/explanation smoke test. The reviewed corpus and full Phase 2C evaluation remain unstarted and require subsequent approval.

## Approved live end-to-end smoke — partial success, explanation rate-limited

The user subsequently approved one example with a six-request ceiling, no connectivity repeat, no production changes and a stop on the first failed processing stage. The actual run made **three API requests**, with no retries, then stopped. All LLM clients used `groq`, model `openai/gpt-oss-20b`, the existing truthful application User-Agent, configured JSON Object Mode, a 2,048-token output cap per request and a 45-second timeout.

### Frozen example and expected requirement

This is a small **synthetic, realistic** release-note example, not a document sourced from an actual vehicle or an admitted real-document accuracy corpus:

> brake firmware version 2 or later requires gateway firmware version 2 or later.

The authoritative inventory contains two simulated ECUs, `gateway` and `brake`, each with current version 1, target version 2, a valid active A image and an empty B slot. Gateway/brake write durations are 1.5/1 simulated minutes. Ignition is off, battery 90%, and there are two write channels. The scenario explicitly authorizes each ECU to restore version 1 during recovery; the model neither invents nor grants these authorizations.

The predeclared gold requirement is `brake@>=2 requires gateway@>=2`. The gold file was saved before inference and was not included in model prompts. No real-document accuracy claim follows from this single synthetic case.

### Actual requests and stages

The existing `build_graph` LangGraph workflow was streamed node by node. The extraction node uses the existing `extract_and_verify` pipeline: extraction, strict schema/evidence checks, then a separate faithfulness call. Planning occurs only after that gate. The smoke harness inspected each node result and stopped on a blocked gate, invalid plan or failed live explanation; it supplied no fixture clients and performed no output repairs.

| Stage | Start UTC | Start Asia/Kolkata | HTTP | Request latency ms | Result |
| --- | --- | --- | ---: | ---: | --- |
| Extraction | 2026-11-06 17:41:31.548988 | 2026-11-06 23:11:31.548988 | 200 | 2,112.112 | One strict, source-grounded requires constraint |
| Faithfulness | 2026-11-06 17:41:33.663358 | 2026-11-06 23:11:33.663358 | 200 | 1,365.325 | `faithful=true`, complete document/constraint coverage, no findings |
| Explanation | 2026-11-06 17:41:35.254829 | 2026-11-06 23:11:35.254829 | 429 | 277.791 | `rate_limit_exceeded`, token-per-minute budget exceeded |

These elapsed times cover the existing client call, HTTP round trip and response handling, not isolated model generation time. Deterministic node timings are retained separately in `summary.json`; the entire attempted workflow took 4,021.522 ms including capture overhead.

The actual extracted constraint was:

```json
{
  "id": "c1",
  "source_document_id": "release-notes",
  "source_text": "brake firmware version 2 or later requires gateway firmware version 2 or later.",
  "type": "requires",
  "ecu": "brake",
  "version_spec": ">=2",
  "needs": "gateway",
  "needs_version_spec": ">=2"
}
```

Its evidence span was `release-notes[0:79]`, the complete exact source segment. Strict JSON/schema parsing, known-ECU checks, unique constraint identity, exact source-text/document/offset checks and the saved-evidence revalidation in `verified_campaign` passed. The normalized semantic comparison found one expected requirement matched, zero extra requirements and zero omissions. This is a one-case correctness check, not a dataset accuracy estimate. The live verifier reviewed document `release-notes` and constraint `c1`; its agreement is model evidence, not a proof.

### Deterministic plan and simulator findings

Z3 returned **feasible**, with **90,000 ms simulated makespan**, `optimal=true`, and no findings from a separate complete `validate_plan` replay:

| ECU | Write interval, simulated ms | Target slot | Activation index |
| --- | --- | --- | ---: |
| gateway | 0–90,000 | B | 1 |
| brake | 30,000–90,000 | B | 2 |

Both writes finish at the same modeled timestamp, but serialized activation ranks activate gateway before brake. Active versions move from `(gateway=1, brake=1)` through `(2,1)` to `(2,2)`, satisfying the extracted dependency throughout. Requires constrains active versions, not finish-before-start write order. No LLM chose or checked the schedule.

The existing graph also ran its deterministic baseline stress test. Nominal execution passed. All **28 expected fault cases** were executed: **26 passed and 2 reported violations**, one boot-failure injection per ECU. Those two cases generated four trace findings of `invalid_active_image`. This is an observed simulated safety finding, not a transport/parsing failure or a passing fault-safety result. The graph intentionally sends deterministic findings to explanation; the smoke did not suppress them or change recovery logic. Overall analysis status was `simulation_violations`, and no human approval was granted.

### Exact stopping failure

The explanation request received a real HTTP 429 response whose sanitized provider error had `code=rate_limit_exceeded`, `type=tokens`, and the following reported values:

- Token-per-minute limit: **8,000**.
- Already used: **3,488**.
- Requested: **5,195**.

The provider suggested waiting, but the smoke **did not wait and retry** because the user required stopping at the first failed stage. No billing upgrade was enabled. The reported requested amount is the provider's rate-budget calculation, not a count of generated output tokens or a cost measurement.

The existing `explain_results` function returned its documented deterministic fallback after the HTTP error. The harness explicitly classified this as **failed live explanation**, stopped before `prepare_review`/human review, and did not present the fallback as successful model output. There was no usable explanation response to parse, and no JSON parsing errors were observed in the two successful stages. This attempt therefore does **not** establish a complete live extraction-to-explanation workflow.

### Provenance, regression and saved evidence

Both successful call records have `origin=live`, `provider=groq`. All three stage requests delegated to the existing `LLMClient` with its actual default `http_transport`. The harness only bounded calls, observed real HTTP responses and recorded elapsed times; no network response or LLM transport was mocked for this run. There were **two successful provider responses and one denied request**, not three successful inference calls. No separate connectivity request was made.

Regression command:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.ota_state/groq-e2e-tests-v1 tests/test_llm_client.py tests/test_llm_evidence.py tests/test_llm_pipeline.py tests/test_graph.py tests/test_planner.py tests/test_plan_validation.py tests/test_simulator.py tests/test_invariants.py
```

Actual result: **179 passed, 0 failures/errors, 13 warnings in 6.82 seconds**. The warnings are the existing LangSmith Python deprecation. These offline tests do not add real Groq requests. Production source hashes for planner, compatibility, simulator, graph and LLM client were unchanged during the smoke. `.env` remained ignored/untracked and its contents were not displayed.

The ignored directory `runs/groq-e2e-smoke-20261106T174131Z/` contains frozen input/gold, exact runner, call records with raw model text, per-node outputs, deterministic schedule/fault evidence, the failed explanation snapshot, outcome summary, regression command/log and a SHA-256 manifest. API keys are excluded/redacted; the organization identifier in the provider error body was also redacted after capture. `result.json` explicitly records the unsuccessful overall result. Evidence hashes were checked after final sanitization and regression capture.

**Stop here.** With separate approval, a minimal next test could validate the saved evidence and retry only explanation after quota headroom is available, using a bounded wait rather than enabling paid quota. That would be a separate attempt, not a replacement for this failed one. Full accuracy evaluation still requires corpus review/admission and separate approval. No production rate-limit handling or other production logic was changed by this smoke.

## Approved follow-up — fault analysis and one explanation retry

### Fault root cause and classification

The original evidence hashes were verified before analysis. Both affected cases were replayed using the unchanged existing `simulate_plan`, original campaign, original plan, original fault specification and original simulation options. Their complete replayed results matched the saved results exactly. Neither is unsupported or an input/harness misconfiguration.

The baseline sequence is verify image → select the candidate active slot → boot. In `simulator._inject`, `boot_failure` deliberately marks the **currently active image** invalid before the modeled boot event. `_Run.record` immediately checks invariants. Thus this supported injection produces a **genuine violation of the baseline model's bootable-image invariant**, by construction. Expected injection behavior is not a reason to count the safety assessment as passed. The `valid` flag is a simulated bootability abstraction, not evidence about cryptographic image validation or physical boot hardware.

| Case | Failed active image | Finding trace indices | Authorized recovery actions | Final state |
| --- | --- | --- | --- | --- |
| gateway boot failure, before boot | gateway B/version 2 becomes invalid | 7 (`fault`), 8 (`halt`) | gateway B/2 → A/1 | Both original A/version 1 images active and valid |
| brake boot failure, before boot | brake B/version 2 becomes invalid | 10 (`fault`), 11 (`halt`) | brake B/2 → A/1, then gateway B/2 → A/1 | Both original A/version 1 images active and valid |

All these events occur at simulated 90,000 ms. Each case has two trace findings because the same unsafe active image is observed at both `fault` and `halt`, not because two distinct faults were injected. During the gateway case, halting also cancels the still-unverified brake write; its inactive candidate stays invalid while its original active image stays valid. That is separate from the gateway active-image violation.

For both cases, `check_recovery_path` returned no findings, every recorded trace state remained compatible under the shared `check_compatibility`, and final `check_state`/`original_images_active` checks passed. The original explicit per-ECU/version rollback permissions authorize the version-2-to-1 slot switches. Therefore:

- Invariant 1 (always bootable active image): **violated transiently**, as recorded.
- Invariant 2 (active-version compatibility): no violation in either replay.
- Invariant 3 (downgrade authorization): recovery uses the existing explicit permissions; no unauthorized downgrade finding.
- Invariant 4 (defined compatible recovery path): an available validated path restores the original images in each case.

Recovery success does not erase earlier bootability failures. The original aggregate stays **26/28 fault cases passed, two violation cases, four trace findings**, and overall `simulation_violations`. No passing criteria or production logic changed. This behavior is explicitly covered by existing `test_boot_failure_retains_historical_violation_after_successful_recovery` and the single-fault sweep tests. Guarded trial-boot has separate semantics and tests; this follow-up did not switch policies or assert a guarded-policy result for this campaign.

### Explanation request budget and headroom

The prior error reported **8,000 TPM**, **3,488 used**, **5,195 requested**, and suggested a 5.1225-second wait. Their sum, 8,683, exceeded the then-available minute budget. The original harness did not capture rate-limit headers, so absence in its saved allowlist does not mean the server omitted them. Those reported admission-budget values are not actual successful prompt/completion usage.

The explanation request was reconstructed from the saved validated snapshot. All **38 facts** remained, including every finding and all three mandatory summaries (`extraction`, `plan`, `simulation`). The existing fact selector reorders facts for explanation but removes none here; complete fact identity/content equality was checked. The unchanged schema, system/user prompts, JSON mode, model, temperature, 2,048-token output cap and strict validation were retained. A preflight wire-body hash was matched by the actual outgoing request before delegating to the real transport. The original failed HTTP call did not save a full outgoing request body, so this check validates deterministic reconstruction and this retry's outgoing body rather than claiming a historical byte-for-byte comparison unavailable in the old record.

More than one minute had elapsed before the retry; no extra provider request was used to probe headroom. Organization-wide background usage cannot be determined locally. The actual success establishes sufficient headroom at this attempt. Groq documents [organization-level rate limits and rate-limit response headers](https://console.groq.com/docs/rate-limits); its [model page](https://console.groq.com/docs/model/openai/gpt-oss-20b) lists a 131,072-token context window and 65,536-token maximum output. Those model context/output limits are distinct from this account's much smaller 8,000 TPM budget.

### Actual single explanation retry

| Property | Observed result |
| --- | --- |
| Purpose | Explanation only; no new extraction, verification, planner execution or stress sweep |
| Configured and response model | `openai/gpt-oss-20b` |
| Start UTC | 2026-11-06 17:51:43.746732 |
| Start Asia/Kolkata | 2026-11-06 23:21:43.746732 |
| HTTP status | **200** |
| Whole explanation-call latency | **1,724.646 ms** |
| Provider prompt tokens | **4,871** |
| Provider completion tokens | **423**, including **290 reasoning tokens** |
| Provider total tokens | **5,294** |
| Returned explanation status | `live` |
| Validation findings | None |
| Preserved analysis status | `simulation_violations` |
| New requests / automatic retries | **1 / 0** |

The successful prompt count plus the unchanged maximum completion budget is 6,919 tokens, below 8,000 when sufficient headroom exists. No facts, required evidence or validation requirements had to be weakened. Actual usage values and rate-limit admission estimates need not be identical.

Captured response metadata included:

```text
x-ratelimit-limit-tokens: 8000
x-ratelimit-remaining-tokens: 2874
x-ratelimit-reset-tokens: 38.445s
x-ratelimit-limit-requests: 1000
x-ratelimit-remaining-requests: 999
x-ratelimit-reset-requests: 1m26.4s
```

Groq documents the request headers as daily request counters and token headers as minute counters. These are response-time observations, not a promise of continuing headroom. The existing `http_transport` was called once through an observation-only pass-through wrapper, which retained actual provider model/usage metadata without changing responses. Redirects and automatic retries were prohibited. No fixtures or mocked inference were used.

Strict local explanation parsing and citation/outcome/mandatory-summary checks passed. The three returned statements cite `extraction`, `plan` and `simulation`, respectively; the simulation statement explicitly retains the two violations. This proves neither unrestricted prose faithfulness nor campaign safety. No human decision or approval was created.

### Counts, regression and evidence preservation

For this example there are now **four HTTP attempts across the original smoke and follow-up**: successful extraction, successful faithfulness, original explanation HTTP 429, and successful explanation retry. That is **three successful inference responses and one denied request**. The original smoke is still recorded as unsuccessful; successful stage evidence now exists across two attempts. The earlier connectivity checks are excluded from this example count. Including all recorded connectivity attempts, the Phase 2C history has eight client attempts: seven observed HTTP responses and one sandbox connection failure without a usable HTTP response.

Regression command:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.ota_state/groq-followup-tests-v1 tests/test_simulator.py tests/test_invariants.py tests/test_recovery.py tests/test_exhaustive_recovery.py tests/test_guarded_boot.py tests/test_boot_comparison.py tests/test_explainer.py tests/test_llm_client.py tests/test_llm_evidence.py tests/test_llm_pipeline.py tests/test_graph.py
```

Actual result: **197 passed, 0 failures/errors, 13 warnings in 17.13 seconds**. The warnings are the existing LangSmith Python deprecation. These passing pytest assertions include checking that unsafe baseline boot failures remain reported; they do not turn those fault outcomes into safety passes.

Local ignored evidence is in `runs/groq-followup-v1/`:

- `analysis.json`: exact two-case replays, trace summaries, validated recovery paths, unchanged fact catalog, request fingerprint and source hashes.
- `retry.json`: actual HTTP status, sanitized headers, provider model/usage metadata, live call record, explanation and timings.
- `combined-readonly-snapshot.json`: original deterministic artifacts plus the newly validated explanation. This is an evidence combination, not an executable restored checkpoint or a fresh full graph run.
- `result.json`, exact runner, regression command/log, and `SHA256SUMS.json`.

All **13 original artifact hashes** remained unchanged, and all production Python source hashes recorded in this follow-up remained unchanged. The new evidence package was checked for credentials and hashed after final capture. `.env` stayed ignored and untracked.

The explanation rate-limit blocker is resolved for this one isolated retry. Remaining constraints are the baseline's two genuine bootability violations, organization-wide token budgeting for multi-stage runs, and the unreviewed full evaluation corpus. No rate-limit scheduler, policy correction, provider/model switch or production change was implemented. The combined snapshot remains ineligible for approval because `simulation_violations` persists. Stop after this follow-up; full accuracy evaluation still requires separate approval.
