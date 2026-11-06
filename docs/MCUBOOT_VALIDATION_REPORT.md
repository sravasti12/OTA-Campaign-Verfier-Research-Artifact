# MCUboot validation: final engineering evidence report

## Executive summary

OTA Campaign Verifier's guarded recovery model was compared with **actual MCUboot v2.4.0 C bootloader execution over simulated flash**. The final twelve scenarios retain **6 MATCH, 2 MISMATCH, 4 UNSUPPORTED and 0 INCONCLUSIVE**. The mismatches are intentional campaign-policy distinctions, not corrected simulator defects. Unsupported mechanisms were not counted as successful validations.

The unified runner separates native builds, fresh native execution, replay of recorded native evidence, fresh Python simulation, regression testing and documentation analysis. It creates a separate evidence package per run and verifies a SHA-256 manifest that includes the consolidated report itself. Earlier phase evidence is preserved.

These results support bounded selected-image and confirmation endpoints. They do not establish full MCUboot equivalence, hardware/application execution, real-vehicle validation or regulatory compliance.

## Engineering objective and scope

The objective is to determine which observable recovery predictions are supported by a real open-source bootloader implementation and make the differences independently reviewable. The campaign-level requirements remain intact: explicit older-version authorization, compatible intermediate states and recovery to original campaign images.

The comparison targets `guarded-trial-v1` on a single ECU with no inter-ECU dependencies. The baseline policy and other project components receive regression coverage, not a claim of differential equivalence. Existing Z3 planning, LLM integration, LangGraph workflow and public Streamlit behavior are not modified by this work.

## Reference implementation and environment

| Component | Reference |
| --- | --- |
| MCUboot | v2.4.0, commit `6d3b3d2c38ab20c242e5b9abb04d050086383eb2` |
| Execution | Official Rust simulator, linked to C bootutil |
| Upgrade strategy | Scratch swap, one image pair |
| Features | `--no-default-features --features sig-rsa,validate-primary-slot` |
| Image authentication | RSA-2048/SHA-256, upstream test keys |
| Native toolchain | Rust/Cargo 1.90.0; GCC 13.3.0; Ubuntu 24.04 WSL2 |
| Dependency lock | Included `validation/mcuboot/Cargo.lock`; resolved package versions/checksums pinned |
| mbedTLS | `2ca6c285a0dd3f33982dd57299012dacab1ff206` |
| Flash geometry | Upstream simulated K64f layout; 128 KiB primary/secondary, 4 KiB scratch, alignment 8, erased `0xff` |
| Images | Original `0.0.1+0`, candidate `1.0.1+1`; Python numeric forms `0.0.1.0` and `1.0.1.1` |

Exact host/compiler/submodule records and native archive hashes are in each package's `reference/environment.txt` and `differential/environment.txt`. The consolidated JSON records the current Python environment separately from the captured native environment. Linux package patch versions and WSL kernel details are observations, not a pinned operating-system image; see [the environment setup](MCUBOOT_REFERENCE_ENVIRONMENT.md) for that limitation.

## Methodology and execution labels

The [single runner](../validation/mcuboot/validate.py) performs these stages:

1. Verifies preserved Phase 1C evidence and fingerprints production source, existing tests and dependency files.
2. In **fresh** mode, builds the pinned native reference, runs three upstream tests plus two observation tests, and runs the twelve-scenario C driver. Cargo may reuse build artifacts; **fresh execution means the test binaries ran again**, not necessarily a clean rebuild.
3. In **replay** mode, copies recorded native logs and labels them `REPLAYED_NATIVE_EVIDENCE`. No build or native test command runs in this mode. Python still executes.
4. Executes all twelve Python scenarios with the existing planner/simulator, then runs the evidence-backed refinement checks using that run's comparison report. These outputs are written outside historical evidence folders.
5. Runs the complete existing `tests/` suite plus the differential, refinement and final-runner tests. JUnit supplies passed/failed/error/skipped counts; pytest logs preserve warnings and diagnostic output.
6. Checks that protected source and historical evidence are unchanged, snapshots the validation scripts for review, writes `validation.json` and `SHA256SUMS.json`, and independently verifies the manifest.

Documentation interpretation is labelled `DOCUMENTATION_ONLY`; it adds no execution coverage. A successful package status means the engineering checks passed with documented differences, not that all twelve scenarios matched. The native tests' six test-function executions are also distinct from the twelve scenario comparisons and from pytest counts.

