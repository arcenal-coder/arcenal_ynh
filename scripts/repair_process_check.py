"""Réparation ciblée du filtre de sauvegarde installé ; aucune donnée applicative touchée."""

import argparse
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.request import urlopen


KNOWN = {
    "87064d33495734b8fa7907f3fe1e2a6a36ce16f3c7409f6dad3254f1928be553",
    "0df097d009ac7a1d3ede7d423b18db13995892f5dd5895dd6a4c262cc07853a2",
    "56627ec69ae74a3f89f7d1280081f39e00ecf7c8f66e9dec6a525e66e9d92fc5",
}


def replace_function(original: bytes, function: bytes) -> bytes:
    start = original.index(b"hermes_quiescent_data() {\n")
    end = original.index(b"hermes_retire_privileges() {", start)
    return original[:start] + function.rstrip() + b"\n\n" + original[end:]


def atomic_write(path: Path, data: bytes, mode: int) -> None:
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".process-check-")
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def download(revision: str, name: str) -> bytes:
    url = f"https://raw.githubusercontent.com/arcenal-coder/arcenal_ynh/{revision}/scripts/{name}"
    with urlopen(url, timeout=30) as response:
        return response.read()


def repair(directory: Path, helper: bytes, source: bytes) -> Path:
    common = directory / "_common.sh"
    target = directory / "process_check.py"
    if common.is_symlink() or target.is_symlink():
        raise ValueError("Lien symbolique inattendu : réparation refusée.")
    original = common.read_bytes()
    if hashlib.sha256(original).hexdigest() not in KNOWN:
        raise ValueError("Le script installé n'est pas une révision connue ; aucune modification effectuée.")
    if target.exists() and target.read_bytes() != helper:
        raise ValueError("Un contrôleur personnalisé existe déjà ; réparation refusée.")
    start = source.index(b"hermes_quiescent_data() {\n")
    end = source.index(b"hermes_retire_privileges() {", start)
    patched = replace_function(original, source[start:end])
    subprocess.run(["bash", "-n"], input=patched, check=True, capture_output=True)
    compile(helper, "process_check.py", "exec")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    backup = common.with_name("_common.sh.before-process-fix-" + stamp)
    shutil.copy2(common, backup)
    atomic_write(target, helper, 0o600)
    atomic_write(common, patched, common.stat().st_mode & 0o777)
    return backup


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--helper-sha256", required=True)
    parser.add_argument("--common-sha256", required=True)
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error("Authentification administrateur requise.")
    if not re.fullmatch(r"[0-9a-f]{40}", args.revision):
        parser.error("Révision Git complète requise.")
    helper = download(args.revision, "process_check.py")
    source = download(args.revision, "_common.sh")
    if (hashlib.sha256(helper).hexdigest() != args.helper_sha256
            or hashlib.sha256(source).hexdigest() != args.common_sha256):
        raise ValueError("Empreinte du correctif invalide ; réparation refusée.")
    backup = repair(Path("/etc/yunohost/apps/arcenal/scripts"), helper, source)
    print("Filtre corrigé. Original conservé :", backup)
    print("Aucun service redémarré, aucune sauvegarde ou mise à jour lancée.")


if __name__ == "__main__":
    main()
