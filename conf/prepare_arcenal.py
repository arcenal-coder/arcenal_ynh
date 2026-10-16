"""Habillage de la distribution ARCenal et politique de mise à jour YunoHost."""

import argparse
from pathlib import Path


SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-label="ARCenal Agent">
<rect width="64" height="64" rx="14" fill="#b84b2c"/>
<path d="M14 49 28 14h8l14 35H40l-3-8H26l-3 8Zm15-16h6l-3-10Z" fill="#fff9ef"/>
</svg>\n'''


def substitute(text: str, old: str, new: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise ValueError("Point d'adaptation amont absent ; aucun fichier modifié.")
    if text.count(old) != 1:
        raise ValueError("Point d'adaptation amont ambigu ; aucun fichier modifié.")
    return text.replace(old, new, 1)


def prepare(source: Path) -> None:
    replacements = {
        "web/src/App.tsx": [
            ("                  Hermes\n                  <br />\n                  Agent",
             "                  ARCenal\n                  <br />\n                  Agent"),
            ("const canUpdateHermes = status?.can_update_hermes === true;",
             "const canUpdateHermes = false; // Mises à jour gérées par YunoHost."),
        ],
        "web/src/pages/SystemPage.tsx": [
            ("const canUpdateHermes = status?.can_update_hermes !== false;",
             "const canUpdateHermes = false; // Mises à jour gérées par YunoHost."),
            ('<div className="text-xs uppercase tracking-wider text-muted-foreground">Hermes</div>',
             '<div className="text-xs uppercase tracking-wider text-muted-foreground">ARCenal Agent</div>'),
        ],
        "web/index.html": [
            ("<title>Hermes Agent - Dashboard</title>", "<title>ARCenal Agent — Tableau de bord</title>"),
            ('href="/favicon.ico"', 'href="/arcenal-agent.svg"'),
        ],
    }
    planned = {}
    for relative, changes in replacements.items():
        path = source / relative
        text = path.read_text(encoding="utf-8")
        for old, new in changes:
            text = substitute(text, old, new)
        planned[path] = text
    for path in (source / "web/src/i18n").glob("*.ts"):
        text = path.read_text(encoding="utf-8")
        if 'brand: "Hermes Agent"' in text:
            planned[path] = text.replace('brand: "Hermes Agent"', 'brand: "ARCenal Agent"').replace('brandShort: "HA"', 'brandShort: "ARC"')
    policy = source / "hermes_cli/web_server_files.py"
    text = policy.read_text(encoding="utf-8")
    old = """    from hermes_cli.web_server import PROJECT_ROOT
    from hermes_cli.config import detect_install_method
    if _default_hermes_root_is_opt_data():"""
    new = """    from hermes_cli.web_server import PROJECT_ROOT
    from hermes_cli.config import detect_install_method
    from hermes_cli.steward import read_install_stamp
    if read_install_stamp(PROJECT_ROOT).get("updateMechanism") == "external":
        return True
    if _default_hermes_root_is_opt_data():"""
    planned[policy] = substitute(text, old, new)
    icon = source / "web/public/arcenal-agent.svg"
    if icon.exists() and icon.read_text(encoding="utf-8") != SVG:
        raise ValueError("Une icône ARCenal personnalisée existe déjà ; adaptation refusée.")
    for path, text in planned.items():
        path.write_text(text, encoding="utf-8")
    icon.write_text(SVG, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    prepare(parser.parse_args().source)