Each scenario retains initial native and Python slot states, stimuli, expected endpoint, actual observations, per-property comparison, original status, refined policy explanation and evidence paths/hashes. Normalization uses observed image versions rather than slot letters: physical scratch swapping and logical A/B selection have different transitions. The initial native candidate is already staged; Python starts before its own write/verify stages. The difference is retained in the manifests.

## Complete scenario results

O = original `0.0.1.0`; N = candidate `1.0.1.1`. “Unavailable” is not a selected version, even if a last effective version remains in state.

| Scenario | Actual MCUboot endpoint | Actual project endpoint | Status and scope |
| --- | --- | --- | --- |
| Successful test upgrade | N selected, unconfirmed | N effective at the pre-confirm boot checkpoint | **MATCH**, bounded trial endpoint |
| Confirmation across reboot | N remains confirmed after reboot | N remains confirmed through public reset primitives | **MATCH**, bounded persistence endpoint |
| Unconfirmed revert | O after reset | Authorized recovery restores O | **MATCH**, endpoint; different mechanisms |
| Unconfirmed revert without authorization | O after automatic revert | Older boot blocked; ECU unavailable | **MISMATCH**, intentional authorization policy |
| Invalid signature | Bad candidate rejected; O selected | Verification-failure abstraction retains O | **UNSUPPORTED** for cryptographic equivalence; endpoint agreement retained |
| Payload corruption | Corrupted candidate rejected; O selected | Corruption detected; O retained | **MATCH**, abstract rejection endpoint |
| Power interruption during swap | Interrupted operation observed; resume selects N | Coarse pre-activation fault aborts and restores O | **UNSUPPORTED**, unequal boundaries and different endpoints |
| Interrupted revert recovery | Interrupted revert resumes to O | Authorized logical recovery ends at O | **UNSUPPORTED**, no recovery-internal cut equivalent |
| Failed trial/missing confirmation | N selected first, then reset returns to O | Health failure prevents N becoming effective; O remains | **UNSUPPORTED**, different exposure and health semantics |
| Repeated resets | O through three reset checkpoints | O after recovery and two further public reset operations | **MATCH**, bounded driver sequence |
| Known-good retention/recovery | O available with corrupt candidate | O available, recovery defined | **MATCH**, repeats payload-corruption fault mode |
| Post-confirmation campaign restoration | Confirmed N remains selected | Reboots N, then explicitly restores authorized O | **MISMATCH**, intentional campaign recovery objective |

Totals: **6 MATCH; 2 MISMATCH; 4 UNSUPPORTED; 0 INCONCLUSIVE.** Matching reused stimuli are not independent new fault modes or a coverage percentage. No unexpected supported-property contradiction was identified in the recorded scenarios.

## Analysis of the policy mismatches

**Authorization:** MCUboot's automatic test-image revert has no reviewer-scoped downgrade-authorization input. The project intentionally checks that permission. The refined gate requires actual authorization blockers and unavailable recovery before accepting this explanation; a scenario label alone is insufficient.

**Restoration objective:** the immediate confirmed-image reboot agrees: both select N. The project then performs a separate campaign-level recovery to the authorized original. Comparing that later policy endpoint with MCUboot's next-boot endpoint produces a real final-state difference, preserved as `MISMATCH`. The refined gate requires the intermediate N reboot, exact rollback authorization and a healthy original final state.

No production defect was found that justified changing either invariant. Additional image-validity, confirmation or unexplained availability differences fail the refined review rather than inheriting an intentional label. [Phase 1D analysis](MCUBOOT_MODEL_REFINEMENT.md) documents these guards and regression tests.

## Unsupported scenarios and remaining gaps

- **Scratch progress:** only two selected operation-counter cuts were exercised—one upgrade and one revert. They interrupt before a flash write/erase, not inside a torn operation. The Python model has no sector-copy/status journal or equivalent recovery-internal boundary. Native resume evidence does not validate that abstraction.
- **Signatures:** the native reference uses actual authentication code; the project uses Boolean image validity. Abstract rejection endpoints cannot establish a parser, signature verifier, trust provisioning or cryptographic equivalence.
- **Application health:** bootutil returns a selected image but does not execute the application. Missing confirmation plus reset is an external stimulus. It cannot establish watchdog/crash detection or equivalence with guarded pre-exposure health checks.
- **Reset driver:** repeated-reset/persistence comparisons explicitly call existing public primitives. They do not establish a complete production campaign reboot interface.
- **Broader scope:** no multi-ECU native coordination, hardware flash tearing, arbitrary repeated faults, encrypted images, alternative upgrade strategies, secure-counter behavior or fleet compatibility is established.

