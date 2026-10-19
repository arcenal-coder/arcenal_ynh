"""Entrée isolée : uniquement du code du paquet, pas le PYTHONPATH d'Hermes."""

import importlib
from pathlib import Path
import sys


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("server", "provision", "backup", "inventory"):
        raise SystemExit("Sous-commande centrale non autorisée")
    module = sys.argv.pop(1)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    importlib.import_module("arcenal_connectors." + module).main()
