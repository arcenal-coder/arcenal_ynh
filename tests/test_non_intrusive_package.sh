#!/bin/bash

set -euo pipefail

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
package_files=("$root_dir/manifest.toml" "$root_dir/scripts" "$root_dir/conf")

assert_supported_yunohost_boundaries() {
    grep -Fq 'packaging_format = 2' "$root_dir/manifest.toml"
    grep -Fq 'helpers_version = "2.1"' "$root_dir/manifest.toml"
    grep -Fq 'ynh_config_add_nginx' "$root_dir/scripts/install"
    grep -Fq 'ynh_config_add_systemd' "$root_dir/scripts/install"
    grep -Fq 'ynh_backup "/var/www/$app/data"' "$root_dir/scripts/backup"
}

assert_no_yunohost_core_patch() {
    local forbidden
    for forbidden in \
        '/etc/yunohost' \
        '/etc/nginx/nginx.conf' \
        '/etc/ssowat' \
        'yunohost app catalog' \
        'apt install'; do
        if grep -R -Fq --exclude='test_non_intrusive_package.sh' "$forbidden" "${package_files[@]}"; then
            printf 'Modification globale interdite détectée : %s\n' "$forbidden" >&2
            return 1
        fi
    done
    if grep -R -E '(sed -i|cp |install |rm ).*/usr/share/yunohost' "$root_dir/scripts" "$root_dir/conf"; then
        echo "Le paquet ne doit pas écrire dans le cœur YunoHost." >&2
        return 1
    fi
}

assert_removal_is_app_scoped() {
    grep -Fq 'yunohost service remove "$app"' "$root_dir/scripts/remove"
    grep -Fq 'ynh_config_remove_systemd --service="$app"' "$root_dir/scripts/remove"
    grep -Fq 'ynh_config_remove_nginx' "$root_dir/scripts/remove"
    grep -Fq 'ynh_system_user_delete --username="${app}_control"' "$root_dir/scripts/remove"
    if grep -Eq 'rm (-[^ ]* )*(-r|-R)|rm -rf|rm -fr' "$root_dir/scripts/remove"; then
        echo "La désinstallation ne doit pas supprimer récursivement des chemins système." >&2
        return 1
    fi
}

assert_supported_yunohost_boundaries
assert_no_yunohost_core_patch
assert_removal_is_app_scoped
