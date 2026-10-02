#!/bin/bash

set -eu

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
manifest="$root_dir/manifest.toml"
common="$root_dir/scripts/_common.sh"

grep -Fq 'version = "0.21.0~ynh49"' "$manifest"
grep -Fq 'v0.21.0-arcenal31.tar.gz' "$manifest"
grep -Fq 'sha256 = "69a76c69452a9a883c0b89235917590426e0d2e37a7dd84cbceb12b58ad81790"' "$manifest"
grep -Fq 'echo "0.21.0-arcenal31"' "$common"
grep -Fq 'Environment=ARCENAL_RELEASE=0.21.0-arcenal31' "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_PACKAGE_VERSION=0.21.0~ynh49' "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_SOURCE_REVISION=a7ddd9759112b3b7efee41439b23c9358645595a' \
    "$root_dir/conf/arcenal.service"

if grep -Eq 'v0\.21\.0-arcenal(19|20)\.tar\.gz' "$manifest"; then
    printf 'Le manifeste référence encore la source précédente.\n' >&2
    exit 1
fi
