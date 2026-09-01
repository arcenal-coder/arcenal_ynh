# Disclaimer / Avertissement

**ARCenal Agent executes commands on your server.** This application is an AI
agent whose core feature is running shell commands and editing files on the host,
under the dedicated unprivileged `arcenal` system user. Anyone with access to the
web UI can instruct the agent to act on the server.

- Restrict access via YunoHost's permission system at install time (default: `admins` only).
- Data dir `/var/www/arcenal/data/.env` holds your provider API keys (chmod 600).
- For stronger isolation, configure a containerized terminal backend instead of `local`.

**FR :** ARCenal Agent exécute des commandes sur votre serveur, sous l'utilisateur
système dédié et sans privilèges `arcenal`. Toute personne ayant accès à l'interface
web peut lui demander d'agir sur le serveur. Restreignez l'accès via les permissions
YunoHost (défaut : `admins` uniquement). Les clés API sont stockées dans
`/var/www/arcenal/data/.env` (chmod 600).

---

Fork of [Hermes Agent](https://github.com/NousResearch/hermes-agent) by Nous
Research, MIT license. ARCenal Agent is an independent project; upstream is not
responsible for it.
