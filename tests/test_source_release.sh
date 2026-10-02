#!/bin/bash

set -eu

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
manifest="$root_dir/manifest.toml"
common="$root_dir/scripts/_common.sh"

grep -Fq 'version = "0.21.0~ynh50"' "$manifest"
grep -Fq 'v0.21.0-arcenal32.tar.gz' "$manifest"
grep -Fq 'sha256 = "ae22e12dec1e605922d77baad3e80ca9157f91a5c6071ff35697c786d057fcc5"' "$manifest"
grep -Fq 'echo "0.21.0-arcenal32"' "$common"
grep -Fq 'Environment=ARCENAL_RELEASE=0.21.0-arcenal32' "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_PACKAGE_VERSION=0.21.0~ynh50' "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_SOURCE_REVISION=a7ddd9759112b3b7efee41439b23c9358645595a' \
    "$root_dir/conf/arcenal.service"

if grep -Eq 'v0\.21\.0-arcenal(19|20)\.tar\.gz' "$manifest"; then
    printf 'Le manifeste référence encore la source précédente.\n' >&2
    exit 1
fi
