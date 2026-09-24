#!/bin/bash

set -euo pipefail

helper="$(dirname "$0")/../conf/arcenal-supervisor-helper"

grep -Fq 'yunohost app list --output-as json' "$helper"
grep -Fq 'yunohost service status --output-as json' "$helper"
grep -Fq 'yunohost --version' "$helper"
if grep -Eq 'eval|bash -c|sh -c' "$helper"; then
    echo "Le pont YunoHost ne doit jamais exécuter une commande arbitraire." >&2
    exit 1
fi
