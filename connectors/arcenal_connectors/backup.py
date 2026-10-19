"""Instantané privé cohérent ; refus des liens et chemins étrangers à la couche centrale."""

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import uuid

from .contracts import require
from .store import Store


ROOTS = ("var/lib/arcenal-connectors", "etc/arcenal-connectors",
         "usr/local/libexec/arcenal-yunohost", "etc/sudoers.d/arcenal-connectors")


def validate(archive):
    members = archive.getmembers()
    require(bool(members), "sauvegarde_connecteurs_invalide")
    require(len({str(PurePosixPath(member.name)) for member in members}) == len(members), "sauvegarde_connecteurs_invalide")
    for member in members:
        path = PurePosixPath(member.name)
        permitted = any(member.name == root or member.name.startswith(root + "/") for root in ROOTS[:2])
        permitted = permitted or (member.name in ROOTS[2:] and member.isfile())
        require(str(path) == member.name and not path.is_absolute() and ".." not in path.parts and permitted
                and (member.isfile() or member.isdir()) and 0 <= member.size <= 1024 ** 3, "sauvegarde_connecteurs_invalide")
    require("var/lib/arcenal-connectors" in {member.name for member in members}, "sauvegarde_connecteurs_invalide")
    return members


def extract(archive, members, destination):
    """Extraction sans liens, compatible avec Python système Bookworm 3.11.2."""
    destination.mkdir(parents=True, mode=0o700, exist_ok=True)
    for member in members:
        target = destination / member.name
        directory = target if member.isdir() else target.parent
        parent = destination
        for part in directory.relative_to(destination).parts:
            parent = parent / part
            require(not parent.is_symlink(), "destination_invalide")
            mode = 0o755 if str(parent.relative_to(destination)) in ("usr", "usr/local", "usr/local/libexec") else 0o700
            parent.mkdir(mode=mode, exist_ok=True)
        if member.isfile():
            require(not target.is_symlink(), "destination_invalide")
            temporary = target.with_name(target.name + ".restore-" + uuid.uuid4().hex)
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with os.fdopen(fd, "wb") as output, archive.extractfile(member) as source:
                    shutil.copyfileobj(source, output)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary, target)
            finally:
                if temporary.exists():
                    temporary.unlink()


def restore(path, destination=Path("/")):
    with tarfile.open(path) as archive:
        members = validate(archive)
        owner_file = destination / "etc/arcenal-connectors/owner"
        require(not owner_file.is_symlink(), "destination_invalide")
        owner = owner_file.read_bytes() if owner_file.exists() else None
        # Valider intégralement avant tout déplacement ou remplacement.
        for root in ROOTS[:2]:
            current = destination / root
            require(not current.is_symlink(), "destination_invalide")
            if current.exists():
                current.rename(current.with_name(current.name + ".before-restore-" + uuid.uuid4().hex))
        extract(archive, [m for m in members if m.name != "etc/arcenal-connectors/owner"], destination)
        helper = destination / "usr/local/libexec/arcenal-yunohost"
        if helper.exists():
            helper.chmod(0o755)
        if owner is not None:
            owner_file.write_bytes(owner)
            owner_file.chmod(0o600)
        policy_file = destination / "etc/arcenal-connectors/policy.json"
        if policy_file.exists():
            policy = json.loads(policy_file.read_text())
            # Un UID numérique archivé peut désigner une autre personne sur l'hôte cible.
            policy["profile_uids"] = {}
            policy_file.write_text(json.dumps(policy, indent=2) + "\n")
            policy_file.chmod(0o640)
        profiles = destination / "var/lib/arcenal-connectors/profiles"
        if profiles.exists():
            for home in profiles.iterdir():
                if not home.is_dir():
                    continue
                store = Store(profiles, home.name, {})
                with store.transaction("restore") as db:
                    for name, value in store._items(db, "connector"):
                        value["revision"] += 1
                        value["state"] = "a_tester" if value.get("secret") or name == "yunohost" else "desactive"
                        store._write(db, "connector", name, value)
                    for key, grant in store._items(db, "grant"):
                        grant["revoked"] = True
                        store._write(db, "grant", key, grant)
                    for key, request in store._items(db, "request"):
                        if request["state"] in ("pending", "executing"):
                            request["state"] = "invalidated_by_restore"
                            store._write(db, "request", key, request)
                    store._audit(db, "restauration_autorisations_invalidees", "restore")


def main():
    require(os.geteuid() == 0, "restauration_root_requise")
    parser = argparse.ArgumentParser()
    parser.add_argument("--restore", required=True, type=Path)
    args = parser.parse_args()
    restore(args.restore)


if __name__ == "__main__":
    main()
