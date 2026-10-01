#!/bin/bash

set -eu

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
config_script="$root_dir/scripts/config"

grep -Fq 'grep -v "^${provider_env}_API_KEY="' "$config_script"
grep -Fq 'install -o "$app" -g "$app" -m 0600' "$config_script"
grep -Fq 'getter__api_key' "$config_script"
grep -Fq 'validate__provider' "$config_script"
grep -Fq "\$'\\r'" "$config_script"

if grep -Fq 'printf '\''%s_API_KEY=%s\n'\'' "$provider_env" "$api_key" > "$env_file"' "$config_script"; then
    printf 'La rotation ne doit pas écraser les secrets des autres fournisseurs.\n' >&2
    exit 1
fi
