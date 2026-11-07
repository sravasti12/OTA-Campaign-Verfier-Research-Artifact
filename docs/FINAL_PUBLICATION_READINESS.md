# Final publication readiness

## Public-reference separation assessment - 7 November 2026

**Decision: READY WITH LIMITATIONS for public GitHub publication.** The previous distribution/test blocker is addressed by explicitly optional external-reference verification, not by redistributing manufacturer assets or weakening first-party tests. The assessment below supersedes the archived blocked snapshots.

### Changes and dependency boundary

The normal suite keeps all five corpus cases and all original schema, source-span, expected-gate, exclusion-parser and actual Z3 assertions. No test is skipped. Only the absence of four exact external asset paths is allowed:

- `eval/live_extraction/real-review-v2/sources/flysky-nb4-manual.pdf`
- `eval/live_extraction/real-review-v3/sources/flysky-nb4-manual.pdf`
- `eval/live_extraction/real-review-v3/rendered-pages/flysky-page-7.png`
- `eval/live_extraction/real-review-v3/rendered-pages/flysky-page-67.png`

`tests/test_real_review_v2.py` and `validate_real_v3.py` previously required direct reads of the PDF; the latter also required nonempty rendered pages. They now report `UNAVAILABLE_EXTERNAL_REFERENCE` for absent optional files. Present files must match their original hashes, including page images (a stronger check than the former nonempty check). Tests emit explicit warnings when external provenance cannot be checked; embedded citation/schema checks still execute. These are not claims to have independently verified a missing PDF or its transcription.

New `eval/live_extraction/verify_reference_assets.py` verifies every SHA256SUMS-indexed published artifact and separately lists missing external references. Non-optional missing files and all wrong present bytes fail. `--require-external` demands all four references too. The v3 validator CLI is now read-only instead of overwriting immutable `validation.json`. Packet-construction scripts and historical snapshots retain their original dependencies and must not be used to regenerate evidence.

New regression coverage tests absent, correct and corrupt bytes for every optional path, missing first-party evidence and manifest path escape. No OTA planning, LLM behavior, prompts, simulator behavior or historical dataset/results were modified.

### Exact verification results

**Clean public-checkout full suite: 717 passed, 0 failed, 0 errors, 0 skipped, 15 warnings in 213.81s.** The four restricted assets were absent throughout. Warnings: 13 dependency deprecations and two explicit external-reference-unavailability warnings, one for each corpus test boundary. The original 703 tests remain active; 14 new reference-boundary regressions account for the total increase.

- Local targeted tests: **22 passed, 0 failed/errors/skipped, 13 dependency warnings**, 0.61s.
- Additional MCUboot/scalability suites: **102 passed, 0 failed/errors/skipped, 13 dependency warnings**, 60.12s.
- `pip check`: **No broken requirements found.**
- Public-checkout evidence audit: **20 manifests, 7,963 entries verified**, exactly four external references unavailable; exit 0, `complete_reference_package_verified=false`.
- Strict audit in that same public checkout: **exit 2**, exactly four unavailable external references; this is the expected incomplete-reference result, not a full-reference pass.
- Strict local audit with independently retained original assets: **20 manifests, 7,967 entries verified, zero unavailable**, exit 0. No asset was copied into the public checkout.
- Existing MCUboot package verification from the public checkout: **58 fresh-package and 50 replay-package artifact hashes passed**. These verify historical native logs; no fresh MCUboot C execution is claimed.
- Engineering evidence exporter verification passed from the public checkout.
- Temporary index and exported checkout: **7,983 unique SHA256SUMS-indexed files including their manifests** matched exact original bytes; **67 production-source fingerprints** matched. This check has a narrower enumeration than the earlier 8,008-file audit; it does not supersede or reinterpret that historical count.
- Static documentation checks: README plus main guides, **39 Markdown documents**, no broken local links/images, unbalanced fences or table-column issues. No browser-rendering or hosted-service claim.

### Temporary publication check

