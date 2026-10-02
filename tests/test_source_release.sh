#!/bin/bash

set -eu

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
manifest="$root_dir/manifest.toml"
common="$root_dir/scripts/_common.sh"

grep -Fq 'version = "0.21.0~ynh44"' "$manifest"
grep -Fq 'v0.21.0-arcenal26.tar.gz' "$manifest"
grep -Fq 'sha256 = "c97a2e9b9fa52a43c27647d54a696186e43731f62f743abe5adfcde55919d5f1"' "$manifest"
grep -Fq 'echo "0.21.0-arcenal26"' "$common"
grep -Fq 'Environment=ARCENAL_RELEASE=0.21.0-arcenal26' "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_PACKAGE_VERSION=0.21.0~ynh44' "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_SOURCE_REVISION=f396975074fad49cfc068781a6422b530ece5c00' \
    "$root_dir/conf/arcenal.service"

if grep -Eq 'v0\.21\.0-arcenal(19|20)\.tar\.gz' "$manifest"; then
    printf 'Le manifeste référence encore la source précédente.\n' >&2
    exit 1
fi
