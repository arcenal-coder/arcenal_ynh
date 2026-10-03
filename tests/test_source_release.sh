#!/bin/bash

set -eu

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
manifest="$root_dir/manifest.toml"
common="$root_dir/scripts/_common.sh"

grep -Fq 'version = "0.21.0~ynh52"' "$manifest"
grep -Fq 'v0.21.0-arcenal35.tar.gz' "$manifest"
grep -Fq 'sha256 = "bf1d3b66ad770ccbf4903b0708c69ac670bd38f7ae042887cf8734376369a821"' "$manifest"
grep -Fq 'echo "0.21.0-arcenal35"' "$common"
grep -Fq 'Environment=ARCENAL_RELEASE=0.21.0-arcenal35' "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_PACKAGE_VERSION=0.21.0~ynh52' "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_SOURCE_REVISION=ff93c4c59f4307274163a264a94e44473b0ca2d0' \
    "$root_dir/conf/arcenal.service"

if grep -Eq 'v0\.21\.0-arcenal(19|20)\.tar\.gz' "$manifest"; then
    printf 'Le manifeste référence encore la source précédente.\n' >&2
    exit 1
fi
