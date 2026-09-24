#!/bin/bash

set -eu

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
service_file="$root_dir/conf/arcenal.service"
common_file="$root_dir/scripts/_common.sh"

assert_node_runtime_is_exposed() {
    grep -Fq 'Environment="PATH=__PATH_WITH_NODEJS__"' "$service_file"
    grep -Fq 'Environment=HERMES_TUI_DIR=__INSTALL_DIR__/ui-tui' "$service_file"
}

assert_tui_is_built_before_startup() {
    grep -Fq -- '--workspace ui-tui' "$common_file"
    grep -Fq 'run build --workspace ui-tui' "$common_file"

    for script_name in install upgrade restore; do
        grep -Fq 'arcenal_build_interfaces "$web_base"' \
            "$root_dir/scripts/$script_name"
    done
}

assert_node_runtime_is_exposed
assert_tui_is_built_before_startup
