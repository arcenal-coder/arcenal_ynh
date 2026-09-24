#!/bin/bash

set -eu

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
upgrade_script="$root_dir/scripts/upgrade"
restore_script="$root_dir/scripts/restore"

assert_upgrade_repairs_dependencies() {
    grep -Fq 'source "$(dirname "$0")/_common.sh"' "$upgrade_script"
    grep -Fq 'ynh_setup_source --dest_dir="$install_dir" --full_replace' "$upgrade_script"
    grep -Fq 'arcenal_install_deps' "$upgrade_script"

    if grep -Fq '"$install_dir/.local/bin/uv" sync' "$upgrade_script"; then
        printf 'La mise à niveau ne doit pas supposer que uv existe déjà.\n' >&2
        return 1
    fi
}

assert_core_only_restore_is_supported() {
    grep -Fq 'ynh_restore_file --origin_path="/var/www/$app/data" --not_mandatory' "$restore_script"
    grep -Fq 'source "$(dirname "$0")/_common.sh"' "$restore_script"
    grep -Fq 'arcenal_install_deps' "$restore_script"

    if grep -Fq '"$install_dir/.local/bin/uv" sync' "$restore_script"; then
        printf 'La restauration ne doit pas supposer que uv existe déjà.\n' >&2
        return 1
    fi
}

assert_upgrade_repairs_dependencies
assert_core_only_restore_is_supported
