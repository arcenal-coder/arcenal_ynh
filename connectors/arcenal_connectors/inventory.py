"""Inventaire YunoHost minimal : identifiants uniquement, jamais les réglages."""

import json
import os
import re
import subprocess

from .contracts import Denied, fields, require


READ_COMMANDS = {
    "applications": ["/usr/bin/yunohost", "app", "list", "--output-as", "json"],
    "services": ["/usr/bin/yunohost", "service", "status", "--output-as", "json"],
    "domains": ["/usr/bin/yunohost", "domain", "list", "--output-as", "json"],
}
SELF_SERVICES = frozenset(("arcenal", "arcenal-connectors"))
STOP_PROTECTED = SELF_SERVICES | {"nginx", "slapd", "nslcd", "ssh", "sshd", "yunohost-api", "yunohost-portal-api"}


def validate_inventory(value):
    fields(value, READ_COMMANDS)
    patterns = {"applications": r"[a-z][a-z0-9_-]{0,63}",
                "services": r"[a-z][a-z0-9_.@-]{0,79}",
                "domains": r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?"}
    for kind, values in value.items():
        require(isinstance(values, list) and len(values) <= 50, "inventaire_hors_limites")
        require(all(isinstance(item, str) and re.fullmatch(patterns[kind], item) for item in values),
                "inventaire_invalide")
    return {kind: sorted(set(value[kind])) for kind in READ_COMMANDS}


def collect():
    result = {}
    for kind, command in READ_COMMANDS.items():
        try:
            response = subprocess.run(command, capture_output=True, text=True, check=False, timeout=30,
                cwd="/", env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8"})
            require(response.returncode == 0 and len(response.stdout) <= 1024 * 1024, "inventaire_indisponible")
            data = json.loads(response.stdout)
            if kind == "applications":
                require(isinstance(data, dict) and isinstance(data.get("apps"), list), "inventaire_invalide")
                result[kind] = [app["id"] for app in data["apps"] if isinstance(app, dict) and isinstance(app.get("id"), str)]
            elif kind == "services":
                require(isinstance(data, dict), "inventaire_invalide")
                result[kind] = list(data)
            else:
                require(isinstance(data, dict) and isinstance(data.get("domains"), list), "inventaire_invalide")
                result[kind] = data["domains"]
        except (OSError, ValueError, subprocess.SubprocessError):
            raise Denied("inventaire_indisponible") from None
    return validate_inventory(result)


def filtered(value, allowed):
    value = validate_inventory(value)
    return {kind: [name for name in values if name in allowed.get(kind, [])] for kind, values in value.items()}


def main():
    require(os.geteuid() == 0, "root_requis")
    print(json.dumps(collect()))
