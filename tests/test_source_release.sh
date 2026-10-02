#!/bin/bash

set -eu

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
manifest="$root_dir/manifest.toml"
common="$root_dir/scripts/_common.sh"

grep -Fq 'version = "0.21.0~ynh47"' "$manifest"
grep -Fq 'v0.21.0-arcenal29.tar.gz' "$manifest"
grep -Fq 'sha256 = "0ddfe1ae82959a6c86fb70041998e24ce7ea848291329f3ae799a112d4a6df46"' "$manifest"
grep -Fq 'echo "0.21.0-arcenal29"' "$common"
grep -Fq 'Environment=ARCENAL_RELEASE=0.21.0-arcenal29' "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_PACKAGE_VERSION=0.21.0~ynh47' "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_SOURCE_REVISION=a7ddd9759112b3b7efee41439b23c9358645595a' \
    "$root_dir/conf/arcenal.service"

if grep -Eq 'v0\.21\.0-arcenal(19|20)\.tar\.gz' "$manifest"; then
    printf 'Le manifeste référence encore la source précédente.\n' >&2
    exit 1
fi
