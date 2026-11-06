# MCUboot differential recovery validation — Phase 1C

Executed 2026-11-06. **Phase 1C complete; Phase 1D has not started.** Production simulator, planner, models, compatibility rules, workflow, Streamlit code, existing tests and Python dependencies were not modified. This is a comparison of software simulations, including actual MCUboot C bootloader execution over simulated flash. No hardware, application instruction execution or real-vehicle validation is established.

## Conclusion

The current **guarded-trial-v1** simulator agrees with MCUboot at six bounded observable endpoints in the twelve declared scenarios. There are two observable mismatches attributable to explicit project policy/orchestration, and four unsupported mechanism/boundary comparisons. No unexpected contradiction was observed in the supported endpoint checks. These counts are descriptive, not a validation percentage: several scenarios share stimuli, and unsupported mechanisms cannot be scored as passing.

The evidence supports narrow predictions about candidate selection, explicit confirmation, authorized unconfirmed recovery, and rejection/retention endpoints. It does **not** establish that the simulator represents MCUboot scratch-swap recovery, cryptographic validation, application-health detection or arbitrary repeated resets. In particular, a reference interrupted upgrade resumed into the candidate while the project's coarse activation-fault counterpart returned to the original. That difference is retained in the report, but the interruption boundaries are not equivalent, so the scenario is UNSUPPORTED rather than a claimed direct contradiction.

## Exact reference and execution evidence

The environment from [Phase 1B](MCUBOOT_REFERENCE_ENVIRONMENT.md) was reused:

- MCUboot **v2.4.0**, commit `6d3b3d2c38ab20c242e5b9abb04d050086383eb2`.
- Scratch swap, one image pair, RSA-2048/SHA-256, primary-slot validation: `--no-default-features --features sig-rsa,validate-primary-slot`.
- Rust/Cargo 1.90.0, Ubuntu 24.04 WSL2, GCC 13.3.0, the same included Cargo lock and mbedTLS revision.
- Official K64f simulated geometry, alignment 8, erased value `0xff`, 128 KiB primary and secondary regions, 4 KiB scratch. This names a flash layout, not an executed physical board.

`run-differential.sh` checks the commit, mbedTLS revision, lock equality and cleanliness of C bootutil, bindings and upstream image source. It temporarily includes the observation-only `ota_differential.rs` test module, executes real `mcuboot_sys::c::boot_go` calls, captures evidence, and restores the upstream source on exit. No bootloader decision code is patched. The Rust driver asserts the compiled scratch/RSA/primary-validation capabilities and image count.

The native driver passed **one Rust test containing all twelve scenarios**, with individual boot responses and observations for each scenario. The Python command also successfully ran the native driver and then the unchanged Python implementation end to end. The final report was regenerated from that retained native execution using `--reuse-reference` after report-provenance checks were added; its `reference_reused` field explicitly records this. No mocked native outputs are used in the comparison report.

Artifacts under [validation/mcuboot/differential_evidence](../validation/mcuboot/differential_evidence/):

| File | Evidence |
| --- | --- |
| [comparison.json](../validation/mcuboot/differential_evidence/comparison.json) | Machine-readable inputs, expected outcomes, initial states, actual observations, property comparisons, categories, summary and evidence hashes. |
| [reference.log](../validation/mcuboot/differential_evidence/reference.log) | Actual C boot responses, interruption results, JSON observations, and successful native test footer. |
| `reference-command.log` | Exact Cargo invocation and native run transcript. |
| `driver.log` | End-to-end Python driver invoking WSL/Cargo and reporting comparison results. PowerShell may render normal native stderr as NativeCommandError records; the process exited successfully. |
| `environment.txt` | Executed commit, compiler versions, submodule revisions, dependency-lock/module/native-library hashes. |
| `instrumentation.patch` | Only the temporary test-module inclusion in upstream `image.rs`. |
| `<scenario>-simulator.json` | Actual campaign, Z3 plan, fault, full guarded simulation trace, findings, recovery proof and sampled/reset checkpoints for each scenario. |
| `pytest.log` | Final automated comparison and existing recovery test results. |
| `attempt-01-reference.log` | Failed initial harness attempt, retained rather than counted as a successful scenario run. |

