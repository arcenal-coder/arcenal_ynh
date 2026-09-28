#!/bin/bash

set -eu

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
manifest="$root_dir/manifest.toml"
common="$root_dir/scripts/_common.sh"

grep -Fq 'version = "0.21.0~ynh34"' "$manifest"
grep -Fq 'v0.21.0-arcenal19.tar.gz' "$manifest"
grep -Fq 'sha256 = "e53215dfce09f138f09322d10a86b4cae46de13917335ee96ebcbd597234df99"' "$manifest"
grep -Fq 'echo "0.21.0-arcenal19"' "$common"

if grep -Fq 'v0.21.0-arcenal18.tar.gz' "$manifest"; then
    printf 'Le manifeste référence encore la source précédente.\n' >&2
    exit 1
fi
