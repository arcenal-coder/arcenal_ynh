#!/bin/bash

set -euo pipefail

broker="$(dirname "$0")/../conf/arcenal-privileged-broker"

grep -Fq '"/usr/bin/yunohost", "app", "list", "--output-as", "json"' "$broker"
grep -Fq '"/usr/bin/yunohost", "service", "status", "--output-as", "json"' "$broker"
grep -Fq '"/usr/bin/yunohost", "domain", "list", "--output-as", "json"' "$broker"
grep -Fq '"/usr/bin/yunohost", "backup", "list", "--output-as", "json"' "$broker"
grep -Fq '"/usr/bin/yunohost", "user", "list", "--output-as", "json"' "$broker"
grep -Fq '"/usr/bin/yunohost", "diagnosis", "show", "--issues", "--output-as", "json"' "$broker"
grep -Fq '"/usr/bin/yunohost", "app", "list", "--upgradable", "--output-as", "json"' "$broker"
grep -Fq '"/usr/bin/journalctl", "--priority=err"' "$broker"
grep -Fq '"yunohost.certificate.read"' "$broker"
grep -Fq '"/usr/bin/yunohost", "--version"' "$broker"
grep -Fq 'Action interdite sur le canal de lecture.' "$broker"
if grep -Eq 'eval|bash -c|sh -c' "$broker"; then
    echo "Le pont YunoHost ne doit jamais exécuter une commande arbitraire." >&2
    exit 1
fi

grep -Fq 'NoNewPrivileges=true' "$(dirname "$0")/../conf/arcenal.service"
grep -Fq 'HERMES_TUI_TOOLSETS=arcenal-admin' "$(dirname "$0")/../conf/arcenal.service"
grep -Fq 'Group=www-data' "$(dirname "$0")/../conf/arcenal-control.service"
grep -Fq 'SupplementaryGroups=__APP__ __APP___control' "$(dirname "$0")/../conf/arcenal-control.service"
grep -Fq 'UMask=0077' "$(dirname "$0")/../conf/arcenal-control.service"
grep -Fq 'StateDirectoryMode=0700' "$(dirname "$0")/../conf/arcenal-control.service"
grep -Fq 'ARCENAL_APPROVAL_DB=/run/arcenal-web/approvals.sqlite3' "$(dirname "$0")/../conf/arcenal-control.service"
grep -Fq 'ExecStartPost=/bin/chmod 0660 /run/__APP__-web/http.sock' \
    "$(dirname "$0")/../conf/arcenal-control.service"
grep -Fq '/run/arcenal-web/http.sock' "$(dirname "$0")/../conf/nginx.conf"
grep -Fq 'proxy_set_header Remote-User $http_ynh_user;' "$(dirname "$0")/../conf/nginx.conf"
! grep -Fq '$http_remote_user' "$(dirname "$0")/../conf/nginx.conf"
test ! -e "$(dirname "$0")/../conf/arcenal-supervisor-sudoers"

if grep -Eq 'groupadd|groupdel|usermod|gpasswd' "$(dirname "$0")/../scripts/_common.sh" \
    "$(dirname "$0")/../scripts/remove"; then
    echo "Le paquet ne doit pas modifier les groupes d’un service global." >&2
    exit 1
fi
