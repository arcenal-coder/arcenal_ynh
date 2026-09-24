#!/bin/bash

set -eu

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
manifest="$root_dir/manifest.toml"
common="$root_dir/scripts/_common.sh"

grep -Fq 'version = "0.21.0~ynh31"' "$manifest"
grep -Fq 'v0.21.0-arcenal17.tar.gz' "$manifest"
grep -Fq 'sha256 = "624a1e8d20fb572dbe0063eea34f1e2bfcf25a0c85f0592e2a936825dcaf9e3e"' "$manifest"
grep -Fq 'echo "0.21.0-arcenal17"' "$common"

if grep -Fq 'v0.21.0-arcenal16.tar.gz' "$manifest"; then
    printf 'Le manifeste référence encore la source précédente.\n' >&2
    exit 1
fi
