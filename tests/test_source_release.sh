#!/bin/bash

set -eu

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
manifest="$root_dir/manifest.toml"
common="$root_dir/scripts/_common.sh"

grep -Fq 'version = "0.21.0~ynh45"' "$manifest"
grep -Fq 'v0.21.0-arcenal27.tar.gz' "$manifest"
grep -Fq 'sha256 = "cd38de51db17798b71a3547cd9f4a6e2ecb75ab2b164c89d4303fb6bfe908440"' "$manifest"
grep -Fq 'echo "0.21.0-arcenal27"' "$common"
grep -Fq 'Environment=ARCENAL_RELEASE=0.21.0-arcenal27' "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_PACKAGE_VERSION=0.21.0~ynh45' "$root_dir/conf/arcenal.service"
grep -Fq 'Environment=ARCENAL_SOURCE_REVISION=d120a8d397ba6f990a6195488d46e0ee07b5b319' \
    "$root_dir/conf/arcenal.service"

if grep -Eq 'v0\.21\.0-arcenal(19|20)\.tar\.gz' "$manifest"; then
    printf 'Le manifeste référence encore la source précédente.\n' >&2
    exit 1
fi
