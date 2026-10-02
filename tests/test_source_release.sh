#!/bin/bash

set -eu

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
manifest="$root_dir/manifest.toml"
common="$root_dir/scripts/_common.sh"

grep -Fq 'version = "0.21.0~ynh48"' "$manifest"
grep -Fq 'v0.21.0-arcenal30.tar.gz' "$manifest"
grep -Fq 'sha256 = "0f1b5e88582d233d1d97bbd04c7b76c796e4dbcf2e50e91055aaf4bee4215bce"' "$manifest"
grep -Fq 'echo "0.21.0-arcenal30"' "$common"
grep -Fq 'Environment=ARCENAL_RELEASE=0.21.0-arcenal30' "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_PACKAGE_VERSION=0.21.0~ynh48' "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_SOURCE_REVISION=a7ddd9759112b3b7efee41439b23c9358645595a' \
    "$root_dir/conf/arcenal.service"

if grep -Eq 'v0\.21\.0-arcenal(19|20)\.tar\.gz' "$manifest"; then
    printf 'Le manifeste référence encore la source précédente.\n' >&2
    exit 1
fi
