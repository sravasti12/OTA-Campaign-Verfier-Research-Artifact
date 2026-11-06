#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
ref="$root/.mcuboot-reference/upstream"
out="${MCUBOOT_EVIDENCE_DIR:-$root/validation/mcuboot/differential_evidence}"
export PATH="$HOME/.cargo/bin:$PATH"
mkdir -p "$out"
exec > >(tee "$out/reference-command.log") 2>&1
cd "$ref"
test "$(git rev-parse HEAD)" = 6d3b3d2c38ab20c242e5b9abb04d050086383eb2
test "$(git -C ext/mbedtls rev-parse HEAD)" = 2ca6c285a0dd3f33982dd57299012dacab1ff206
cmp Cargo.lock "$root/validation/mcuboot/Cargo.lock"
git -c core.autocrlf=true diff --quiet -- boot/bootutil sim/mcuboot-sys sim/src/image.rs
test ! -e sim/src/ota_differential.rs
cp "$root/validation/mcuboot/ota_differential.rs" sim/src/ota_differential.rs
cleanup() {
    git show HEAD:sim/src/image.rs > sim/src/image.rs
    rm -f sim/src/ota_differential.rs
}
trap cleanup EXIT
printf '\n#[cfg(test)]\n#[path = "ota_differential.rs"]\nmod ota_differential;\n' >> sim/src/image.rs
git -c core.autocrlf=true diff -- sim/src/image.rs > "$out/instrumentation.patch"
echo 'COMMAND cargo +1.90.0 test --locked --no-default-features --features sig-rsa,validate-primary-slot --lib ota_differential:: -- --nocapture --test-threads=1'
cargo +1.90.0 test --locked --no-default-features --features sig-rsa,validate-primary-slot \
    --lib ota_differential:: -- --nocapture --test-threads=1 2>&1 | tee "$out/reference.log"
grep -q 'test result: ok. 1 passed; 0 failed' "$out/reference.log"
{
    date -u --iso-8601=seconds
    git rev-parse HEAD
    rustc +1.90.0 -Vv
    gcc --version
    git submodule status --recursive ext/mbedtls
    sha256sum Cargo.lock "$root/validation/mcuboot/ota_differential.rs"
    find target/debug/build -name libbootutil.a -exec sha256sum {} \;
} > "$out/environment.txt"
