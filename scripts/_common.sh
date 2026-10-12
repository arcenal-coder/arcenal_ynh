#!/bin/bash

# Le gestionnaire PM amont vérifie ses outils épinglés : aucun curl | sh.
hermes_build() {
    ynh_setup_source --dest_dir="$install_dir" --full_replace=1
    # Bookworm peut fournir Python 3.11.2, sans filtres tarfile. Le helper
    # YunoHost extrait d'abord le Python épinglé par Hermes avec le tar système.
    ynh_setup_source --source_id=python --dest_dir="$install_dir/.bootstrap-python"
    chown -R "$app:$app" "$install_dir"
    local bootstrap="$install_dir/.bootstrap-python/bin/python3"
    test -x "$bootstrap" || ynh_die "Le Python d'amorçage Hermes est absent."
    ynh_exec_as_app "$bootstrap" -c \
        'import inspect, tarfile; assert "filter" in inspect.signature(tarfile.TarFile.extractall).parameters'
    local environment="$install_dir/.runtime-$(date +%s)-$$"
    ynh_exec_as_app env HOME="$data_dir" HERMES_HOME="$data_dir" \
        HERMES_RUNTIME_DIR="$install_dir/.tools" PYTHONPATH="$install_dir" \
        "$bootstrap" -m pm.build_env --source "$install_dir" --out "$environment" \
        --extra web --extra pty --extra cron --extra mcp
    hermes_python="$environment/bin/python"
    ynh_app_setting_set --key=hermes_python --value="$hermes_python"
    local nodejs_version
    nodejs_version=$(ynh_app_setting_get --key=nodejs_version)
    hermes_node="/opt/node_n/n/versions/node/$nodejs_version/bin/node"
    test -x "$hermes_node" || ynh_die "Le runtime Node YunoHost est absent."
    ynh_app_setting_set --key=hermes_node --value="$hermes_node"
    ynh_exec_as_app env HOME="$data_dir" npm --prefix "$install_dir" ci \
        --workspace web --workspace ui-tui --include-workspace-root --include=dev
    ynh_exec_as_app env HOME="$data_dir" npm --prefix "$install_dir" run build --workspace web
    ynh_exec_as_app env HOME="$data_dir" npm --prefix "$install_dir" run build --workspace ui-tui
    ynh_exec_as_app "$bootstrap" "$install_dir/scripts/write_install_stamp.py" \
        --output "$install_dir/install-stamp.json" --update-mechanism external \
        --commit 0aa764feddf00aed631019763ef777d38faf4335 --source yunohost \
        --display-version "0.21.0~ynh66"
    chown -R "root:$app" "$install_dir"
    chmod -R u=rwX,g=rX,o= "$install_dir"
}

hermes_configure() {
    install -o root -g "$app" -m 0640 ../conf/configure.py "$install_dir/yunohost_configure.py"
    ynh_exec_as_app env HOME="$data_dir" HERMES_HOME="$data_dir" \
        PYTHONPATH="$install_dir" "$hermes_python" "$install_dir/yunohost_configure.py"
    chmod 700 "$data_dir"
    ynh_config_add_nginx
    hermes_admin_permission
    ynh_config_add_systemd --template=arcenal.service
    yunohost service add "$app" --description="Hermes Agent" --log="$data_dir/logs/gui.log"
}

hermes_admin_permission() {
    ynh_permission_url --permission=main --url="$domain$path" --auth_header=true
    # Réapplique aussi la frontière administrateur sur une permission héritée.
    local allowed
    allowed=$(yunohost user permission info "$app.main" --output-as json | python3 -c \
        'import json,sys; print(";".join(g for g in json.load(sys.stdin)["allowed"] if g != "admins"))')
    if [ -n "$allowed" ]; then
        ynh_permission_update --permission=main --remove="$allowed"
    fi
    ynh_permission_update --permission=main --add=admins
}

hermes_quiescent_data() {
    # Les enfants détachés peuvent terminer après systemctl stop. Attendre
    # leur sortie avant de refuser, sans tuer de processus utilisateur.
    local attempt status
    for attempt in {0..30}; do
        status=0
        pgrep -u "$app" >/dev/null || status=$?
        case "$status" in
            1) return 0 ;;
            0) [ "$attempt" -eq 30 ] || sleep 1 ;;
            *) ynh_die "Impossible de vérifier les processus de $app ; sauvegarde interrompue." ;;
        esac
    done
    # Les noms et PID suffisent au diagnostic ; aucun argument potentiellement secret.
    ps -u "$app" -o pid,ppid,stat,comm >&2
    ynh_die "Des processus de $app persistent après 30 secondes. Arrêtez les gateways actifs avant de réessayer."
}

hermes_retire_privileges() {
    # Ne vise que les deux artefacts privilégiés appartenant à ce paquet.
    rm -f "/etc/sudoers.d/$app-supervisor" /usr/local/sbin/arcenal-supervisor-helper
    for legacy in "${app}_control" "${app}_broker"; do
        if systemctl cat "$legacy.service" >/dev/null 2>&1; then
            ynh_config_remove_systemd "$legacy"
        fi
    done
    rm -f /usr/local/sbin/arcenal-privileged-broker /usr/local/sbin/arcenal-nginx-reload \
        /usr/local/sbin/arcenal-control-socket-ready
}

hermes_stop_legacy_services() {
    for legacy in "${app}_control" "${app}_broker"; do
        if systemctl cat "$legacy.service" >/dev/null 2>&1; then
            ynh_systemctl --service="$legacy" --action=stop
        fi
    done
}

hermes_start() {
    ynh_systemctl --service="$app" --action=start
    local attempt
    for attempt in {1..60}; do
        if curl --fail --silent "http://127.0.0.1:$port/" >/dev/null; then
            return 0
        fi
        sleep 2
    done
    ynh_die "Le dashboard Hermes n'est pas prêt après 120 secondes."
}