Each native observation includes both slots' raw headers/trailers, addresses, whole-slot SHA-256 hashes, parsed versions, confirmation/copy flags, and comparisons against upstream fixture image bytes. Boot outcomes come from C return status and assertions; expected outcomes are separate declarations. Report generation rejects missing/duplicate scenarios, missing reset checkpoints, absent power cuts, failed/zero-test native runs, and environment evidence that does not identify the pinned commit and dependency lock. A native result contrary to the declared expected image is flagged even if both implementations agree with one another.

## Inputs and normalization

Reference image versions are **original `0.0.1.0` and candidate `1.0.1.1`** (MCUboot notation `0.0.1+0` and `1.0.1+1`). The Python campaign uses the same numeric components. Comparison normalizes numeric versions, not physical slot addresses: MCUboot swaps bytes into primary; the project selects logical slot B.

The reference begins with the original factory image in primary, its trailer erased, and a candidate staged in secondary. Upgrade magic is explicitly requested, including for the bad-signature fixture. Python begins earlier in the campaign with valid original slot A and an empty inactive slot; the existing simulator performs its own erase/write/verify stages. Initial states and this staging offset are recorded rather than declared identical. The original reference's erased confirmation flag is not equated to an unconfirmed test image: confirmation-bit comparison is used only at the candidate trial/confirmation checkpoints where it has the intended meaning.

The guarded policy is the primary comparison target because it explicitly models trial, confirmation, availability and health. The baseline policy remains covered by existing regression tests but was not subjected to differential comparison here. Results therefore do not validate both policies interchangeably.

For rollback cases, the campaign includes an explicit ECU/original-version downgrade authorization except in the deliberately unauthorized case. No permission is inferred from native output. All campaigns contain one ECU and no inter-ECU dependencies, so these observations say nothing about vehicle-wide compatibility or parallel fleet recovery.

`selected_version` means the image selected by a successful C bootloader return versus the available effective image in the project snapshot. It does not prove application health. `selected_valid` compares successful selection of known fixture bytes under primary validation with the project's Boolean validity; it does not establish equivalent cryptographic mechanisms. Confirmation compares the candidate's actual `image_ok` marker with the project's running-versus-confirmed selection.

The test-upgrade row samples the project's `boot` trace event before its automatic confirmation, not its final state. The persistence and repeated-reset rows additionally invoke existing public `power_loss` and `guarded_boot` primitives to boot the persisted confirmed slot. This is an explicit test driver choice, not a new production reset policy. Full campaign-failure behavior is compared separately in the post-confirmation row. All original complete simulation traces remain available.

## Comparison table: every declared scenario

O = original `0.0.1.0`; N = candidate `1.0.1.1`. An unavailable project ECU has no selected/running image even though its last effective version is retained in state.

