#!/bin/bash

# Fonctions communes du paquet YunoHost ARCenal Agent.
# Les helpers du packaging v2 sont chargés automatiquement.

readonly ARCENAL_INSTALL_DIR="/var/www/arcenal/app"
readonly ARCENAL_DATA_DIR="/var/www/arcenal/data"     # HERMES_HOME (config.yaml, .env, skills, memory)
readonly ARCENAL_SERVICE_NAME="arcenal"

# Retourne la version figée de l'archive source ARCenal Agent.
# Le manifeste épingle aussi son empreinte afin de garantir la reproductibilité.
arcenal_get_source_version() {
    echo "0.21.0-arcenal20"
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
    local web_group="${app}_web"
    if ! ynh_system_user_exists --username="$control_user"; then
        ynh_system_user_create --username="$control_user" --groups="$app"
    fi
    if ! ynh_system_group_exists --group="$web_group"; then
        groupadd --system "$web_group"
    fi
    usermod -a -G "$web_group" "$control_user"
    usermod -a -G "$web_group" www-data
}

arcenal_prepare_control_state() {
    install -d -o "${app}_control" -g "${app}_control" -m 0700 "/var/lib/$app-control"
}

arcenal_install_security_bridge() {
    install -o root -g root -m 0755 ../conf/arcenal-privileged-broker /usr/local/sbin/arcenal-privileged-broker
    install -o root -g root -m 0755 ../conf/arcenal-nginx-reload /usr/local/sbin/arcenal-nginx-reload
    rm -f /usr/local/sbin/arcenal-supervisor-helper "/etc/sudoers.d/$app-supervisor"
    ynh_config_add_systemd --service="${app}_broker" --template="arcenal-broker.service"
    ynh_config_add_systemd --service="${app}_control" --template="arcenal-control.service"
}

arcenal_start_security_bridge() {
    ynh_systemctl --service="${app}_broker" --action="restart"
    ynh_systemctl --service="${app}_control" --action="restart"
}

arcenal_write_config() {
    # $1 = provider, $2 = api key, $3 = model
    local provider="$1"
    local api_key="$2"
    local model="$3"

    mkdir -p "$ARCENAL_DATA_DIR"
    chmod 700 "$ARCENAL_DATA_DIR"

    # Non-interactive config, replacing `hermes setup`.
    cat > "$ARCENAL_DATA_DIR/config.yaml" <<EOF
# Managed by YunoHost (arcenal app). Manual edits may be overwritten
# by the config panel; use `yunohost app config set arcenal` instead.
model:
  provider: $provider
  default: $model
terminal:
  backend: local
EOF
    chown -R "$app:" "$ARCENAL_DATA_DIR"

    if [ -n "$api_key" ]; then
        printf '%s_API_KEY=%s\n' "$(echo "$provider" | tr '[:lower:]-' '[:upper:]_')" "$api_key" \
            > "$ARCENAL_DATA_DIR/.env"
        chmod 600 "$ARCENAL_DATA_DIR/.env"
        chown "$app:" "$ARCENAL_DATA_DIR/.env"
    fi
}
