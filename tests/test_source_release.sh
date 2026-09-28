#!/bin/bash

set -eu

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
manifest="$root_dir/manifest.toml"
common="$root_dir/scripts/_common.sh"

grep -Fq 'version = "0.21.0~ynh35"' "$manifest"
grep -Fq 'v0.21.0-arcenal20.tar.gz' "$manifest"
grep -Fq 'sha256 = "c108196870558151d3a5936300628a40e3cff1f4d85c1a5d879dd745d7c3bd32"' "$manifest"
grep -Fq 'echo "0.21.0-arcenal20"' "$common"

if grep -Fq 'v0.21.0-arcenal19.tar.gz' "$manifest"; then
    printf 'Le manifeste référence encore la source précédente.\n' >&2
    exit 1
fi
