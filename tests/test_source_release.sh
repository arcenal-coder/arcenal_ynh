#!/bin/bash

set -eu

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
manifest="$root_dir/manifest.toml"
common="$root_dir/scripts/_common.sh"

grep -Fq 'version = "0.21.0~ynh60"' "$manifest"
grep -Fq 'v0.21.0-arcenal40.tar.gz' "$manifest"
grep -Fq 'sha256 = "73cd45fd01d8e88c4c7a42cf692abefb8f4420d61cf632f7ea6ce09ef2285ce5"' "$manifest"
grep -Fq 'echo "0.21.0-arcenal40"' "$common"
grep -Fq 'Environment=ARCENAL_RELEASE=0.21.0-arcenal40' "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_PACKAGE_VERSION=0.21.0~ynh60' "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_SOURCE_REVISION=e83340877fee025a937c66eccbe15f0bbe53e282' \
    "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_AUDIT_DIR=__DATA_DIR__/arcenal/audit' \
    "$root_dir/conf/arcenal.service"

if grep -Eq 'v0\.21\.0-arcenal(19|20)\.tar\.gz' "$manifest"; then
    printf 'Le manifeste référence encore la source précédente.\n' >&2
    exit 1
fi
