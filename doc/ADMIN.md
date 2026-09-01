# Administration — ARCenal Agent (YunoHost)

## Architecture

- **App dir**: `/var/www/arcenal/app` — sources, venv (uv, Python 3.11), built web UI
- **Data dir**: `/var/www/arcenal/data` (`HERMES_HOME`) — `config.yaml`, `.env`, skills, memory, logs
- **Service**: `systemctl status arcenal` — runs `arcenal serve` (FastAPI web UI) on 127.0.0.1:9119
- **Reverse proxy**: nginx, exposed at the domain/path chosen at install; protected by YunoHost SSO (`init_main_permission`)

## Routine

```bash
yunohost app config set arcenal -a "main.model.model=anthropic/claude-sonnet-4"
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

## Gateways (Telegram, Discord, ...)

The web UI is the primary surface. Messaging gateways (`arcenal gateway`) run as
a separate concern; each platform (Telegram bot token, etc.) is configured in
`/var/www/arcenal/data/config.yaml`. A dedicated systemd unit can be added later.

## Security notes

The agent executes arbitrary shell commands **as the `arcenal` system user** on
your server. The unit is hardened (ProtectSystem=strict, NoNewPrivileges) but the
execution capability is the product's core feature — restrict SSO access
accordingly and consider a Docker terminal backend for stronger isolation.
