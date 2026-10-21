"""Provisionnement root explicite ; aucun secret métier ni compte administrateur créé."""

import argparse
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
from typing import Any

from .contracts import identifier, require
from .inventory import SELF_SERVICES, STOP_PROTECTED, validate_inventory
from urllib.parse import urlsplit


def atomic(path, content, mode=0o600):
    require(not path.is_symlink(), "fichier_de_provisionnement_invalide")
    temporary = path.with_suffix(path.suffix + ".new")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def install_plugins(source, home, console_origin):
    root = home / "plugins"
    require(not root.is_symlink(), "collision_plugin")
    root.mkdir(mode=0o750, exist_ok=True)
    for directory in source.iterdir():
        if not directory.is_dir():
            continue
        target = root / directory.name
        require(not target.is_symlink(), "collision_plugin")
        marker = target / ".arcenal-owned"
        if target.exists():
            require(marker.is_file(), "plugin_personnalise_a_preserver")
            require(not any(file.is_symlink() for file in target.rglob("*")), "collision_plugin")
            hashes = json.loads(marker.read_text())
            for relative, expected in hashes.items():
                file = target / relative
                require(file.is_file() and not file.is_symlink()
                        and hashlib.sha256(file.read_bytes()).hexdigest() == expected, "plugin_personnalise_a_preserver")
        shutil.copytree(directory, target, dirs_exist_ok=True)
        if directory.name == "arcenal-connectors":
            entry = target / "dashboard/dist/index.js"
            entry.write_text(entry.read_text().replace('"__ARCENAL_CONSOLE_ORIGIN__"', json.dumps(console_origin)))
        hashes = {str(file.relative_to(target)): hashlib.sha256(file.read_bytes()).hexdigest()
                  for file in target.rglob("*") if file.is_file() and file.name != ".arcenal-owned"
                  and "__pycache__" not in file.parts}
        atomic(marker, json.dumps(hashes))
    marker = home / ".arcenal-connectors-installed"
    require(not marker.is_symlink(), "collision_plugin")
    marker.touch(mode=0o600, exist_ok=True)


def bootstrap(policy_file, vault_root, home, profile, users, origin, inventory=None):
    identifier(profile)
    parsed = urlsplit(origin)
    require(parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password and not parsed.query
            and not parsed.fragment and not parsed.path and parsed.port and 1024 <= parsed.port <= 65535,
            "origine_console_invalide")
    require(not Path(home).is_symlink() and Path(home).is_dir(), "profil_hermes_absent")
    require(users and all(isinstance(user, str) and re.fullmatch(r"[a-z][a-z0-9_.-]{0,63}", user)
                         for user in users), "administrateur_requis")
    policy_file = Path(policy_file)
    existing = policy_file.exists()
    policy: dict[str, Any] = json.loads(policy_file.read_text()) if existing else {
        "schema": 1, "origin": origin, "vault_root": str(vault_root), "principals": {},
        "profile_uids": {}, "allowed_private_networks": [], "yunohost_targets": {},
    }
    require(isinstance(policy, dict) and all(isinstance(policy.get(name), dict) for name in
            ("principals", "profile_uids", "yunohost_targets")), "politique_incompatible")
    require(policy.get("schema") == 1 and policy["origin"] == origin
            and policy["vault_root"] == str(vault_root), "politique_incompatible")
    uid = Path(home).stat().st_uid
    require(uid != 0, "runtime_client_non_root_requis")
    bindings = policy.setdefault("profile_uids", {})
    require(all(name == profile or owner != uid for name, owner in bindings.items()),
            "un_utilisateur_systeme_distinct_par_client_est_requis")
    require(bindings.get(profile, uid) == uid, "identite_systeme_du_client_modifiee")
    bindings[profile] = uid
    first_profile = profile not in policy["yunohost_targets"]
    if first_profile:
        for user in users:
            principal = policy["principals"].setdefault(user, {"role": "admin", "profiles": []})
            if profile not in principal["profiles"]:
                principal["profiles"].append(profile)
        policy["yunohost_targets"][profile] = {"service.status": ["arcenal"], "service.restart": [], "backup.create": []}
        if inventory is not None:
            inventory = validate_inventory(inventory)
            services = sorted(set(inventory["services"]) | {"arcenal"})
            require(len(services) <= 50, "inventaire_hors_limites")
            policy["yunohost_targets"][profile] = {
                "server.inventory": ["server"], "service.status": ["arcenal", *[s for s in services if s != "arcenal"]],
                "service.start": [s for s in services if s not in SELF_SERVICES],
                "service.stop": [s for s in services if s not in STOP_PROTECTED],
                "service.restart": [s for s in services if s not in SELF_SERVICES],
                "backup.create": [app for app in inventory["applications"] if app != "arcenal"],
            }
            policy.setdefault("yunohost_inventory", {})[profile] = inventory
    policy_file.parent.mkdir(parents=True, mode=0o750, exist_ok=True)
    atomic(policy_file, json.dumps(policy, indent=2) + "\n", 0o640)
    return policy


def main():
    parser = argparse.ArgumentParser(description="Affecter un profil client à des administrateurs SSO explicites.")
    parser.add_argument("--policy", default="/etc/arcenal-connectors/policy.json")
    parser.add_argument("--vault-root", default="/var/lib/arcenal-connectors/profiles")
    parser.add_argument("--hermes-home", required=True)
    parser.add_argument("--profile", default="default")
    parser.add_argument("--users-json", required=True)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--plugins-source", required=True)
    parser.add_argument("--native-yunohost", action="store_true")
    parser.add_argument("--inventory-json", help="Inventaire minimal collecté par l'installateur root")
    parser.add_argument("--operation-authority", action="store_true")
    args = parser.parse_args()
    require(os.getuid() == 0, "root_requis")
    home = Path(args.hermes_home)
    require(not args.native_yunohost or args.inventory_json is not None, "inventaire_requis")
    inventory = json.loads(args.inventory_json) if args.native_yunohost else None
    policy = bootstrap(Path(args.policy), args.vault_root, home, args.profile, json.loads(args.users_json), args.origin, inventory)
    if args.operation_authority:
        policy.setdefault("operation_authority", {})[args.profile] = True
        atomic(Path(args.policy), json.dumps(policy, indent=2) + "\n", 0o640)
    uid = pwd.getpwnam("arcenal-connectors").pw_uid
    gid = grp.getgrnam("arcenal-connectors").gr_gid
    os.chown(args.policy, 0, gid)
    os.chmod(Path(args.policy).parent, 0o750)
    os.chown(Path(args.policy).parent, 0, gid)
    vault = Path(args.vault_root)
    vault.mkdir(parents=True, mode=0o700, exist_ok=True)
    for path in (vault.parent, vault):
        os.chown(path, uid, gid)
        path.chmod(0o700)
    if args.native_yunohost:
        from .store import Store
        Store(vault, args.profile, {}).initialize_yunohost("https://" + urlsplit(args.origin).hostname,
                                                        policy["yunohost_targets"][args.profile])
    install_plugins(Path(args.plugins_source), home, args.origin)
    hermes_gid = home.stat().st_gid
    os.chown(home / "plugins", 0, hermes_gid)
    (home / "plugins").chmod(0o750)
    for path in (home / "plugins").rglob("*"):
        if any(part.startswith("arcenal-") for part in path.relative_to(home / "plugins").parts[:1]):
            require(not path.is_symlink(), "collision_plugin")
            os.chown(path, 0, hermes_gid)
            path.chmod(0o750 if path.is_dir() else 0o640)


if __name__ == "__main__":
    main()
