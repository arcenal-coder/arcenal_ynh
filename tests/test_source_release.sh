#!/bin/bash

set -eu

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
manifest="$root_dir/manifest.toml"
common="$root_dir/scripts/_common.sh"

grep -Fq 'version = "0.21.0~ynh54"' "$manifest"
grep -Fq 'v0.21.0-arcenal36.tar.gz' "$manifest"
grep -Fq 'sha256 = "6e533aa82f518a5e7fd20755fb761e7c34a63a857851897cad61a8269755bc74"' "$manifest"
grep -Fq 'echo "0.21.0-arcenal36"' "$common"
grep -Fq 'Environment=ARCENAL_RELEASE=0.21.0-arcenal36' "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_PACKAGE_VERSION=0.21.0~ynh54' "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_SOURCE_REVISION=4b7acf426fda42fd8576dbc764dd2360b6f3502a' \
    "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_AUDIT_DIR=__DATA_DIR__/arcenal/audit' \
    "$root_dir/conf/arcenal.service"

if grep -Eq 'v0\.21\.0-arcenal(19|20)\.tar\.gz' "$manifest"; then
    printf 'Le manifeste référence encore la source précédente.\n' >&2
    exit 1
fi
