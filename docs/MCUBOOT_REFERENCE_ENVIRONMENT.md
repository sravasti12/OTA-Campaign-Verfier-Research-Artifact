# MCUboot Phase 1B: executable reference environment

Execution date: 2026-11-06. **Phase 1B succeeded. Phase 1C has not started and requires separate approval.** OTA Campaign Verifier remains a simulation. Its production Python code, tests, workflow and safety policies were not changed.

## Reference identity

| Component | Executed configuration |
| --- | --- |
| MCUboot | v2.4.0, commit `6d3b3d2c38ab20c242e5b9abb04d050086383eb2` |
| Harness | Official `sim/` Rust simulator, linking MCUboot C bootutil |
| Features | `--no-default-features --features sig-rsa,validate-primary-slot` |
| Upgrade | Swap using scratch; one image pair; no encryption or antirollback features |
| Authentication | RSA-2048/SHA-256, upstream simulator's test keys |
| Environment | Windows host; Ubuntu 24.04.4 LTS on WSL2, x86_64 Linux |
| Rust/Cargo | 1.90.0; exact compiler identifiers in the environment evidence |
| C compiler | GCC 13.3.0, Ubuntu package `13.3.0-6ubuntu2~24.04.1` |
| mbedTLS | `2ca6c285a0dd3f33982dd57299012dacab1ff206` |
| mbedTLS framework | `750634d3a51eb9d61b59fd5d801546927c946588` |
| Rust dependencies | Included `validation/mcuboot/Cargo.lock`, SHA-256 `2892bcc36e7a0ad01d96dd13a0606c8627d8ea2c8ed90ab63426bac3510e6cb1` |

