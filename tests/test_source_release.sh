#!/bin/bash

set -eu

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
manifest="$root_dir/manifest.toml"
common="$root_dir/scripts/_common.sh"

grep -Fq 'version = "0.21.0~ynh55"' "$manifest"
grep -Fq 'v0.21.0-arcenal37.tar.gz' "$manifest"
grep -Fq 'sha256 = "833cbd933d2d705fbe028046a3cbf794950ac2acc84bee76d0c642a4e3282026"' "$manifest"
grep -Fq 'echo "0.21.0-arcenal37"' "$common"
grep -Fq 'Environment=ARCENAL_RELEASE=0.21.0-arcenal37' "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_PACKAGE_VERSION=0.21.0~ynh55' "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_SOURCE_REVISION=9ced30207a4d410b41ec1d6e9c3375c52b171a0f' \
    "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_AUDIT_DIR=__DATA_DIR__/arcenal/audit' \
    "$root_dir/conf/arcenal.service"

if grep -Eq 'v0\.21\.0-arcenal(19|20)\.tar\.gz' "$manifest"; then
    printf 'Le manifeste référence encore la source précédente.\n' >&2
    exit 1
fi
