#!/bin/bash

set -eu

source "$(dirname "$0")/../scripts/model_config.sh"

temporary_dir="$(mktemp -d)"
trap 'rm -rf "$temporary_dir"' EXIT
config_file="$temporary_dir/config.yaml"
current_owner="$(id -un)"
current_group="$(id -gn)"

cat > "$config_file" <<'EOF'
provider: openrouter
model: openrouter/auto
terminal:
  backend: local
EOF

arcenal_model_migrate_legacy "$config_file" "$current_owner" "$current_group"
test "$(arcenal_model_get "$config_file" provider)" = "openrouter"
test "$(arcenal_model_get "$config_file" default)" = "openrouter/auto"
! grep -q '^provider:' "$config_file"

arcenal_model_set "$config_file" default "anthropic/claude-sonnet-4" "$current_owner" "$current_group"
test "$(arcenal_model_get "$config_file" default)" = "anthropic/claude-sonnet-4"
test "$(grep -c '^model:' "$config_file")" = "1"

unchanged="$(cksum "$config_file")"
arcenal_model_migrate_legacy "$config_file" "$current_owner" "$current_group"
test "$(cksum "$config_file")" = "$unchanged"

printf 'terminal:\n  backend: local\n' > "$config_file"
arcenal_model_set "$config_file" provider "openai" "$current_owner" "$current_group"
test "$(arcenal_model_get "$config_file" provider)" = "openai"
test "$(grep -c '^model:' "$config_file")" = "1"

printf 'provider: openrouter\n' > "$config_file"
if arcenal_model_migrate_legacy "$config_file" "$current_owner" "$current_group"; then
    echo "Une configuration historique incomplète aurait dû être rejetée." >&2
    exit 1
fi
