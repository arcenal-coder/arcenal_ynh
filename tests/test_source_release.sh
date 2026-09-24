#!/bin/bash

set -eu

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
manifest="$root_dir/manifest.toml"
common="$root_dir/scripts/_common.sh"

grep -Fq 'version = "0.21.0~ynh30"' "$manifest"
grep -Fq 'v0.21.0-arcenal16.tar.gz' "$manifest"
grep -Fq 'sha256 = "3c26f24d517f056b2a196ff792139113a0e715108561ac60b6ce351a6c4c388e"' "$manifest"
grep -Fq 'echo "0.21.0-arcenal16"' "$common"

if grep -Fq 'v0.21.0-arcenal15.tar.gz' "$manifest"; then
    printf 'Le manifeste référence encore la source précédente.\n' >&2
    exit 1
fi