| Scenario | Native stimulus and expected endpoint | Actual MCUboot outcome | Existing simulator input and actual outcome | Classification |
| --- | --- | --- | --- | --- |
| `test_upgrade` | Valid staged candidate, test boot; expect N unconfirmed. | N selected, `image_ok=0xff`, copy complete. | Nominal run sampled at `boot`: N effective, confirmed pointer still A. | **MATCH**, trial endpoint. |
| `confirmed_reboot` | Test boot, explicit confirmation write, next boot; expect N confirmed. | N selected; `image_ok=1` persists. | Nominal confirmation, then public reset/confirmed-slot boot primitives: N available and confirmed. | **MATCH**, primitive-driven persistence endpoint. |
| `unconfirmed_revert` | Test boot, omit confirmation, reset; expect O. | Reverts to O. | Power loss before `confirm`, explicit rollback permission: O restored, recovery available. | **MATCH**, authorized endpoint; recovery mechanisms differ. |
| `unauthorized_revert` | Same unconfirmed reset; MCUboot has no reviewer-permission input. | Reverts to O. | Same fault without downgrade permission: reboot to older image blocked, ECU unavailable; last effective N retained. | **MISMATCH**, intentional authorization policy. |
| `invalid_signature` | Upstream bad-signature candidate with pending upgrade magic; expect rejection and O. | O selected; candidate not activated. | `verification_failure` before verify: O retained. | **UNSUPPORTED** for signatures; selected-image endpoint agrees. |
| `payload_corruption` | Clear a bit in staged candidate payload, then boot; expect O. | Rejects corrupted candidate, selects O. | `write_corruption` after write: verify detects failure, O remains valid/available. | **MATCH**, abstract rejection endpoint only. |
| `swap_power_loss` | Interrupt before flash mutation operation 7 during test upgrade, resume boot; expect completed trial N. | Cut observed; next boot resumes and selects N. | `power_loss` before logical `activate`: campaign aborts and recovers O. | **UNSUPPORTED**, unequal cut boundaries; different endpoints explicitly recorded. |
| `interrupted_revert` | Complete test upgrade; interrupt before operation 7 of next boot's revert; resume. | Cut observed; resume selects O. | Power loss before confirmation and authorized recovery selects O; no injection within rollback available. | **UNSUPPORTED**, no equivalent recovery-internal boundary. |
| `failed_trial` | External reset without confirmation after test selection; expect eventual O. | N was selected first; later reset reverts to O. No application crash was executed. | `boot_failure` before boot: health failure prevents N ever becoming effective; final O. | **UNSUPPORTED**, health/exposure semantics differ despite same endpoint. |
| `repeated_resets` | Unconfirmed test boot followed by three resets; expect O after revert and thereafter. | O on resets 1, 2 and 3. | Authorized pre-confirm fault restores O; two additional public primitive resets retain O. | **MATCH**, bounded sequence with explicit driver. |
| `known_good_recovery` | Corrupted candidate with good original; expect original available. | O selected successfully. | Write corruption, recovery available with O. | **MATCH**, known-good retention; repeats the payload-corruption fault mode. |
| `post_confirm_campaign_recovery` | Confirm test candidate, reset; expect N retained. | N remains selected and confirmed. | Power loss after `confirm`: initially reboots confirmed N, then campaign recovery restores authorized O. | **MISMATCH**, intentional campaign recovery goal. |

**Summary: 6 MATCH, 2 MISMATCH, 4 UNSUPPORTED, 0 INCONCLUSIVE.** No unexpected supported-property contradiction was found. Unsupported rows retain each property's measured MATCH/MISMATCH in JSON; the scenario-level classification does not erase observed differences. Matching duplicate/reused stimuli are not independent new fault coverage.

## Interruption and corruption boundaries

Both interruptions are real executions of upstream C wrappers with the fault counter set to 7; the wrapper interrupts before a selected write/erase call. The recorded return is interrupted, and the next invocation uses the retained simulated flash with fresh bootloader context. This covers one chosen cut during upgrade and one during revert, **not all operations, torn writes, arbitrary repeated faults or hardware power behavior**. Raw intermediate slot metadata is retained; no claim is made that the project has a corresponding sector-level state.

Payload corruption is an external stored-byte fault: the driver clears a bit in an aligned 8-byte payload block. Upstream SimFlash forbids all second writes to programmed addresses, including otherwise physically plausible bit clears. The injection temporarily disables only that harness write-history guard to alter the stored bytes, then restores it **before C bootutil runs**. Bootloader validation and all normal flash operations remain unchanged. It is not a mocked validation outcome.

The first implementation attempted the bit clear through a normal second write and failed with `Write to unerased location at 0x40020`. That harness construction error is preserved in `attempt-01-reference.log`; the partial run was not accepted as validation. The corrected complete run has all twelve scenario observations and a passing native footer.

## Findings and recommended Phase 1D decisions