A separate temporary Git repository/index selected **9,384 candidate paths**, with autocrlf enabled, then exported a new checkout outside the project directory. All four restricted paths and `.env` were confirmed absent. The real Git index remained unchanged; no commit or branch was created. The suite used the existing project virtualenv, the exported first-party source tree and a subprocess environment with LLM/Groq/Gemini/Ollama variables removed. The dependency environment is shared, not a newly installed venv or remote clone. Windows was exercised; Linux was not newly verified.

Diagnostics remain under ignored `.ota_state/public-reference-v1/`: checkout.json, pytest.log, public-evidence.json, byte-integrity.json and docs.json. The original 8,555-file inventory and third-party notices remain in place. README/report wording updates after the test snapshot do not change the exercised code or frozen evidence.

### Reproduction and third-party handling

From the project root in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe eval/live_extraction/verify_reference_assets.py
.\.venv\Scripts\python.exe eval/live_extraction/verify_reference_assets.py --require-external
.\.venv\Scripts\python.exe eval/live_extraction/validate_real_v3.py
.\.venv\Scripts\python.exe -m pip check
```

The first, second and fourth commands work offline without the four external files. The strict third command verifies the original external package when legally obtained and exits 2 if unavailable; any corrupted present artifact exits 1. The validator does not alter its archived packet. See [the reference guide](THIRD_PARTY_PUBLICATION.md) for the official Flysky revision 20231219 URL, all expected hashes, manual retrieval and Windows rendering limitations. Nothing is automatically downloaded. Historical page raster bytes may require the unchanged private archive; a different rendering must not be substituted and resealed as original evidence.

The four ignored manufacturer assets remain intact locally. Published source quotations/labels and original manifests remain unchanged, with attribution. This technical decision is not a legal license grant. ExpressLRS GPL notices and MCUboot Apache notices remain included. The full original reference package is optional external evidence, not part of the public repository's claim of verified bytes.

### Files changed in this task

- New `eval/live_extraction/verify_reference_assets.py` and `tests/test_optional_reference_assets.py`.
- Updated `eval/live_extraction/validate_real_v3.py`, `tests/test_real_review_v2.py`, `tests/test_real_review_v3.py`.
- Updated `README.md`, `docs/THIRD_PARTY_PUBLICATION.md`, this report.

No additional ignore exceptions, frozen-label changes, production OTA changes, credential handling changes or evidence regeneration were needed. All prior modified files remain visible for the owner's Git review.

### Remaining limitations

Missing external references cannot be independently authenticated by the public checkout; warnings and machine-readable absence remain explicit. Owner review of historical machine-path metadata and distribution attribution remains advised. Neither the hashes nor this report establish source truth, domain-expert approval or legal clearance.

Engineering findings are unchanged: final live workflow correctness 4/5 with a Flysky false rejection; only two positive embedded-document rules; two feasible zero-step Z3 handoffs; two genuine bootability violations; bounded MCUboot agreement with two policy mismatches and four unsupported scenarios; unresolved scalability outcomes; incomplete normative/organizational review and remote CI/OIDC verification. No vehicle/hardware safety, regulatory compliance or production readiness is claimed.

No Groq request, third-party download, commit, push or deployment occurred. No new phase was started.

---

## Archived blocker-resolution assessment

The following snapshots describe earlier checks and blockers. The public-reference separation assessment above supersedes their current-status wording without altering historical results.

# Final publication readiness

## Current resolution assessment - 7 November 2026

**Status: BLOCKED for a self-contained GitHub publication. Both original technical blockers are resolved.** Offline profile tests no longer depend on private provider settings, and temporary Git staging/checkout preserves included immutable evidence and production fingerprints. A separate third-party distribution/reproducibility blocker remains: four manufacturer PDF/page-image assets have no established redistribution grant. They are retained locally and narrowly excluded from publication; a bare proposed public checkout fails the existing corpus integrity test without them. No historical manifest was altered to conceal that gap.

### Test results from the resolution run

| Command / environment | Passed | Failed | Errors | Skipped | Warnings | Observation |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Full pytest, first sandbox attempt | 604 | 0 | 99 | 0 | 13 | 92.95s; test_temp ACL setup failures |
| Exact full command, authorized outside-sandbox retry | 703 | 0 | 0 | 0 | 14 | 273.21s; all passed |
| Additional MCUboot/scalability suites | 102 | 0 | 0 | 0 | 13 | 36.08s; all passed |
| Sanitized pre-fix configuration probe | 0 | 1 | 0 | 0 | 13 | Missing model configuration reproduced |
| Both affected modules, sanitized after fix | 13 | 0 | 0 | 0 | 13 | 1.15s; no provider environment or .env |
| Both affected modules, normal environment | 13 | 0 | 0 | 0 | 13 | 0.91s; assertions unchanged |
| Bare proposed public-checkout corpus probe | 0 | 1 | 0 | 0 | 13 | Missing excluded Flysky PDF; not a successful full-public-checkout test |
| Sanitized exported checkout, four original assets restored privately | 703 | 0 | 0 | 0 | 13 | 209.09s; full suite passes without provider configuration |

The sanitized exported-checkout run used no local `.env` or provider variables and disabled only pytest cache writing (`-p no:cacheprovider`), not tests. It restored the exact four privately retained assets into the exported working tree, outside the temporary index. It is not a bare-public-checkout success. The exported directory came from `checkout-index` without creating a commit; this is not a remote clone or Linux verification.

The full-suite and additional suites total **805 passing tests**; the 13 profile tests are overlapping checks, not extra unique tests. `pip check`: **No broken requirements found.** Warnings comprise 13 upstream LangSmith deprecations and one full-run pytest cache WinError183 warning. The 99 sandbox setup errors were environmental, not assertion failures; the exact command passed outside the sandbox. No production correction was made to obtain that result.

### Offline isolation correction

The reproduced failure was `tests/test_final_reliability_repair.py::test_budget_is_bounded_and_new_evaluation_remains_unapproved`: `LLMError` because no model was configured. Both that module and `tests/test_final_retest_runner.py` construct the Groq evaluation profile in otherwise-offline tests.

New opt-in `tests/conftest.py::offline_groq_settings` supplies explicit dummy settings and prohibits real client HTTP. The two modules opt in with `pytest.mark.usefixtures`; no assertion was removed, weakened or skipped. Environment-loader tests retain their real behavior because the fixture is not autouse. The sanitized run used a fresh directory without `.env` and removed LLM_/GROQ_/GEMINI_/OLLAMA_ variables. Production extraction, verification, planner, prompts and simulator remain unchanged by this repair.

### Git byte preservation and evidence integrity

Scoped root `.gitattributes` rules preserve `eval/live_extraction/*-v[0-9]*/**`, `examples/engineering_evidence_v1/**` and `src/ota_verifier/**` with `-text`. The source package is included because the live evidence binds its exact bytes: evidence-only rules initially left 35 source fingerprints altered by autocrlf. Existing results/raw, scalability and MCUboot evidence rules remain. Global newline normalization was not disabled; historical files were not normalized or resealed.

A separate temporary Git repository/index simulated staging with `core.autocrlf=true` and exported a checkout using `checkout-index`. There was no commit, real-index staging or branch change. The original real index was checked unchanged.

- Proposed snapshot: 9,382 paths, selected explicitly from Git's tracked/untracked candidate list, excluding the four restricted assets. This snapshot predates the final report/README wording edits.
- **8,008 unique included hash-verified files** matched in both temporary staged blobs and exported checkout; zero staged/checkout mismatches.
- All **67 production-source fingerprints** matched after adding the scoped source-package rule.
- Local recursive SHA256SUMS audit: **7,967 entries across 20 manifests, zero failures**. Counts include repeated/nested entries and differ from the unique staged-file count.
- Existing MCUboot verifier: **58 fresh-package artifacts and 50 replay-package artifacts verified**. This verifies historical C evidence; no fresh native execution was claimed.
- Existing scalability `report.verify` executed against every scalability SHA256SUMS directory; engineering exporter `--verify` passed.
- The four excluded assets still match their original hashes locally. Their absence from the public snapshot is explicitly a missing-reference gap, not a hash-verification success.

Detailed local diagnostics are retained under ignored `.ota_state/publication-fix-v1/`: integrity.json, staged-checkout.json, sanitized logs, bare-checkout failure and exported-checkout log. No frozen dataset, prediction or historical result changed.

### Publication inventory and third-party decisions

[PUBLICATION_FILE_INVENTORY.csv](PUBLICATION_FILE_INVENTORY.csv) classifies every file in the original **8,555-file untracked cohort**:

| Category | Files | Proposed disposition |
| --- | ---: | --- |
| Source code and tests | 50 | Retain |
| Essential evaluation evidence | 8,459 | Retain |
| Documentation and examples | 28 | Retain |
| Third-party snapshots | 18 | Retain 14 with notices; exclude four restricted manufacturer assets |
| Generated caches / virtual environments | 0 | Already ignored, outside this cohort |
| Temporary / sensitive | 0 | Already ignored, outside this cohort |

This is an inventory, not authorization to stage all files. New resolution files are listed below; the current Git count differs from the original cohort. No `git add .`, deletion or actual staging was performed.

[Third-party publication decisions and retrieval instructions](THIRD_PARTY_PUBLICATION.md) record pinned provenance. MCUboot snapshots retain Apache-2.0 LICENSE/NOTICE. The actual pinned ExpressLRS Docs LICENSE and website licensing statement establish GPL-3.0 coverage; copies and attribution are now supplied. Whole tool installations, downloaded upstream trees, virtualenvs, caches, secrets and local SQLite state remain excluded. The Flysky complete PDF and two derived page images have no established distribution basis: four exact-path ignore entries retain them privately. Public availability alone was not treated as permission to bundle them. Limited attributed quotations remain an owner distribution-review item.

The bare checkout's existing source-integrity test fails with FileNotFoundError for `sources/flysky-nb4-manual.pdf`. Local retrieval instructions preserve exact expected hashes and explain that rendering anew may not reproduce historical raster bytes. A separately approved public derivative or appropriate permission/access solution is needed; no fixture or missing-file skip replaces actual source evidence.

### Security and documentation

The earlier complete current-file/reachable-history secret scan below remains the baseline. This resolution adds no API call, credential or real provider configuration. `.env`, actual Streamlit secrets, `.venv` and `.ota_state` remain Git-ignored and untracked. Dummy fixture values are deliberately non-credentials. Historical hashed evidence still contains local machine paths/user metadata; it has not been silently redacted. Owner disclosure review remains required.

README's obsolete private-provider test qualification is corrected and links the reference-asset prerequisites. Its 14 phases, final five-case measurements, persistent Flysky false rejection, two bootability violations, MCUboot mismatches/unsupported cases and standards-concept limitations remain intact. Final static check: **39 main Markdown documents, zero broken local links/images, zero unbalanced fences and zero table-column issues**. Existing GitHub Actions workflow review remains recorded in the archived audit. Final candidate scan: **9,382 paths, zero configured-secret/token/private-key candidates**; final Git status: **12 modified tracked files and 8,556 untracked files**. Root Git index remains unstaged by this task. These counts include pre-existing work. Static checks do not establish visual rendering. Further workflow review results are recorded below; no claim of browser rendering, remote CI, live OIDC or current hosted-demo validation is made.

### Files changed by this resolution

- `.gitattributes`, `.gitignore`: scoped byte preservation and four exact restricted-asset exclusions.
- `tests/conftest.py`, `tests/test_final_reliability_repair.py`, `tests/test_final_retest_runner.py`: opt-in dummy settings and HTTP prohibition.
- `README.md`, this report: test prerequisites and current status.
- `docs/PUBLICATION_FILE_INVENTORY.csv`, `docs/THIRD_PARTY_PUBLICATION.md`: full original-cohort selection/provenance.
- `docs/third_party/EXPRESSLRS_DOCS_GPL-3.0.txt`, `docs/third_party/EXPRESSLRS_DOCS_LICENSING.md`: upstream notices.

Other modified production and evaluation files visible in Git status predate this resolution; they were not reverted or changed to force passing tests.

### Remaining decision and engineering limits

**Original test-isolation blocker: RESOLVED. Original newline-conversion blocker: RESOLVED for included artifacts. Final self-contained publication: BLOCKED** until third-party asset distribution/access and complete-reference checkout verification are resolved. Do not publish restricted files merely to make integrity tests pass. The proposed selection and unchanged private full evidence package are different artifacts.

Retained engineering limitations: 4/5 live workflow outcomes; two positive embedded-document rules do not establish automotive accuracy; two zero-step Z3 handoffs; unresolved large-scale solver outcomes; unreliable historical parent memory monitoring; 26/28 fault cases with two genuine bootability violations; bounded simulated-flash MCUboot comparison; no vehicle validation, production-safety or regulatory-compliance claim.

No live Groq request, installation, commit, push, release or deployment occurred. No new development phase was started.

---

## Archived initial publication audit (before the authorized repairs)

The following is the earlier audit snapshot. Its unresolved-original-blocker statements and counts describe that earlier assessment; the current assessment above supersedes them.

# Final publication readiness

Assessment: 7 November 2026 (Asia/Calcutta), Windows11, Python3.14.4, existing project virtual environment.

**Overall status: BLOCKED for GitHub publication.** The configured local full suite and additional regressions pass, dependency and current evidence checks pass, and no exposed credential was detected. Two reproducibility blockers remain: an offline evaluation test requires private/local provider configuration, and Git newline filtering changes bytes in frozen corpus evidence. These were diagnosed without changing production code, prompts, tests or historical artifacts.

## 1. Exact test and environment results

| Check | Passed | Failed assertions | Errors | Skipped | Warnings | Result |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Requested full command, first sandbox run | 604 | 0 | 99 | 0 | 13 | Fixture setup denied access to test_temp; 162.43s |
| Exact same full command, authorized outside-sandbox retry | **703** | **0** | **0** | **0** | **14** | **All full-suite tests passed**, 208.17s |
| Additional MCUboot/scalability regressions | **102** | **0** | **0** | **0** | **13** | Passed, 46.85s |
| Controlled no-.env reproducibility probe | 0 | **1** | 0 | 0 | 13 | Failed; confirms CI/configuration blocker |

Exact requested command, used in both full runs:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Additional regression command:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.ota_state/publication-extra-tests validation/mcuboot/test_differential.py validation/mcuboot/test_refinement.py validation/mcuboot/test_validate.py eval/scalability/test_scalability.py
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe run_all.py --smoke --require-tlc
```

The703 default tests and102 explicitly collected additional tests are separate, disjoint suites:805 passing cases across those two successful commands. The research smoke command also passed five stages: research-corpus, benchmark-core, its selected pytest subset, TLC positive model, and expected seeded TLC violation. Its overlapping tests are not added again to805. Existing checksum-pinned TLC and Java were available; no dependency/tool installation was performed.

Warnings:13 recurring LangSmith dependency deprecations for asyncio.iscoroutinefunction. The outside-sandbox full run also emitted one PytestCacheWarning: unable to create an existing cache path under .pytest_cache ([WinError183]). This did not fail tests. The first99 errors were [WinError5] while pytest attempted to clear its project-local test_temp base; direct sandbox directory/ACL access was denied. The exact rerun passed without a code/configuration change. No failed test was deleted or bypassed. pip check returned **No broken requirements found.**

### Reproduced clean-environment failure

A child pytest process was launched from a fresh empty working directory with LLM_*, GROQ_*, OLLAMA_* and GEMINI_* variables removed, so it could not read the project .env. The existing test `tests/test_final_reliability_repair.py::test_budget_is_bounded_and_new_evaluation_remains_unapproved` failed with **LLMError: Set LLM_MODEL to an installed or provider-supported model**. The path is continuation_plan.budget -> ClientSettings.from_env. This is an actual hidden configuration dependency, not a provider request or a failure of the deterministic planner.

Local success therefore does not establish clean-checkout CI success. Related final-runner/profile tests also inspect local settings. A test-scoped, explicitly mocked/dummy settings fixture should make offline tests independent of private credentials; that repair was not authorized here. Do not put a real Groq key into CI merely to satisfy offline tests. No Groq requests were made during this verification.

## 2. Security audit

Git tracking and ignore checks, not filenames alone, were used:

```powershell
git ls-files -- .env .env.example .streamlit/secrets.toml
git check-ignore -- .env .venv test_temp
git ls-files -ci --exclude-standard
git log --all --format= --name-only -- .env .streamlit/secrets.toml
```

Findings:

- `.env` and `.streamlit/secrets.toml` are untracked; .env, the virtual environment and temporary/cache directories are ignored. No tracked-ignored files were found. Neither private secret-file path appears in local reachable commit history.
- `.env.example` is tracked and its API-key fields are empty. The tracked Streamlit secrets example contains explicit replacement placeholders only. A generic assignment scanner flagged that example's client-secret placeholder; manual review confirmed it is not a credential.
- Initial scan:826 tracked files and9,380 tracked-plus-untracked publication candidates. No match for configured private secret values, recognizable Groq/GitHub/Google/AWS credential patterns, or private-key PEM headers was found. Generic current-file credential-assignment candidates were also reviewed without printing their values.
- All13 local reachable commits /1,089 reachable Git blobs were checked for configured secret values and recognizable token/private-key patterns:zero candidates. Remote-only refs, unreachable/deleted objects and unknown secret formats are outside that scan; this is not an absolute guarantee against every possible secret.
- No publishable SQLite database, real secrets file, key store or private-key file was identified among Git candidates. Current logs/reports/evaluation artifacts were included in the credential scan. Secrets themselves were never printed.
- The initial path/contact scan flagged477 files, mainly archived source snapshots, logs and environment records. Upstream contact addresses and local machine paths are not automatically credentials. One hardcoded owner-specific WSL path in the public MCUboot guide was replaced with an explicit generic path placeholder. Hashed historical logs still contain local path/user metadata; they were not redacted in place. Owner review/consent or a separately versioned public derivative is needed before distributing that metadata. Do not claim that the complete evidence archive is personal-information-free.

The existing ignore rules are appropriate for .env variants (with .env.example excepted), Streamlit secrets, .venv, test_temp, .ota_state, runs, model-checker binaries, the upstream MCUboot checkout, and throwaway research smoke output. No new blanket ignore rule was added: it would risk hiding required evaluation evidence.

## 3. Evidence integrity

| Evidence scope | Actual verification |
| --- | --- |
| MCUboot Phase12E fresh package | Existing validate.py --verify command:58 artifacts passed |
| MCUboot Phase12E replay package | Existing validate.py --verify command:50 artifacts passed |
| Z3 scalability directories | Existing scalability.report.verify:7,768 entries passed across nine directories |
| Scalability study index |13 additional top-level entries passed |
| Synthetic pilot | Original execution12 and recovery20 entries passed; original12-entry index also checked |
| Original real-document pilot | Original execution14 and final20 entries passed; original14-entry index also checked |
| Final real-document retest | Original execution17 and final23 entries passed; original17-entry index also checked |
| Review/repair packages | Readiness4, real-review-v2 13, real-review-v3 16, review-materials8, reliability-repair4 entries passed |
| Engineering evidence sample | Existing exporter --verify succeeded;3 file-manifest entries passed |

Other than scalability, the recursive manifest audit checked305 entries in17 manifests, including the108 MCUboot entries above. Nested/repeated indices are separate checks, not305 unique artifacts. No hash mismatch, missing indexed file or escaping manifest path was found. Historical failed cases, the original HTTP400, persistent false rejection, MCUboot mismatches and unsupported scenarios remain intact.

Existing verification commands:

```powershell
.\.venv\Scripts\python.exe validation/mcuboot/validate.py --verify validation/mcuboot/final_evidence/phase1e-fresh/validation.json
.\.venv\Scripts\python.exe validation/mcuboot/validate.py --verify validation/mcuboot/final_evidence/phase1e-replay/validation.json
.\.venv\Scripts\python.exe -m ota_verifier.engineering_evidence --verify examples/engineering_evidence_v1
```

No fresh native MCUboot C execution or expensive scalability matrix was repeated. Existing native evidence was hash-verified and additional Python differential/refinement/runner regressions executed. Native logs are historical observations, not fresh hardware or vehicle validation. All production-source hashes still match the final live-retest freeze.

### Byte-preservation publication blocker

Git core.autocrlf is true. `git check-attr text eol` reports unspecified text handling for the new live-extraction corpus/evaluation paths. A read-only comparison of `git hash-object --no-filters` against Git's normal clean-filter result proves different bytes for both:

- `eval/live_extraction/real-review-v3/sources/mcuboot-design.md`
- `eval/live_extraction/real-retest-v2/dataset.json`

Therefore successful workspace SHA256 checks do not guarantee that staging/checkout preserves the evidence. Existing attributes protect results/raw, scalability evidence and MCUboot execution evidence, but not all newer byte-hashed packages. Before staging, review byte-preserving attributes for `eval/live_extraction/**` and `examples/engineering_evidence_v1/**`, then verify hashes in a clean checkout. Do not normalize files or regenerate frozen hashes to conceal the problem. Changing .gitattributes/tests is beyond this task's permitted documentation/Git-ignore corrections, so those fixes remain explicit blockers rather than unreviewed changes.

## 4. README, documentation and workflow checks

All14 numbered phases are present in README. Phase13 includes the final five-case retest, eight HTTP200 requests,18,022 tokens,100% semantic/grounding precision and recall on two positive rules,4/5 complete outcomes, persistent Flysky false rejection, and two feasible zero-step plans. Historical760-test broad and274-test targeted records remain identified as historical, not overwritten with the smaller audit suite counts.

Phase12 retains6 MATCH /2 policy MISMATCH /4 UNSUPPORTED /0 INCONCLUSIVE. Phase14 clearly presents engineering-concept mapping rather than regulatory compliance, with normative/organizational review incomplete. The two genuine bootability violations remain visible. Simulation, native-reference observations and real-vehicle assurance are distinguished.

Static checks covered README plus36 existing Markdown guides:37 documents, no unresolved local links/images, balanced fenced code blocks and consistent table columns. README itself has56 local file links and9 heading links. The new readiness report was checked separately after creation. GitHub Mermaid/browser rendering and external URL uptime were not exercised; these are static checks, not visual or hosted-deployment validation.

Two minimal documentation corrections were made:

1. README's Phase4 test-configuration claim now matches its setup qualification; it no longer promises that every newer evaluation-profile test is independent of local provider configuration.
2. The MCUboot public guide's owner-specific WSL directory became an explicit generic placeholder. Historical evidence bytes were untouched.

Older consolidated/readiness/research documents remain dated snapshots; README identifies the final retest comparison as the later LLM evaluation record. They were not rewritten to falsify historical status.

`.github/workflows/ci.yml` parsed successfully. It defines eight Windows/Linux × Python3.11-3.14 jobs, contents:read permissions, dependency installation, checksum-pinned TLC setup, smoke/regression/benchmark/release checks and artifact upload. No real credential or live API invocation was found. **The verified clean-environment configuration dependency is an actual blocker to assuming this workflow will pass**, because the job supplies no local LLM settings. Remote Actions execution, fresh dependency resolution on every matrix version and real OIDC remain unverified. Local Python3.14 success is not Python3.11 verification.

## 5. Git status and publication hygiene

At inspection start:9 modified tracked files,8,554 untracked files,826 tracked files and9,380 total candidate files (~61.3MB). Most untracked files are recorded scalability inputs/results and live-evaluation artifacts. No candidate exceeded10MiB. Largest artifacts:two copies of the Flysky manual at7,858,745 bytes each, the demo recording at5,057,029 bytes, and primary scalability trials at3,014,419 bytes. Duplicate PDFs are intentional versioned source snapshots; no evidence was deleted to reduce size.

Modified tracked files before this audit were Makefile, README.md, run_all.py, src/ota_verifier/formal/tlc_trace.py, four existing LLM modules (client/extractor/pipeline/verifier), and tests/test_llm_client.py. This audit additionally modifies the public MCUboot guide and adds this report. The final status count is recorded below. These pre-existing changes were not staged, reverted or treated as new work performed by this audit.

Retain and review for publication: the new source/test modules, phase reports, frozen synthetic/real pilot and retest evidence, approvals, exact source excerpts, benchmark results/manifests, engineering-export sample and relevant licenses/notices. Many README-linked reports and test dependencies are currently untracked; a partial manual staging selection can produce a broken checkout even though the working tree passes. Review the complete Git status before choosing files.

Keep excluded: .env, actual Streamlit secrets, virtualenv, pytest/cache/temp directories, local SQLite workspace, downloaded upstream/tool installations and throwaway smoke outputs. The new smoke run resides under ignored results/raw/smoke; detailed audit diagnostics reside under ignored .ota_state/publication-audit-v1. No important evidence was removed or silently ignored.

The retained manufacturer PDF is publicly downloadable, but its redistribution permission was not established by this technical audit. Confirm appropriate redistribution of third-party snapshots and review local-path metadata before choosing a public package. If a separate sanitized/distribution-safe derivative is needed, preserve the original private/raw package and use a new manifest/version; do not overwrite frozen evidence.

## 6. Known engineering limitations

- Final live workflow outcomes remain4/5; Flysky's false faithfulness rejection persists despite correct extraction. The five known embedded-document cases with two positive rules do not establish automotive ECU accuracy or independent generalization.
- Two final Z3 handoffs were feasible no-op scaffolds, not nonempty real-device update schedules.
- Z3 primary600 trials retain225 feasible,180 infeasible,180 unknown and15 watchdog outcomes; primary positive100-ECU scheduling was not demonstrated. Parent-process memory monitoring was historically unreliable; no corrected full-matrix rerun was performed.
- Fault evidence retains26/28 passing cases and two genuine bootability violations. Successful rollback does not erase observed unsafe states.
- MCUboot comparison is bounded simulated-flash reference validation, not full bootloader equivalence or hardware assurance.
- Shared-mode live OIDC, remote CI and current hosted-demo interaction were not verified here. Standards-concept mapping is not normative compliance/certification.

## 7. Required decisions before publication

1. Remove hidden local/private-configuration dependencies from offline tests with explicitly mocked/dummy settings; prove a clean no-.env run. Do not inject production credentials into tests or CI as a workaround.
2. Protect all byte-hashed evidence from Git newline conversion before staging, then run integrity checks on the resulting clean checkout.
3. Review/select the thousands of untracked evidence/source/test files together with required licenses. Resolve third-party snapshot redistribution and local metadata disclosure; preserve original evidence separately if necessary.
4. Only after those issues are resolved, rerun clean-checkout CI-equivalent verification and confirm publication status. No additional LLM repair/evaluation is required or authorized by this report.

The local configured suite passed, but **publication is BLOCKED by reproducibility/integrity issues**, not by hidden assertion failures or a fabricated all-clear. This audit changed only documentation. It made no Groq requests, installed no dependencies, changed no production code/prompts/frozen labels/evidence, and performed no commit, push, release or deployment.

Final Git status at report completion: **10 modified tracked files; 8555 untracked files** (including this report). No staging was performed.
