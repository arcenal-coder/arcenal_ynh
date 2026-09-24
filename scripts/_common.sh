#!/bin/bash

# Fonctions communes du paquet YunoHost ARCenal Agent.
# Les helpers du packaging v2 sont chargés automatiquement.

readonly ARCENAL_INSTALL_DIR="/var/www/arcenal/app"
readonly ARCENAL_DATA_DIR="/var/www/arcenal/data"     # HERMES_HOME (config.yaml, .env, skills, memory)
readonly ARCENAL_SERVICE_NAME="arcenal"

# Retourne la version figée de l'archive source ARCenal Agent.
# Le manifeste épingle aussi son empreinte afin de garantir la reproductibilité.
arcenal_get_source_version() {
    echo "0.21.0-arcenal17"
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
