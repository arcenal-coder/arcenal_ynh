#!/bin/bash

# Fonctions communes du paquet YunoHost ARCenal Agent.
# Les helpers du packaging v2 sont chargés automatiquement.

readonly ARCENAL_INSTALL_DIR="/var/www/arcenal/app"
readonly ARCENAL_DATA_DIR="/var/www/arcenal/data"     # ARCENAL_HOME ; compatibilité HERMES_HOME transitoire
readonly ARCENAL_SERVICE_NAME="arcenal"

# Retourne la version figée de l'archive source ARCenal Agent.
# Le manifeste épingle aussi son empreinte afin de garantir la reproductibilité.
arcenal_get_source_version() {
    echo "0.21.0-arcenal27"
}

arcenal_install_source() {
    # La source est déclarée dans manifest.toml, puis extraite dans ce dossier.
    ynh_setup_source --dest_dir="$ARCENAL_INSTALL_DIR"
}

arcenal_install_deps() {
    # Installe uv dans le dossier applicatif, entièrement sous l'utilisateur app.
    if [ ! -x "$ARCENAL_INSTALL_DIR/.local/bin/uv" ]; then
        ynh_exec_as_app env \
            HOME="$ARCENAL_INSTALL_DIR" \
            UV_INSTALL_DIR="$ARCENAL_INSTALL_DIR/.local/bin" \
            sh -c 'curl -LsSf https://astral.sh/uv/0.12.9/install.sh | sh'
    fi
    # Crée l'environnement Python et installe les dépendances verrouillées.
    ynh_exec_as_app env \
        HOME="$ARCENAL_INSTALL_DIR" \
        UV_PYTHON_INSTALL_DIR="$ARCENAL_INSTALL_DIR/.uv/python" \
        "$ARCENAL_INSTALL_DIR/.local/bin/uv" sync \
            --directory "$ARCENAL_INSTALL_DIR" --python 3.11 --no-dev
}

arcenal_build_interfaces() {
    local web_base="$1"

    # Le chat doit être prêt avant le démarrage : aucun téléchargement npm
    # ne doit dépendre de la première connexion d'un administrateur.
    ynh_exec_as_app env HOME="$ARCENAL_INSTALL_DIR" \
        npm --prefix "$ARCENAL_INSTALL_DIR" ci \
            --workspace web --workspace ui-tui --include-workspace-root --include=dev
    ynh_exec_as_app env HOME="$ARCENAL_INSTALL_DIR" \
        npm --prefix "$ARCENAL_INSTALL_DIR" run build --workspace ui-tui
    ynh_exec_as_app env HOME="$ARCENAL_INSTALL_DIR" \
        npm --prefix "$ARCENAL_INSTALL_DIR" run build --workspace web -- --base="$web_base"
}

arcenal_install_control_user() {
    local control_user="${app}_control"
    if ! ynh_system_user_exists --username="$control_user"; then
        ynh_system_user_create --username="$control_user" --groups="$app"
    fi
}

arcenal_prepare_control_state() {
    install -d -o "${app}_control" -g "${app}_control" -m 0700 "/var/lib/$app-control"
}

arcenal_secure_base_permissions() {
    install -d -o root -g "$app" -m 0750 "/var/www/$app"
}

arcenal_secure_data_permissions() {
    local sensitive_file
    install -d -o "$app" -g "$app" -m 0700 "$ARCENAL_DATA_DIR"
    for sensitive_file in config.yaml .env .arcenal-yunohost; do
        [ ! -f "$ARCENAL_DATA_DIR/$sensitive_file" ] || \
            chown "$app:$app" "$ARCENAL_DATA_DIR/$sensitive_file"
        [ ! -f "$ARCENAL_DATA_DIR/$sensitive_file" ] || \
            chmod 0600 "$ARCENAL_DATA_DIR/$sensitive_file"
    done
    install -d -o "$app" -g "$app" -m 0700 "$ARCENAL_DATA_DIR/arcenal"
    if [ -f "$ARCENAL_DATA_DIR/arcenal/config.json" ]; then
        chown "$app:$app" "$ARCENAL_DATA_DIR/arcenal/config.json"
        chmod 0600 "$ARCENAL_DATA_DIR/arcenal/config.json"
    fi
    find "$ARCENAL_DATA_DIR" -xdev -type f \
        \( -name '*.db' -o -name '*.db-wal' -o -name '*.db-shm' -o -name '*.sqlite3' \) \
        -exec chown "$app:$app" {} + -exec chmod 0600 {} +
}

arcenal_migrate_native_configuration() {
    # L’ancien fichier reste intact ; la commande vérifie la copie native avant démarrage.
    ynh_exec_as_app env -u ARCENAL_CONFIG_BACKEND \
        ARCENAL_HOME="$ARCENAL_DATA_DIR" \
        HERMES_HOME="$ARCENAL_DATA_DIR" \
        "$ARCENAL_INSTALL_DIR/.venv/bin/python" \
        "$ARCENAL_INSTALL_DIR/scripts/arcenal_config_migrate.py" \
        "$ARCENAL_INSTALL_DIR" "$ARCENAL_DATA_DIR" || \
        ynh_die "La migration de la configuration native ARC a échoué."
    arcenal_secure_data_permissions
}

arcenal_install_security_bridge() {
    install -o root -g root -m 0755 ../conf/arcenal-privileged-broker /usr/local/sbin/arcenal-privileged-broker
    install -o root -g root -m 0755 ../conf/arcenal-nginx-reload /usr/local/sbin/arcenal-nginx-reload
    install -o root -g root -m 0755 ../conf/arcenal-control-socket-ready /usr/local/sbin/arcenal-control-socket-ready
    rm -f /usr/local/sbin/arcenal-supervisor-helper "/etc/sudoers.d/$app-supervisor"
    ynh_config_add_systemd --service="${app}_broker" --template="arcenal-broker.service"
    ynh_config_add_systemd --service="${app}_control" --template="arcenal-control.service"
}

arcenal_start_security_bridge() {
    ynh_systemctl --service="${app}_broker" --action="restart"
    ynh_systemctl --service="${app}_control" --action="restart"
}

arcenal_write_config() {
    mkdir -p "$ARCENAL_DATA_DIR"
    chmod 700 "$ARCENAL_DATA_DIR"

    # Les fournisseurs et modèles appartiennent aux agents, pas au paquet.
    cat > "$ARCENAL_DATA_DIR/config.yaml" <<EOF
# Managed by YunoHost (arcenal app). Manual edits may be overwritten
# by the config panel; use `yunohost app config set arcenal` instead.
terminal:
  backend: local
EOF
    chown -R "$app:" "$ARCENAL_DATA_DIR"
    arcenal_secure_data_permissions
}
