#!/bin/bash

# Utilitaires de compatibilité pour la configuration des modèles Hermes.

arcenal_model_get() {
    local config_file="$1"
    local key="$2"
    awk -v key="$key" '
        /^model:/ { in_model = 1; next }
        in_model && /^[^ ]/ { in_model = 0 }
        in_model && $1 == key ":" { print $2; exit }
    ' "$config_file"
}

arcenal_model_set() {
    local config_file="$1" key="$2" value="$3" owner="$4" group="$5"
    local temporary_file
    temporary_file="$(mktemp)"
    awk -v key="$key" -v value="$value" '
        /^model:/ { found = 1; in_model = 1; print; next }
        in_model && /^[^ ]/ && !updated { print "  " key ": " value; updated = 1; in_model = 0 }
        in_model && $1 == key ":" { print "  " key ": " value; updated = 1; next }
        { print }
        END {
            if (!found) print "model:\n  " key ": " value
            else if (!updated) print "  " key ": " value
        }
    ' "$config_file" > "$temporary_file"
    install -o "$owner" -g "$group" -m 600 "$temporary_file" "$config_file"
    rm -f "$temporary_file"
}

arcenal_model_migrate_legacy() {
    local config_file="$1" owner="$2" group="$3"
    grep -q '^provider:' "$config_file" || return 0
    local provider model temporary_file
    provider="$(awk '$1 == "provider:" { print $2; exit }' "$config_file")"
    model="$(awk '$1 == "model:" && NF > 1 { print $2; exit }' "$config_file")"
    [ -n "$provider" ] && [ -n "$model" ] || return 1
    temporary_file="$(mktemp)"
    awk '$1 != "provider:" && !($1 == "model:" && NF > 1)' "$config_file" > "$temporary_file"
    printf 'model:\n  provider: %s\n  default: %s\n' "$provider" "$model" >> "$temporary_file"
    install -o "$owner" -g "$group" -m 600 "$temporary_file" "$config_file"
    rm -f "$temporary_file"
}
