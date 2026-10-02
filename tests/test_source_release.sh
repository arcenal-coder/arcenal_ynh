#!/bin/bash

set -eu

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
manifest="$root_dir/manifest.toml"
common="$root_dir/scripts/_common.sh"

grep -Fq 'version = "0.21.0~ynh43"' "$manifest"
grep -Fq 'v0.21.0-arcenal25.tar.gz' "$manifest"
grep -Fq 'sha256 = "7a460f2b850815389e7e3efb7bf74c5d619cb0dadfb5ee38352e26865ccc7c28"' "$manifest"
grep -Fq 'echo "0.21.0-arcenal25"' "$common"
grep -Fq 'Environment=ARCENAL_RELEASE=0.21.0-arcenal25' "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_PACKAGE_VERSION=0.21.0~ynh43' "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_SOURCE_REVISION=3e97eed68bb882a56f0450d52250553a5b1f8da2' \
    "$root_dir/conf/arcenal.service"

if grep -Eq 'v0\.21\.0-arcenal(19|20)\.tar\.gz' "$manifest"; then
    printf 'Le manifeste référence encore la source précédente.\n' >&2
    exit 1
fi