The local pinned build script was inspected: absence of alternate upgrade features selects `MCUBOOT_SWAP_USING_SCRATCH`; `sig-rsa` selects RSA-2048 and mbedTLS; the primary-validation feature enables `MCUBOOT_VALIDATE_PRIMARY_SLOT`. Observation tests query the compiled C capability functions and assert scratch, RSA-2048, primary validation and one image. This checks the executed binary, not just a configuration file. [Pinned upstream build script](https://github.com/mcu-tools/mcuboot/blob/6d3b3d2c38ab20c242e5b9abb04d050086383eb2/sim/mcuboot-sys/build.rs).

The observation fixture uses upstream `DeviceName::K64f`: 128 sectors of 4096 bytes; primary at `0x20000` with length `0x20000`; secondary at `0x40000` with length `0x20000`; scratch at `0x60000` with length `0x1000`; programming alignment 8; erased value `0xff`. This is simulated flash geometry, not execution on a K64F board.

The fixture deliberately retains upstream-generated versions **0.0.1+0** and **1.0.1+1**, rather than modifying upstream image generation to obtain the illustrative versions in the audit plan. The original factory image initially has an erased trailer; the staged candidate has upgrade magic. Do not describe the original as already carrying an explicit confirmation marker. Header bytes and trailer state are recorded in the observation log.

## Reproduce from PowerShell

Run from `ota_verifier/`. An existing Ubuntu 24.04 WSL2 distribution was used; native Windows has MinGW GCC 6.3 but no Rust/Cargo, so a native build was not attempted. WSL was chosen to use the installed Linux environment and GCC toolchain. Native Windows incompatibility has not been proven.

Check WSL and install the prerequisites inside the chosen distribution:

```powershell
wsl --list --verbose
wsl -d Ubuntu-24.04 -u root -- apt-get update
wsl -d Ubuntu-24.04 -u root -- apt-get install -y build-essential pkg-config curl ca-certificates
wsl -d Ubuntu-24.04 -- curl --proto =https --tlsv1.2 -sSf https://sh.rustup.rs -o /tmp/ota-mcuboot-rustup.sh
wsl -d Ubuntu-24.04 -- sh /tmp/ota-mcuboot-rustup.sh -y --profile minimal --default-toolchain 1.90.0 --no-modify-path
```

On this machine the package versions were `build-essential=12.10ubuntu1`, `gcc=4:13.2.0-7ubuntu1`, `gcc-13=13.3.0-6ubuntu2~24.04.1`, `libc6-dev=2.39-0ubuntu8.9`, and `pkg-config=1.8.1-2build1`. These versions are recorded rather than silently assuming an arbitrary system compiler is identical. Ubuntu repositories can change; exact historical package replay may require an Ubuntu archive/snapshot. A container/root-filesystem image is not pinned by this phase.

Then run:

```powershell
.\validation\mcuboot\reference.ps1 -Action Build
.\validation\mcuboot\reference.ps1 -Action Run
```

The wrapper converts the project path with `wslpath` and propagates failure. Use `-Distribution` if your distribution name differs. No Python packages are installed for the reference environment.

`Build` clones into ignored `.mcuboot-reference/upstream` when absent, checks out the exact commit, initializes the required mbedTLS submodule recursively, copies the included lock into the **workspace root**, and compiles with:

```bash
cd .mcuboot-reference/upstream/sim
cargo +1.90.0 test --locked --no-default-features \
  --features sig-rsa,validate-primary-slot --no-run -vv
```

The retained dependency lock is a newly resolved snapshot from the initial setup, **not the untouched upstream lock**. Its delta is retained in `evidence/cargo-lock.patch`; subsequent setup requires that included lock and does not resolve fresh versions. Registry package versions and checksums are pinned there. MCUboot C sources and the mbedTLS submodule remain at their selected revisions. Initial setup fetched additional Cypress submodules with the upstream recursive command; they are recorded in the environment log but are not required by the selected build. The repeatable script fetches only mbedTLS and its nested dependency.

`Run` executes upstream `basic_revert`, `norevert` and `bad_secondary_slot` individually using `--test core <name> -- --exact --nocapture --test-threads=1`. It requires one passing test for each filter, preventing a zero-test success. Those tests iterate upstream device/alignment/erased-value configurations; incompatible geometries are explicitly logged as skipped. This is not exhaustive coverage of every geometry or the entire upstream suite.

It then temporarily adds a test-only module inside upstream `sim/src/image.rs`, copies `ota_reference.rs` into that isolated checkout, and runs:

```bash
cargo +1.90.0 test --locked --no-default-features \
  --features sig-rsa,validate-primary-slot --lib ota_reference:: -- \
  --nocapture --test-threads=1
```

The module uses existing image generation, flash and verification helpers and calls `mcuboot_sys::c::boot_go`. It does not implement boot policy. The exit trap restores the upstream image source and removes only the copied module. The runner first refuses to overwrite an existing image-source change and checks bootutil/binding sources for modifications. The instrumentation patch and module hash are retained. Both observation tests must pass; a nonzero Cargo exit fails the runner through `pipefail`.

## Evidence and observed behavior

Evidence is under [validation/mcuboot/evidence](../validation/mcuboot/evidence/):

| Artifact | What it establishes |
| --- | --- |
| `build.log` | Actual compilation/link commands, dependency/toolchain information and `BUILD_COMPLETE`. |
| `upstream-basic_revert.log` | One actual upstream revert test passed, including its configuration iterations. |
| `upstream-norevert.log` | One actual upstream confirmation/persistence test passed. |
| `upstream-bad_secondary_slot.log` | One actual upstream bad-signature rejection test passed. |
| `observations.log` | Two executed test scenarios, boot responses, slot hashes, raw headers/trailers and decoded confirmation/copy flags. |
| `environment.txt` | OS/package/compiler/submodule versions, lock/module/library/binary hashes and native C symbols. |
| `instrumentation.patch`, `cargo-lock.patch` | Exact test hook and dependency-lock deviations from the pinned checkout. |
| `attempt-01-lock-path.log` | Preserved initial setup failure, resolved before successful compilation. |
| `attempt-02-wrapper-path.log`, `runner.log` | Initial Windows path-conversion failure and final PowerShell entry-point transcript. |

The native archive in this execution had SHA-256 `722a6a90ebb6c875af527de3127f84090cbb6c9f75d1bad160540b4f02df558e`. Its symbol table includes `context_boot_go`, `swap_run` and `bootutil_get_caps`. Combined with recorded successful boot responses and changed flash bytes, these are evidence of real bootutil execution. Absolute paths/debug builds can change binary hashes between environments; these are evidence identifiers, not a promise of bit-identical builds.

| Observation checkpoint | Primary image | `image_ok` | `copy_done` | Boot result |
| --- | --- | --- | --- | --- |
| Initial staged campaign | Original 0.0.1+0 | `0xff` (unset) | `0xff` (unset) | Before boot |
| Completed test upgrade | Candidate 1.0.1+1 | `0xff` | `0x01` | Return 0; zero C assertions; primary offset `0x20000` |
| Explicit confirmation written | Candidate | `0x01` | `0x01` | External confirmation stimulus |
| Next boot after confirmation | Candidate | `0x01` | `0x01` | Return 0; zero C assertions |
| Separate unconfirmed trial | Candidate | `0xff` | `0x01` | Return 0; zero C assertions |
| Next boot without confirmation | Original | `0x01` | `0x01` | Return 0; zero C assertions; revert observed |

The confirmation stimulus uses upstream `mark_permanent_upgrades`, which writes `image_ok`, as upstream `run_norevert` does. No application health monitor or real application confirmation API invocation is claimed. Each subsequent `boot_go` creates fresh bootloader context over retained simulated flash. The expected images are compared against actual flash contents through upstream image verification helpers, not just inferred from a success code.

Slot hashes include metadata, so a confirmation write changes a whole-slot hash even when the application bytes are unchanged. RSA-PSS fixture signatures and pointer addresses in debug responses can vary across runs; use recorded headers, image comparisons and flags to assess behavioral reproduction rather than expecting identical log text.

## Actual checks and limitations

- Official targeted tests: **3 passed, 0 failed** (one Rust test each; 24 other core tests filtered per invocation).
- Added observation tests: **2 passed, 0 failed**, with runtime C capability assertions and both upgrade outcomes verified.
- Existing OTA recovery-focused suite: **101 passed, 0 failed, 0 errors, 13 warnings**. Warnings are the installed LangSmith dependency's Python 3.14 deprecation of `asyncio.iscoroutinefunction`; production code/tests were unchanged.
- Upstream `bootsim` reports **20 compiler deprecation warnings**, repeated across Cargo invocations. Verbose dependency compilation also reports dependency warnings; raw build output is retained. Runtime logs include expected unsupported-geometry skips. No warnings were suppressed or treated as proof of scenario execution.
- No application instructions, RTOS, CPU handoff, hardware flash, vehicle or watchdog were exercised. The official simulator executes bootloader C over simulated flash. Power-interruption sweeps and OTA-model comparison are not part of the executed Phase 1B tests.
- Environment issues resolved: sandbox networking/WSL access required approved elevated tool execution; Cargo lock was initially sought in the wrong directory; Windows checkout CRLF required a line-ending-aware Git cleanliness check; the PowerShell wrapper needed forward slashes for `wslpath` and explicit exit-code handling for normal Cargo stderr. There is no remaining compile/execution blocker for the selected WSL configuration.

The recovery-focused pytest command was:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_simulator.py tests/test_invariants.py tests/test_recovery.py tests/test_exhaustive_recovery.py tests/test_guarded_boot.py tests/test_exhaustive_guarded_recovery.py tests/test_boot_comparison.py
```

Only `.gitignore` was extended to exclude the downloaded reference checkout/build outputs. Setup, lock, observation code and evidence live under `validation/mcuboot/`; this document records the environment. Existing README/deployment/report changes were preserved. No commit, push or deployment was performed.

Phase 1C requires approval before adding the independent OTA-model comparison harness. The successful results here establish an executable reference and observed bootloader behavior; they do not yet validate agreement with OTA Verifier's recovery model.
