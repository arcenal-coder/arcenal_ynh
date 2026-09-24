# Administration — ARCenal Agent (YunoHost)

## Architecture

- **App dir**: `/var/www/arcenal/app` — sources, venv (uv, Python 3.11), built web UI
- **Data dir**: `/var/www/arcenal/data` (`HERMES_HOME`) — `config.yaml`, `.env`, skills, memory, logs
- **Service**: `systemctl status arcenal` — runs `arcenal serve` (FastAPI web UI) on 127.0.0.1:9119
- **Reverse proxy** : nginx, exposé sur le domaine et le chemin choisis ; les
  trois volets d'administration sont réservés au groupe `admins` de YunoHost.
- **Wiki QSSERP** : route `/wiki`, accessible aux comptes YunoHost du groupe
  `all_users` ; les brouillons et les API d'administration restent interdits.

## Routine

```bash
yunohost app config set arcenal -a "main.model_settings.provider=anthropic&main.model_settings.model=anthropic/claude-sonnet-4"
tail -f /var/log/arcenal/arcenal.log          # or journalctl -u arcenal -f
yunohost app upgrade arcenal
yunohost app backup arcenal
```

CLI on the server (as the app user):

```bash
sudo -u arcenal HERMES_HOME=/var/www/arcenal/data \
  /var/www/arcenal/app/.venv/bin/arcenal doctor
```

## Updates

The upstream `hermes update` / `arcenal update` mechanism is **bypassed**: upgrades
are driven by YunoHost's `upgrade` script, which re-downloads a pinned source
archive. Never run `arcenal update` on the server — the install is not a git
checkout and the command will refuse or fail harmlessly.

La mise à niveau vers `0.21.0~ynh26` ajoute le menu secondaire Paramètres. Il
permet de connecter OpenRouter, de tester la clé et de sélectionner le modèle
principal sans manipuler `.env` ou `config.yaml` manuellement. Cette révision
répare également les mises à niveau d'installations anciennes auxquelles
l'exécutable `uv` manque et la restauration automatique `BACKUP_CORE_ONLY`.

## Gateways (Telegram, Discord, ...)

The web UI is the primary surface. Messaging gateways (`arcenal gateway`) run as
a separate concern; each platform (Telegram bot token, etc.) is configured in
`/var/www/arcenal/data/config.yaml`. A dedicated systemd unit can be added later.

## Security notes

The agent executes arbitrary shell commands **as the `arcenal` system user** on
your server. The unit is hardened (ProtectSystem=strict, NoNewPrivileges) but the
execution capability is the product's core feature — restrict SSO access
accordingly and consider a Docker terminal backend for stronger isolation.
