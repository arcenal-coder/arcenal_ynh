#!/bin/bash

set -eu

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
manifest="$root_dir/manifest.toml"
common="$root_dir/scripts/_common.sh"

grep -Fq 'version = "0.21.0~ynh32"' "$manifest"
grep -Fq 'v0.21.0-arcenal18.tar.gz' "$manifest"
grep -Fq 'sha256 = "55c0f1aaa3156002febceba8b01b91c82683717d040ec99ae9d40ac87fa5b779"' "$manifest"
grep -Fq 'echo "0.21.0-arcenal18"' "$common"

if grep -Fq 'v0.21.0-arcenal17.tar.gz' "$manifest"; then
    printf 'Le manifeste référence encore la source précédente.\n' >&2
    exit 1
fi
