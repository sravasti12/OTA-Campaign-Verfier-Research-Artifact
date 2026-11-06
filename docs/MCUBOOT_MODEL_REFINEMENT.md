# MCUboot recovery model refinement — Phase 1D

**Phase 1D complete. Phase 1E has not started.** This phase refines comparison interpretation and evidence checks; it makes no production simulator change. The project remains a simulation, and the observations do not establish hardware or real-vehicle validation.

## Findings: policy distinctions, not simulator defects

Both Phase 1C mismatches were reviewed against production source, the recorded campaign inputs, the real MCUboot transcript and complete Python traces.

| Mismatch | Reviewed evidence | Decision |
| --- | --- | --- |
| `unauthorized_revert` | MCUboot selected original `0.0.1.0`. The Python campaign had no downgrade authorization, emitted `unauthorized_downgrade` blockers, reported recovery unavailable, and left the ECU unavailable with its last effective candidate version retained. | Intentional authorization-policy distinction. The bootloader's automatic revert mechanism has no equivalent human/ECU/version authorization input. The project must continue blocking unauthorized older-image boots. |
| `post_confirm_campaign_recovery` | MCUboot retained confirmed candidate `1.0.1.1`. Python first rebooted that same confirmed candidate, then executed an explicitly authorized recovery to original `0.0.1.0`. | Intentional orchestration/objective distinction. Comparing the native next-boot endpoint with the project's later campaign-restoration endpoint was insufficiently scoped for a mechanism-equivalence claim. Both observations are correct under their respective contracts. |

Relevant source contracts remain unchanged:

- `boot.guarded_boot` checks downgrade authorization and compatibility before allowing a selected image to become effective.
- `guarded_simulator._restore_confirmed` tries the persisted confirmed image first.
- `guarded_simulator._failed` subsequently invokes campaign recovery; a successful immediate reboot is not the campaign recovery goal.
- `boot_recovery.recovery_goal` requires original active images, available ECUs, original confirmed selections and compatible state.

Neither mismatch demonstrates a defect in those declared contracts. No invariant was weakened, no automatic authorization was added, and no recovery objective was changed. The Z3 planner, models, LLM integration, LangGraph workflow, public demo and all other production code were preserved.

## What changed

Added an isolated [refinement.py](../validation/mcuboot/refinement.py) review command, [regression tests](../validation/mcuboot/test_refinement.py), and [review.json](../validation/mcuboot/refinement_evidence/review.json). Phase 1C's `comparison.json`, C logs, environment evidence, Python traces and mismatch/property classifications remain unchanged.

The review has separate fields for:

1. **Original status and raw property differences:** the two scenarios still say `MISMATCH`; four still say `UNSUPPORTED`.
2. **Bootloader/mechanism scope:** physical swap, confirmation and revert are distinguished from the project's logical slot operations. Mechanism equivalence remains unestablished even for matching endpoints.
3. **Campaign-policy disposition:** the two differences are labelled `INTENTIONAL_POLICY_DIFFERENCE` only after their specific recorded policy conditions are verified.
4. **Aligned checkpoints:** the post-confirmation review records actual evidence of Python rebooting the candidate before campaign restoration. This supplements, rather than replaces, the final-state mismatch.
5. **Health/exposure scope:** the unsupported failed-trial row records actual native candidate selection and the absence of any effective candidate in the project's failed-health trace. It explicitly records that no application crash executed.

### Harness issue corrected

The legacy Phase 1C comparator's `unexpected_contradiction` flag depends on a broad scenario category. That is too permissive as an ongoing regression gate: a new fault in an already labelled intentional scenario could escape the unexpected-contradiction flag.

The new review gate does not treat that label as sufficient evidence. The unauthorized case must show a good original selected natively, no project rollback authorization, unavailable recovery and an actual authorization blocker. The post-confirmation case must show native confirmation, actual intermediate Python reboot to the target, scoped rollback authorization and a valid/available/confirmed original at the end. Additional image-validity or confirmation contradictions are not covered by the reviewed exception. The command exits nonzero when these checks fail.

Regression tests remove blockers, remove the intermediate reboot, introduce invalid native-image evidence and change final confirmation. Each must become `UNEXPECTED_CONTRADICTION`. These mutations are classifier tests only, not new MCUboot observations.

This is a **validation-harness refinement**, not a production modeling defect. The legacy command and historical report were retained for reproducibility; use the new refinement gate for the evidence-backed policy assessment.

## Unsupported scenarios and reasonable extensions

