#!/bin/bash

set -eu

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
manifest="$root_dir/manifest.toml"
common="$root_dir/scripts/_common.sh"

grep -Fq 'version = "0.21.0~ynh62"' "$manifest"
grep -Fq 'v0.21.0-arcenal42.tar.gz' "$manifest"
grep -Fq 'sha256 = "b6ed4238a3fdc09f73e128bdab04daebddf9ffc75288c8ad0b94439cb0aa42d3"' "$manifest"
grep -Fq 'echo "0.21.0-arcenal42"' "$common"
grep -Fq 'Environment=ARCENAL_RELEASE=0.21.0-arcenal42' "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_PACKAGE_VERSION=0.21.0~ynh62' "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_SOURCE_REVISION=097af60144b99d5785fe45743de92614a19f378e' \
    "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_AUDIT_DIR=__DATA_DIR__/arcenal/audit' \
    "$root_dir/conf/arcenal.service"

if grep -Eq 'v0\.21\.0-arcenal(19|20)\.tar\.gz' "$manifest"; then
    printf 'Le manifeste référence encore la source précédente.\n' >&2
    exit 1
fi
