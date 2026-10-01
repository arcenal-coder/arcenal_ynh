#!/bin/bash

set -eu

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
manifest="$root_dir/manifest.toml"
common="$root_dir/scripts/_common.sh"

grep -Fq 'version = "0.21.0~ynh38"' "$manifest"
grep -Fq 'v0.21.0-arcenal21.tar.gz' "$manifest"
grep -Fq 'sha256 = "5ca954d678de17cb1debdcbfe4e9d153f86b150e9112fa963f3d1687b75951a6"' "$manifest"
grep -Fq 'echo "0.21.0-arcenal21"' "$common"
grep -Fq 'Environment=ARCENAL_RELEASE=0.21.0-arcenal21' "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_PACKAGE_VERSION=0.21.0~ynh38' "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_SOURCE_REVISION=09214e609e8c20e8f998f911166a82b23c322c76' \
    "$root_dir/conf/arcenal.service"

if grep -Eq 'v0\.21\.0-arcenal(19|20)\.tar\.gz' "$manifest"; then
    printf 'Le manifeste référence encore la source précédente.\n' >&2
    exit 1
fi