Future work should choose one bounded objective at a time: a reset/confirmation event driver, isolated signed-image verification, or reference-only operation sweeps. No scalability, live-LLM evaluation or regulatory-evidence phase is authorized by this package.

## Reproduction: Windows PowerShell

From the project root, use the existing Python environment and the [WSL/toolchain setup instructions](MCUBOOT_REFERENCE_ENVIRONMENT.md). No new Python dependency is required.

```powershell
# Full fresh execution; choose a NEW output directory on every invocation.
.\.venv\Scripts\python.exe validation/mcuboot/validate.py --mode fresh --output validation/mcuboot/final_evidence/my-fresh-run

# Explicit historical-native replay; Python and regression tests still run.
.\.venv\Scripts\python.exe validation/mcuboot/validate.py --mode replay --output validation/mcuboot/final_evidence/my-replay-run

# Verify every manifest entry, including the consolidated report itself.
.\.venv\Scripts\python.exe validation/mcuboot/validate.py --verify validation/mcuboot/final_evidence/my-fresh-run/validation.json
```

Default native distribution is `Ubuntu-24.04`; use `--distribution` to change it. If `--output` is omitted, the runner chooses a UTC timestamp directory. Existing output directories are rejected rather than overwritten. The reference checkout stays in ignored `.mcuboot-reference/`; build, command, environment, comparison, refinement and pytest artifacts remain in the selected package directory.