1. **Separate bootloader reboot from campaign rollback orchestration.** A confirmed-image reboot retains N in both implementations at the immediate reboot checkpoint, but the project's full failure path subsequently restores O. Preserve both checkpoints in evidence. Decide explicitly whether future policies should resume a campaign, retain a confirmed partial update, or restore campaign originals; do not silently change the present goal.
2. **Make automatic bootloader revert versus downgrade authorization explicit.** The unauthorized case is a real observable difference, not evidence of a planner bug. A future MCUboot-specific profile must decide how bootloader test/revert is authorized in advance without silently bypassing the existing invariant.
3. **Add reset/withheld-confirmation event support if approved.** The current nominal run confirms automatically. Primitive-driven tests demonstrate bounded states, not a production campaign reset API. An event driver could make those temporal scenarios first-class while retaining existing policy behavior.
4. **Treat scratch progress as a separate model layer or explicitly exclude it.** One coarse `activate` fault cannot predict resumable C flash copying. A future layer would need sector geometry, durable status writes and recovery-internal fault boundaries. Do not relabel the current aborted campaign as MCUboot swap resume.
5. **Keep image integrity separate from application health and exposure.** MCUboot selected N before a missing-confirmation reset; guarded boot failure never exposed it. A bootloader-specific adapter should describe handoff and later health/confirmation as distinct events. This phase executed no application crash detector.
6. **Use an optional real image-verification adapter for cryptographic claims.** Boolean validity supports abstract rejection outcomes but cannot establish signature checking. Keep authentication evidence separate from campaign compatibility.
7. **Broaden coverage only after these semantics are agreed.** Future work may sweep every supported operation, add repeated cuts and vary geometry. Multi-ECU compatibility, parallel writes, antirollback, encrypted images and alternative upgrade strategies remain unvalidated by this report.

These are recommendations only. No production correction or Phase 1D implementation was made.

## Automated commands and actual test results

From the project root with the Phase 1B prerequisites installed:

```powershell
# Executes the real reference, then every Python scenario and writes comparison.json.
.\.venv\Scripts\python.exe validation/mcuboot/differential.py

# Explicit analysis mode: reuses saved authentic C observations; Python still executes.
.\.venv\Scripts\python.exe validation/mcuboot/differential.py --reuse-reference

# Comparison contract tests and retained-real-reference integration tests.
.\.venv\Scripts\python.exe -m pytest -q validation/mcuboot/test_differential.py
```

The executable command requires WSL distribution `Ubuntu-24.04` by default (`--distribution` overrides it). It fails if the native runner fails, removes a stale report before attempting a new run, and produces the report even for observed mismatches. Exit 1 means an unexpected contradiction/reference outcome; exit 2 means inconclusive observations. Documented policy mismatches remain visible in the report without causing an unexpected-regression exit. Missing real reference evidence fails the integration tests; there is no mocked fallback.

The final regression command was:

```powershell
.\.venv\Scripts\python.exe -m pytest -q validation/mcuboot/test_differential.py tests/test_simulator.py tests/test_invariants.py tests/test_recovery.py tests/test_exhaustive_recovery.py tests/test_guarded_boot.py tests/test_exhaustive_guarded_recovery.py tests/test_boot_comparison.py
```

Actual final result: **111 passed, 0 failed, 0 errors, 14 warnings**: ten new validation tests plus 101 existing tests. Thirteen warnings concern LangSmith's Python 3.14 deprecation of `asyncio.iscoroutinefunction`; one is a preexisting pytest cache-path creation warning. An initial sandboxed run had four temporary-directory permission setup errors and 107 passes; rerunning with approved filesystem access resolved all four without deleting tests or changing pytest settings. Upstream bootsim also emits its existing twenty compiler deprecation warnings in native logs. No full-project or full-upstream-suite pass is implied.

The classifier unit tests use synthetic dictionaries only to test fail-closed classification (including unexpected differences, unsupported matches and missing evidence). They are explicitly not execution evidence. The integration tests consume the actual native transcript, rerun the Python implementation and verify all manifests while retaining both policy mismatches. Test-created Python traces use a pytest temporary directory so the canonical report's evidence is not overwritten.

Source checks confirmed no differences under `src/`, `app/`, `tests/`, `pyproject.toml` or `requirements.txt`. Phase 1C adds only the independent harness, its tests/evidence, this document and a JSON line-ending rule in the validation folder. Existing unrelated working-tree changes were preserved. No commit, push or deployment was performed.

**Approval is required before Phase 1D.** The current findings should guide that decision; a broad claim that OTA Verifier recovery is MCUboot-equivalent is not supported.
