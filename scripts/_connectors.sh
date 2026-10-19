#!/bin/bash

hermes_connectors_enabled() {
    [ "$(ynh_app_setting_get --key=connectors_installed)" = "1" ]
}

hermes_connectors_install_layer() {
    hermes_connectors_identity
    # Source du paquet gérée par root, JAMAIS l'arbre construit par l'UID Hermes.
    local layer=/usr/local/lib/arcenal-connectors
    test ! -L "$layer" || ynh_die "Le code central ne peut pas être un lien symbolique."
    install -d -o root -g arcenal-connectors -m 0750 "$layer"
    install -d -o root -g arcenal-connectors -m 0750 "$layer/arcenal_connectors" "$layer/hermes-plugins"
    cp -R ../connectors/arcenal_connectors/. "$layer/arcenal_connectors/"
    cp -R ../connectors/hermes-plugins/. "$layer/hermes-plugins/"
    install -o root -g arcenal-connectors -m 0640 ../connectors/run.py "$layer/run.py"
    install -o root -g arcenal-connectors -m 0640 ../conf/connectors-sudoers "$layer/connectors-sudoers"
    if [ ! -d /usr/local/libexec ]; then install -d -o root -g root -m 0755 /usr/local/libexec; fi
    install -o root -g root -m 0755 ../connectors/yunohost-helper /usr/local/libexec/arcenal-yunohost
    chown -R root:arcenal-connectors "$layer"
    chmod -R u=rwX,g=rX,o= "$layer"
}

hermes_connectors_identity() {
    local connector_user=arcenal-connectors
    # Une identité existante étrangère au paquet n'est jamais adoptée.
    if ynh_system_user_exists --username="$connector_user"; then
        test -f /etc/arcenal-connectors/owner || ynh_die "Compte connecteurs préexistant non géré par ce paquet."
        test "$(cat /etc/arcenal-connectors/owner)" = "$app:$(id -u "$connector_user")" || ynh_die "Propriété du compte connecteurs incohérente."
    else
        local artifact
        for artifact in /usr/local/lib/arcenal-connectors /usr/local/libexec/arcenal-yunohost \
            /etc/arcenal-connectors /etc/sudoers.d/arcenal-connectors /var/lib/arcenal-connectors; do
            if [ -e "$artifact" ] || [ -L "$artifact" ]; then
                ynh_die "Des artefacts connecteurs préexistent sans identité gérée ; vérifier leur propriété."
            fi
        done
        ynh_system_user_create --username="$connector_user" --home_dir=/var/lib/arcenal-connectors
        install -d -o root -g "$connector_user" -m 0750 /etc/arcenal-connectors
        printf '%s\n' "$app:$(id -u "$connector_user")" > /etc/arcenal-connectors/owner
        chmod 0600 /etc/arcenal-connectors/owner
    fi
    ynh_app_setting_set --key=connectors_installed --value=1
}

hermes_connectors_configure() {
    local connector_user=arcenal-connectors
    hermes_connectors_identity
    install -d -o "$connector_user" -g "$connector_user" -m 0700 /var/lib/arcenal-connectors
    local administrators inventory
    administrators=$(yunohost user group info admins --output-as json | python3 -c \
        'import json,sys; print(json.dumps(json.load(sys.stdin)["members"]))')
    inventory=$(/usr/bin/python3 -I -B /usr/local/lib/arcenal-connectors/run.py inventory)
    /usr/bin/python3 -I -B /usr/local/lib/arcenal-connectors/run.py provision \
        --hermes-home "$data_dir" --users-json "$administrators" --origin "https://$domain:$port_connectors" \
        --plugins-source /usr/local/lib/arcenal-connectors/hermes-plugins \
        --native-yunohost --inventory-json "$inventory"
    chown -R "$connector_user:$connector_user" /var/lib/arcenal-connectors
    install -o root -g root -m 0440 /usr/local/lib/arcenal-connectors/connectors-sudoers /etc/sudoers.d/arcenal-connectors
    visudo --check --file=/etc/sudoers.d/arcenal-connectors
    ynh_config_add_systemd --service="$app-connectors" --template=connectors.service
    local connectors_path="${path%/}"
    ynh_config_add --template=connectors-nginx.conf --destination="/etc/nginx/conf.d/$app-connectors.conf"
    yunohost service add "$app-connectors" --description="ARCenal Agent — connecteurs centraux"
}

hermes_connectors_stop() {
    if hermes_connectors_enabled && systemctl is-active --quiet "$app-connectors.service"; then
        ynh_systemctl --service="$app-connectors" --action=stop
    fi
}

hermes_connectors_backup() {
    if hermes_connectors_enabled; then
        local snapshot
        snapshot=$(mktemp "$install_dir/.ynh-connectors-snapshot.XXXXXX")
        # L'autorité est arrêtée par le script appelant : aucun WAL vivant copié.
        if ! tar --create --file="$snapshot" --directory=/ var/lib/arcenal-connectors \
            etc/arcenal-connectors usr/local/libexec/arcenal-yunohost etc/sudoers.d/arcenal-connectors; then
            rm -f "$snapshot"
            return 1
        fi
        chown root:root "$snapshot"
        chmod 0600 "$snapshot"
        mv "$snapshot" "$install_dir/.ynh-connectors-snapshot.tar"
        ynh_backup "/etc/systemd/system/$app-connectors.service"
        ynh_backup "/etc/nginx/conf.d/$app-connectors.conf"
        ynh_backup /usr/local/lib/arcenal-connectors
    fi
}
