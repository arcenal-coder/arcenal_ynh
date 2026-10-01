#!/bin/bash

set -eu

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
upgrade_script="$root_dir/scripts/upgrade"
restore_script="$root_dir/scripts/restore"

assert_upgrade_repairs_dependencies() {
    grep -Fq 'source "$(dirname "$0")/_common.sh"' "$upgrade_script"
    grep -Fq 'ynh_setup_source --dest_dir="$install_dir" --full_replace' "$upgrade_script"
    grep -Fq 'arcenal_install_deps' "$upgrade_script"
    if ! grep -Fq 'arcenal_model_repair_gemini_auto' "$upgrade_script"; then
        printf 'La mise à niveau doit corriger la route Gemini historique.\n' >&2
        return 1
    fi
    repair_line="$(grep -n 'arcenal_model_repair_gemini_auto' "$upgrade_script" | cut -d: -f1)"
    native_line="$(grep -n '^arcenal_migrate_native_configuration$' "$upgrade_script" | cut -d: -f1)"
    if [ "$repair_line" -ge "$native_line" ]; then
        printf 'La route Gemini doit être corrigée avant la migration native.\n' >&2
        return 1
    fi

    if grep -Fq '"$install_dir/.local/bin/uv" sync' "$upgrade_script"; then
        printf 'La mise à niveau ne doit pas supposer que uv existe déjà.\n' >&2
        return 1
    fi
}

assert_core_only_restore_is_supported() {
    grep -Fq 'ynh_restore_file --origin_path="/var/www/$app/data" --not_mandatory' "$restore_script"
    grep -Fq 'source "$(dirname "$0")/_common.sh"' "$restore_script"
    grep -Fq 'arcenal_install_deps' "$restore_script"
    grep -Fq 'ynh_backup "/etc/systemd/system/$app.service" --not_mandatory' "$root_dir/scripts/backup"
    grep -Fq 'ynh_restore_file --origin_path="/etc/systemd/system/$app.service" --not_mandatory' "$restore_script"
    grep -Fq 'ynh_setup_source --dest_dir="$install_dir" --full_replace' "$restore_script"

    if grep -Fq '"$install_dir/.local/bin/uv" sync' "$restore_script"; then
        printf 'La restauration ne doit pas supposer que uv existe déjà.\n' >&2
        return 1
    fi
}

assert_restore_recreates_the_service_registry() {
    grep -Fq 'yunohost service add "$app"' "$restore_script"
    grep -Fq 'arcenal_secure_data_permissions' "$restore_script"
}

assert_upgrade_repairs_dependencies
assert_core_only_restore_is_supported
assert_restore_recreates_the_service_registry
