"""Détecte les processus applicatifs sans confondre le manager systemd utilisateur."""

from dataclasses import dataclass
import os
from pathlib import Path
import pwd
import subprocess
import sys
from typing import Callable


@dataclass(frozen=True)
class Process:
    pid: int
    parent: int
    state: str
    name: str


def parse_processes(output: str) -> list[Process]:
    result = []
    for line in output.splitlines():
        if not line.strip():
            continue
        pid, parent, state, name = line.split(maxsplit=3)
        process = Process(int(pid), int(parent), state, name.strip())
        if process.pid <= 0 or process.parent < 0 or not process.state:
            raise ValueError("Entrée de processus invalide")
        result.append(process)
    return result


def trusted_systemd(pid: int, executable: Callable[[int], str]) -> bool:
    try:
        return executable(pid) in {"/usr/lib/systemd/systemd", "/lib/systemd/systemd"}
    except OSError:
        # Un exécutable illisible reste bloquant ; le nom seul ne suffit pas.
        return False


def application_processes(processes: list[Process], executable: Callable[[int], str]) -> list[Process]:
    live = [process for process in processes if process.state[0] not in {"Z", "X"}]
    managers = {process.pid for process in live
                if process.name == "systemd" and process.parent == 1
                and trusted_systemd(process.pid, executable)}
    return [process for process in live
            if process.pid not in managers
            and not (process.name in {"(sd-pam)", "sd-pam"} and process.parent in managers
                     and trusted_systemd(process.pid, executable))]


def main() -> int:
    if os.geteuid() != 0:
        print("Le contrôle des processus nécessite les droits administrateur.", file=sys.stderr)
        return 2
    try:
        user = sys.argv[1]
        pwd.getpwnam(user)
        snapshot = subprocess.run(
            ["ps", "-u", user, "-o", "pid=,ppid=,stat=,comm="],
            capture_output=True, text=True, check=False,
        )
        if snapshot.returncode not in {0, 1} or (snapshot.returncode == 1 and snapshot.stderr.strip()):
            raise ValueError("Lecture des processus impossible")
        processes = application_processes(
            parse_processes(snapshot.stdout),
            lambda pid: os.path.realpath(os.readlink(Path("/proc") / str(pid) / "exe")),
        )
        for process in processes:
            print(process.pid, process.parent, process.state, process.name)
        return 0 if processes else 1
    except (IndexError, KeyError, OSError, ValueError):
        print("Impossible de vérifier les processus applicatifs.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
