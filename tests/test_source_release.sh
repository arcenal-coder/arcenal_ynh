#!/bin/bash

set -eu

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
manifest="$root_dir/manifest.toml"
common="$root_dir/scripts/_common.sh"

grep -Fq 'version = "0.21.0~ynh59"' "$manifest"
grep -Fq 'v0.21.0-arcenal39.tar.gz' "$manifest"
grep -Fq 'sha256 = "6ddf3f9024b231b9feb9addde13ca04929e5e7c589e97df4e8ce2fce01cc2452"' "$manifest"
grep -Fq 'echo "0.21.0-arcenal39"' "$common"
grep -Fq 'Environment=ARCENAL_RELEASE=0.21.0-arcenal39' "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_PACKAGE_VERSION=0.21.0~ynh59' "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_SOURCE_REVISION=998663ad5b08301f0db073c22d8ac1c7a8f6e766' \
    "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_AUDIT_DIR=__DATA_DIR__/arcenal/audit' \
    "$root_dir/conf/arcenal.service"

if grep -Eq 'v0\.21\.0-arcenal(19|20)\.tar\.gz' "$manifest"; then
    printf 'Le manifeste référence encore la source précédente.\n' >&2
    exit 1
fi
