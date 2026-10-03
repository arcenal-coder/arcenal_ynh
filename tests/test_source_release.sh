#!/bin/bash

set -eu

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
manifest="$root_dir/manifest.toml"
common="$root_dir/scripts/_common.sh"

grep -Fq 'version = "0.21.0~ynh61"' "$manifest"
grep -Fq 'v0.21.0-arcenal41.tar.gz' "$manifest"
grep -Fq 'sha256 = "a159b130f02726c04818d819f9376553378ce45e60d30d190eb48b9694088f82"' "$manifest"
grep -Fq 'echo "0.21.0-arcenal41"' "$common"
grep -Fq 'Environment=ARCENAL_RELEASE=0.21.0-arcenal41' "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_PACKAGE_VERSION=0.21.0~ynh61' "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_SOURCE_REVISION=668ca31afdb4fcf7dd9a05c392eabc1e526b905b' \
    "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_AUDIT_DIR=__DATA_DIR__/arcenal/audit' \
    "$root_dir/conf/arcenal.service"

if grep -Eq 'v0\.21\.0-arcenal(19|20)\.tar\.gz' "$manifest"; then
    printf 'Le manifeste référence encore la source précédente.\n' >&2
    exit 1
fi
