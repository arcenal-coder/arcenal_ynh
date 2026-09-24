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