| Scenario | Current support and refinement | Reasonable next extension | Remaining unsupported claim |
| --- | --- | --- | --- |
| Invalid signature | The real C transcript rejected the requested bad-signature upgrade. The Python verification-failure endpoint also retained the original. The scenario remains `UNSUPPORTED` for cryptographic mechanism equivalence. | An optional isolated real-image verification adapter could accept signed fixture bytes and report authentication results separately from campaign compatibility. Define fixtures, trust key and malformed-image cases first. | The Boolean `Image.valid` model cannot demonstrate signature, header/TLV or trust-key validation. No cryptographic verifier was added. |
| Power loss during swap | The actual reference resumed the interrupted swap and selected the candidate; Python's coarse pre-activation fault aborted the campaign and restored the original. Different endpoints and unequal boundaries remain visible. | Reference-only operation sweeps can broaden bootutil evidence. A later model extension needs an explicit objective, flash geometry, progress/state mapping and supported interruption granularity before implementing a swap layer. | A logical A/B activation event is not a scratch-swap journal or sector-copy model. No speculative flash model was added. |
| Interrupted revert | Native interrupted-revert recovery selected the original; Python's authorized campaign recovery also ended at the original, but had no equivalent fault inside recovery. | Add a bounded recovery-event interface only if interrupted campaign recovery is a defined requirement. Keep native operation-level interruption evidence separate from logical recovery-action interruption. | Matching endpoints do not validate journal replay, torn metadata, recovery-internal cuts or repeated power faults. |
| Failed trial boot | Native missing-confirmation/reset and project pre-exposure health failure end at the original but have different candidate exposure. The new review explicitly reports this difference. | Missing confirmation is already covered by `unconfirmed_revert`; a future reset/withheld-confirmation driver can make that temporal distinction first-class without changing authorization. | Actual application failure detection, watchdog behavior and pre-handoff health equivalence remain unsupported. No application instructions or health monitor ran. |

Reasonable improvements implemented here are **layered interpretation, observed checkpoint alignment, and exposure reporting** using existing evidence. None requires new production semantics. The four unsupported scenarios were not promoted to matches, and no additional native scenario coverage is claimed.

## Updated coverage

The original twelve-scenario accounting is preserved:

| Original status | Count | Refined interpretation |
| --- | ---: | --- |
| MATCH | 6 | Bounded selected-image/confirmation endpoints; not whole-mechanism equivalence. |
| MISMATCH | 2 | Both supported by evidence as intentional campaign-policy distinctions; raw differences retained. |
| UNSUPPORTED | 4 | Cryptographic, scratch-progress/interruption and health/exposure limitations remain explicit. |
| INCONCLUSIVE | 0 | No original observation was missing. |

The refined review found **zero unexpected contradictions** in this dataset. That statement is limited to the recorded scenarios and reviewed checkpoints. Repeated resets use an explicit driver around existing public boot primitives, not a newly established production reset API. Known-good retention repeats the payload-corruption fault mode; counts are not independent fault-coverage percentages. Single-ECU fixtures do not validate fleet compatibility or parallel recovery.

## Evidence integrity and execution

The refinement command:

- Verifies original reference identity/features and all 14 referenced native/environment/Python evidence hashes before review.
- Records the original comparison report's own hash as a fifteenth provenance entry.
- Re-parses the authentic C transcript and checks that each normalized native result agrees with its stored comparison row.
- Reexecutes all twelve Python scenarios into a separate `refinement_evidence/` directory, requiring campaign inputs and final sampled observations to agree with Phase 1C.
- Verifies the original 15 provenance entries again after review, ensuring original artifacts were not changed during the run.
- Retains fresh Python trace hashes in the separate review report.

The reference remains MCUboot v2.4.0, commit `6d3b3d2c38ab20c242e5b9abb04d050086383eb2`, scratch swap, RSA-2048/SHA-256, primary validation, and the Phase 1B dependency/toolchain configuration. **No fresh native execution or new native scenarios were required or claimed in Phase 1D**; native outcomes come from verified actual Phase 1C C execution, not mocks or a Python bootloader approximation.

## Commands and test results

Run from `ota_verifier/`:

```powershell
# Verifies retained evidence, reruns Python scenarios, writes a separate review report.
.\.venv\Scripts\python.exe validation/mcuboot/refinement.py

# Policy-review tests plus differential and existing recovery regressions.
.\.venv\Scripts\python.exe -m pytest -q validation/mcuboot/test_refinement.py validation/mcuboot/test_differential.py tests/test_simulator.py tests/test_invariants.py tests/test_recovery.py tests/test_exhaustive_recovery.py tests/test_guarded_boot.py tests/test_exhaustive_guarded_recovery.py tests/test_boot_comparison.py
```

Actual combined regression result: **124 passed, 0 failed, 0 errors, 14 warnings**: 13 new refinement tests, 10 Phase 1C tests and 101 existing recovery tests. Warnings comprise thirteen existing LangSmith/Python deprecations and one pytest cache-path creation warning. The initial sandboxed attempt had seven temporary-directory setup errors and 117 passes; the rerun with approved access to the existing project-local temporary directory passed without changing tests or pytest configuration. The execution transcript is retained in `refinement_evidence/pytest.log`.

The integrity checks cover preserved evidence, not external authenticity guarantees: hashes detect changes relative to the retained manifest; they are not signed attestations. Machine-readable native source/build provenance remains in the linked Phase 1B/1C environment records.

After the final raw-transcript/features checks were added, the refinement-only suite was rerun: **13 passed, 0 failed/errors, 14 warnings** (`refinement-final-tests.log`). Final artifact verification checked **27 hashes**: 15 preserved Phase 1C provenance entries and 12 fresh Python traces.

## Remaining boundaries and next decision

The simulator remains a campaign-policy abstraction. It has no byte-accurate scratch journal, cryptographic image parser or real application health execution. Confirmation is an atomic modeled event; actual flash-write atomicity, signature trust provisioning, antirollback security counters, arbitrary fault sequences and other upgrade strategies remain outside these results.

No production model defect was found that justifies changing the simulator in this phase. A later phase should select one validation objective before extending it—for example a reset/confirmation event driver, a separate real-image verifier, or reference-only interruption coverage. Those are separate scopes, not implied work authorized here.

**Stopped after Phase 1D. Phase 1E requires user approval.** No commit, push or deployment was performed.
