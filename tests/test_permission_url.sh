#!/bin/bash

set -eu

root_dir="$(cd "$(dirname "$0")/.." && pwd)"

assert_relative_permission_url() {
    script_path="$1"

    grep -Fq 'ynh_permission_url --permission="main" --url="/" --auth_header=true' "$script_path"
}

assert_no_absolute_permission_url() {
    script_path="$1"

    if grep -Fq 'ynh_permission_url --permission="main" --url="$domain$path"' "$script_path"; then
        printf 'URL absolue interdite dans %s\n' "$script_path" >&2
        return 1
    fi
}

assert_relative_permission_url "$root_dir/scripts/install"
assert_relative_permission_url "$root_dir/scripts/upgrade"
assert_no_absolute_permission_url "$root_dir/scripts/install"
assert_no_absolute_permission_url "$root_dir/scripts/upgrade"

# L'administration reste réservée aux administrateurs, tandis que le wiki
# n'ouvre que ses routes de lecture aux comptes salariés.
grep -Fq 'main.allowed = "admins"' "$root_dir/manifest.toml"
grep -Fq 'wiki.url = "/wiki"' "$root_dir/manifest.toml"
grep -Fq 'wiki.allowed = "all_users"' "$root_dir/manifest.toml"
grep -Fq '"/api/plugins/arcenal-supervisor/knowledge/wiki/document"' "$root_dir/manifest.toml"

if grep -Fq '[install.init_main_permission]' "$root_dir/manifest.toml"; then
    printf 'La permission principale ne doit pas être modifiable à l’installation.\n' >&2
    exit 1
fi
