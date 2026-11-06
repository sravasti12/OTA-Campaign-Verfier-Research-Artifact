#!/usr/bin/env bash
# Actual C bootutil execution via upstream Rust tests. No OTA model comparison.
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
ref="$root/.mcuboot-reference/upstream"
out="${MCUBOOT_EVIDENCE_DIR:-$root/validation/mcuboot/evidence}"
export PATH="$HOME/.cargo/bin:$PATH"
mkdir -p "$out"
cd "$ref"
test "$(git rev-parse HEAD)" = 6d3b3d2c38ab20c242e5b9abb04d050086383eb2
cmp Cargo.lock "$root/validation/mcuboot/Cargo.lock"
git -c core.autocrlf=true diff --quiet -- boot/bootutil sim/mcuboot-sys
# Preserve upstream tests as a separate, uninstrumented execution first.
git -c core.autocrlf=true diff --quiet -- sim/src/image.rs
for name in basic_revert norevert bad_secondary_slot; do
    RUST_LOG=info cargo +1.90.0 test --locked --no-default-features \
        --features sig-rsa,validate-primary-slot --test core "$name" -- \
        --exact --nocapture --test-threads=1 2>&1 | tee "$out/upstream-$name.log"
    grep -q 'test result: ok. 1 passed; 0 failed' "$out/upstream-$name.log"
done
cp "$root/validation/mcuboot/ota_reference.rs" sim/src/ota_reference.rs
# Restore only this test-module addition, even when compilation/tests fail.
cleanup() {
    git show HEAD:sim/src/image.rs > sim/src/image.rs
    rm -f sim/src/ota_reference.rs
}
trap cleanup EXIT
printf '\n#[cfg(test)]\n#[path = "ota_reference.rs"]\nmod ota_reference;\n' >> sim/src/image.rs
git -c core.autocrlf=true diff -- sim/src/image.rs > "$out/instrumentation.patch"
cargo +1.90.0 test --locked --no-default-features \
    --features sig-rsa,validate-primary-slot --lib ota_reference:: -- \
    --nocapture --test-threads=1 2>&1 | tee "$out/observations.log"
grep -q 'test result: ok. 2 passed; 0 failed' "$out/observations.log"
{
    date -u --iso-8601=seconds
    rustc +1.90.0 -Vv
    cargo +1.90.0 --version
    gcc --version
    cat /etc/os-release
    uname -a
    dpkg-query -W build-essential gcc gcc-13 libc6-dev pkg-config
    git rev-parse HEAD
    git submodule status --recursive
    sha256sum Cargo.lock "$root/validation/mcuboot/ota_reference.rs"
    find target/debug/build -name libbootutil.a -exec sha256sum {} \;
    find target/debug/deps -maxdepth 1 -type f -executable -name 'bootsim-*' ! -name '*.d' -exec sha256sum {} \;
    find target/debug/build -name libbootutil.a -exec nm -g --defined-only {} \; | grep -E 'context_boot_go|bootutil_get_caps|boot_image_validate|swap_run'
} > "$out/environment.txt"
git -c core.autocrlf=true diff -- Cargo.lock > "$out/cargo-lock.patch"
echo 'REFERENCE_COMPLETE: 3 upstream tests and 2 observation tests passed'
