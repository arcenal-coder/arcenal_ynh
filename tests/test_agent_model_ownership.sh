#!/bin/bash

set -euo pipefail

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
manifest="$root_dir/manifest.toml"
panel="$root_dir/config_panel.toml"
install_script="$root_dir/scripts/install"

if grep -Eq '^    \[install\.(provider|model|api_key)\]' "$manifest"; then
    echo "Le paquet ne doit pas imposer de fournisseur ou modèle global." >&2
    exit 1
fi

if grep -Eq '^    \[main\.(model_settings|secrets)\]' "$panel"; then
    echo "Les fournisseurs doivent être administrés dans ARC." >&2
    exit 1
fi

if grep -Eq '^[[:space:]]*(provider|default):[[:space:]]*\$' "$install_script"; then
    echo "Une installation neuve ne doit pas écrire de route LLM globale." >&2
    exit 1
fi

grep -Fq 'terminal:' "$install_script"
grep -Fq 'arcenal_migrate_native_configuration' "$install_script"
