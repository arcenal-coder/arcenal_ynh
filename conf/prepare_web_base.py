"""Adapte uniquement la base Vite au chemin de l'application YunoHost."""

import argparse
import json
from pathlib import Path


ANCHOR = "export default defineConfig({\n"
MARKER = " // Base YunoHost gérée par le paquet."


def normalize_base(path: str) -> str:
    if (not path.startswith("/") or path.startswith("//")
            or any(character in path for character in ("?", "#", "\\", "\n", "\r", "\x00"))
            or ".." in path.split("/")):
        raise ValueError("Chemin de build YunoHost invalide")
    return path.rstrip("/") + "/"


def configure_base(config: Path, path: str) -> None:
    text = config.read_text(encoding="utf-8")
    if text.count(ANCHOR) != 1:
        raise ValueError("Configuration Vite amont inattendue ; aucune modification.")
    lines = [line for line in text.splitlines(keepends=True) if MARKER not in line]
    text = "".join(lines)
    declaration = "  base: " + json.dumps(normalize_base(path)) + "," + MARKER + "\n"
    config.write_text(text.replace(ANCHOR, ANCHOR + declaration, 1), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--path", required=True)
    args = parser.parse_args()
    configure_base(args.source / "web/vite.config.ts", args.path)


if __name__ == "__main__":
    main()
