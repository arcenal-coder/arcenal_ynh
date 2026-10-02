#!/bin/bash

set -eu

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
manifest="$root_dir/manifest.toml"
common="$root_dir/scripts/_common.sh"

grep -Fq 'version = "0.21.0~ynh51"' "$manifest"
grep -Fq 'v0.21.0-arcenal33.tar.gz' "$manifest"
grep -Fq 'sha256 = "b8143f7dcae4716f5aec1777c76193cd04d86353fd92d445943fbf2798ebb9d5"' "$manifest"
grep -Fq 'echo "0.21.0-arcenal33"' "$common"
grep -Fq 'Environment=ARCENAL_RELEASE=0.21.0-arcenal33' "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_PACKAGE_VERSION=0.21.0~ynh51' "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_SOURCE_REVISION=0aad8846160de88230f2017e184999e21c75b98a' \
    "$root_dir/conf/arcenal.service"

if grep -Eq 'v0\.21\.0-arcenal(19|20)\.tar\.gz' "$manifest"; then
    printf 'Le manifeste référence encore la source précédente.\n' >&2
    exit 1
fi
