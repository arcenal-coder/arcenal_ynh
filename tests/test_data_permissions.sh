#!/bin/bash

set -eu

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
common_script="$root_dir/scripts/_common.sh"

grep -Fq 'install -d -o root -g "$app" -m 0750 "/var/www/$app"' "$common_script"
grep -Fq 'install -d -o "$app" -g "$app" -m 0700 "$ARCENAL_DATA_DIR"' "$common_script"
grep -Fq 'chmod 0600 "$ARCENAL_DATA_DIR/$sensitive_file"' "$common_script"
grep -Fq 'install -d -o "$app" -g "$app" -m 0700 "$ARCENAL_DATA_DIR/arcenal"' "$common_script"
grep -Fq 'chmod 0600 "$ARCENAL_DATA_DIR/arcenal/config.json"' "$common_script"
grep -Fq -- "-name '*.db-wal'" "$common_script"
grep -Fq 'UMask=0077' "$root_dir/conf/arcenal.service"
grep -Fq 'UMask=0077' "$root_dir/conf/arcenal-control.service"
grep -Fq 'UMask=0077' "$root_dir/conf/arcenal-broker.service"
grep -Fq 'ExecStartPre=/bin/rm -f /run/__APP__-web/http.sock' \
    "$root_dir/conf/arcenal-control.service"
grep -Fq 'ExecStartPost=/usr/local/sbin/arcenal-control-socket-ready /run/__APP__-web/http.sock' \
    "$root_dir/conf/arcenal-control.service"
grep -Fq 'RuntimeDirectoryMode=0750' "$root_dir/conf/arcenal-control.service"
grep -Fq 'Environment=ARCENAL_HOME=__DATA_DIR__' "$root_dir/conf/arcenal.service"
grep -Fq 'arcenal_migrate_native_configuration' "$common_script"
grep -Fq 'env -u ARCENAL_CONFIG_BACKEND' "$common_script"

for script_name in config; do
    grep -Fq 'arcenal_secure_data_permissions' "$root_dir/scripts/$script_name"
done

for script_name in install upgrade restore; do
    grep -Fq 'arcenal_secure_base_permissions' "$root_dir/scripts/$script_name"
    grep -Fq 'arcenal_migrate_native_configuration' "$root_dir/scripts/$script_name"
done
