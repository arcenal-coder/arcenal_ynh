#!/bin/bash

set -eu

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
manifest="$root_dir/manifest.toml"
common="$root_dir/scripts/_common.sh"

grep -Fq 'version = "0.21.0~ynh46"' "$manifest"
grep -Fq 'v0.21.0-arcenal28.tar.gz' "$manifest"
grep -Fq 'sha256 = "25196f812b0f9d928bbacc9d65dd4a51947fa441df473099d37ccc489fa00480"' "$manifest"
grep -Fq 'echo "0.21.0-arcenal28"' "$common"
grep -Fq 'Environment=ARCENAL_RELEASE=0.21.0-arcenal28' "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_PACKAGE_VERSION=0.21.0~ynh46' "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_SOURCE_REVISION=f5166ac3c32389c726aae61b0741dc20e5af376b' \
    "$root_dir/conf/arcenal.service"

if grep -Eq 'v0\.21\.0-arcenal(19|20)\.tar\.gz' "$manifest"; then
    printf 'Le manifeste référence encore la source précédente.\n' >&2
    exit 1
fi