The full pytest stage is equivalent to:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests validation/mcuboot/test_differential.py validation/mcuboot/test_refinement.py validation/mcuboot/test_validate.py --junitxml=pytest-results.xml
```

Do not run native harnesses concurrently against the same checkout: observation-module insertion is temporary and sequential. On this workstation, sandboxed pytest cleanup of the existing temporary directory requires approved filesystem access. The runner does not bypass tests or rewrite pytest configuration to avoid that requirement.

## Reproduction: from WSL2

The existing Windows virtual environment can be invoked through WSL interoperability while the runner uses Ubuntu for native C execution:

```bash
cd /mnt/c/Users/KIIT/Desktop/OTACampaignVerifier/ota_verifier
.venv/Scripts/python.exe validation/mcuboot/validate.py --mode fresh --output validation/mcuboot/final_evidence/my-wsl-fresh-run
.venv/Scripts/python.exe validation/mcuboot/validate.py --verify validation/mcuboot/final_evidence/my-wsl-fresh-run/validation.json
```

Adjust the project path. These commands use the Windows Python environment, not an assumed Linux virtual environment. A native Linux Python environment would need the project's normal dependencies separately; that alternative is not an environment tested by this package.

## Evidence package interpretation

`validation.json` contains scenario details, execution labels, actual test counts, recorded environment, policy reviews, gaps, source-integrity checks and artifact hashes. `SHA256SUMS.json` adds a digest of `validation.json` without a circular self-hash. The verification command checks all entries and refuses paths outside the package. These are integrity manifests, not digitally signed attestations or independent proof of provenance.

`reproduction_source/` snapshots the harness scripts and lock for review. They are intended for their repository locations with the project dependencies/reference checkout, not execution as a standalone copied subdirectory. Generated packages preserve failed command logs and failed test outcomes where a stage fails; a zero-test regression run is rejected. A build failure prevents dependent comparison claims rather than substituting simulated native results.

## Recorded final execution

The fresh run is [phase1e-fresh/validation.json](../validation/mcuboot/final_evidence/phase1e-fresh/validation.json), with [the complete manifest](../validation/mcuboot/final_evidence/phase1e-fresh/SHA256SUMS.json), [pytest output](../validation/mcuboot/final_evidence/phase1e-fresh/pytest.log) and [JUnit results](../validation/mcuboot/final_evidence/phase1e-fresh/pytest.xml).

- Fresh native execution: **5 reference test functions passed**, plus **1 native driver test covering 12 scenarios**.
- Fresh Python regression run: **582 passed, 0 failed, 0 errors, 0 skipped, 14 warnings**, in 345.85 seconds as recorded by pytest. This duration is an observed run time, not a benchmark.
- Comparison: **6 MATCH, 2 MISMATCH, 4 UNSUPPORTED, 0 INCONCLUSIVE**; refined review reports no unexpected contradictions.
- **58 package artifact hashes verified**, including the consolidated report itself. The report SHA-256 is `47d3ccacc4eb5c93483ab7a8902eac369fb075932b9a92ccefaa3c6dd9e00716`.
- Both protected-source and historical-evidence integrity checks returned true.

The warnings comprise thirteen existing LangSmith/Python deprecations and one existing pytest cache-path warning. Native logs preserve the upstream compiler deprecations and unsupported-geometry notices. No test was deleted, skipped or reclassified to obtain the result. No native compile/execution failure or Python regression occurred in this fresh run.

After that run, four additional runner-status contract tests were added: documented differences remain acceptable, while inconclusive comparisons, unexpected native outcomes and refinement contradictions cannot receive a successful package status. The original fresh package includes its exact source snapshot and test count; subsequent replay testing is reported separately rather than retroactively changing that historical count.

The completed replay-mode check is [phase1e-replay/validation.json](../validation/mcuboot/final_evidence/phase1e-replay/validation.json), with [its manifest](../validation/mcuboot/final_evidence/phase1e-replay/SHA256SUMS.json), [pytest output](../validation/mcuboot/final_evidence/phase1e-replay/pytest.log) and [JUnit results](../validation/mcuboot/final_evidence/phase1e-replay/pytest.xml).

- **No fresh native execution:** the report explicitly labels native results as `REPLAYED_NATIVE_EVIDENCE`.
- Fresh Python simulator/refinement executions and full regression run: **586 passed, 0 failed/errors/skipped, 14 warnings**, in the recorded 336.76 seconds. The four extra tests are the added package-status guards.
- Comparison remains **6 MATCH, 2 MISMATCH, 4 UNSUPPORTED, 0 INCONCLUSIVE**.
- **50 artifact hashes verified**. Replay report SHA-256: `f1c7c4d11c9be8c60fe15d0a975a155ede1159ceeda58a76ccde601477b41972`.
- Both protected-source and historical-evidence checks again returned true. The current stricter package-status guard was also applied successfully to the preserved fresh observations without changing their files or claiming a new native run.

Both packages have status `PASSED_WITH_DOCUMENTED_DIFFERENCES`. All **108 manifest entries across the two packages** verified; this is an entry count, not a count of unique file contents or validated scenarios. No regression or execution blocker remains. The existing fourteen-warning set and unsupported technical scope remain unresolved limitations, with diagnostics retained.

The source hash check and full test suite establish local regression evidence for the Z3 planner, offline/mocked LLM adapters, LangGraph workflow and public demo code. They do not measure live LLM quality, verify the deployed URL interactively, or exercise external identity services. No deployment or remote Git operation was performed.

Earlier phase results remain separately documented in [Phase 1B](MCUBOOT_REFERENCE_ENVIRONMENT.md), [Phase 1C](MCUBOOT_DIFFERENTIAL_VALIDATION.md) and [Phase 1D](MCUBOOT_MODEL_REFINEMENT.md); those historical logs are not presented as fresh execution.

## Files created or modified in Phase 1E

| Files | Change |
| --- | --- |
| `validation/mcuboot/validate.py` | Unified fresh/replay runner, actual outcome parsing, source/evidence integrity checks and independent package verification. |
| `validation/mcuboot/test_validate.py` | Eight integrity, JUnit and result-gating tests in the final source version. |
| `build-reference.sh`, `run-reference.sh`, `run-differential.sh` under `validation/mcuboot/` | Optional `MCUBOOT_EVIDENCE_DIR` redirects outputs to a new package; historical default commands remain compatible. |
| `validation/mcuboot/differential.py` | Optional separate native-input directory, allowing fresh packages without overwriting Phase 1C. |
| `validation/mcuboot/refinement.py` | Optional comparison-report input and correct relative evidence paths, preserving default historical review behavior. |
| `validation/mcuboot/.gitignore` | Scoped exception keeps final-package build transcripts visible despite the repository-wide build-directory ignore rule. |
| `validation/mcuboot/.gitattributes` | Evidence directories are byte-preserved; Git newline conversion must not invalidate their hashes. Source-script line-ending rules remain separate. |
| `README.md` | Concise validation section/report link; earlier 548-test release record labelled as historical rather than the new run's count. |
| `docs/MCUBOOT_VALIDATION_REPORT.md` | This engineering report and reproduction instructions. |
| `validation/mcuboot/final_evidence/phase1e-fresh/` and `phase1e-replay/` | Raw logs, environment records, comparison/refinement JSON, fresh Python traces, JUnit outcomes, script snapshots, consolidated reports and manifests. |

All other preexisting working-tree changes were preserved. No changes were made to production behavior to manufacture agreement.

**Phase 1E ends here. No scalability/LLM-evaluation or regulatory-evidence phase was begun. Further work requires approval.**
