#!/usr/bin/env bash
# Run in WSL/Linux. Bootutil source is never edited by this script.
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
ref="$root/.mcuboot-reference/upstream"
out="${MCUBOOT_EVIDENCE_DIR:-$root/validation/mcuboot/evidence}"
pin=6d3b3d2c38ab20c242e5b9abb04d050086383eb2
export PATH="$HOME/.cargo/bin:$PATH"
mkdir -p "$out"
exec > >(tee "$out/build.log") 2>&1
trap 'echo "FAILED line=$LINENO exit=$?"' ERR
if [ ! -d "$ref/.git" ]; then
    git clone --no-checkout https://github.com/mcu-tools/mcuboot.git "$ref"
    git -C "$ref" checkout --detach "$pin"
fi
test "$(git -C "$ref" rev-parse HEAD)" = "$pin"
# Only mbedTLS is needed by the chosen RSA configuration.
git -C "$ref" submodule update --init --recursive ext/mbedtls
cd "$ref/sim"
rustc +1.90.0 --version
cargo +1.90.0 --version
gcc --version
uname -a
git rev-parse HEAD
git submodule status --recursive
test -f "$root/validation/mcuboot/Cargo.lock"
cp "$root/validation/mcuboot/Cargo.lock" ../Cargo.lock
sha256sum ../Cargo.lock
cargo +1.90.0 test --locked --no-default-features --features sig-rsa,validate-primary-slot --no-run -vv
echo 'BUILD_COMPLETE'
