"""Prépare les thèmes Hermes sans remplacer les données de l'utilisateur."""

import json
import os
from pathlib import Path


LIGHT = {
    "background": "#fff9ef", "text": "#1f2937", "card": "#fffdf8",
    "secondary": "#fff7e8", "muted": "#f3faf4", "mutedForeground": "#64748b",
    "primary": "#b84b2c", "primaryForeground": "#ffffff", "border": "#e9e3d7",
    "input": "#d7d1c5", "ring": "#3157a4", "success": "#26705d",
    "warning": "#956211", "destructive": "#9d3d25",
}
DARK = {
    "background": "#17191e", "text": "#f5f0e8", "card": "#20232a",
    "secondary": "#292c33", "muted": "#1c2421", "mutedForeground": "#b8b1a7",
    "primary": "#e47a55", "primaryForeground": "#17191e", "border": "#3a3d45",
    "input": "#4a4d55", "ring": "#8fb4ff", "success": "#5aae91",
    "warning": "#e9b85d", "destructive": "#ef8069",
}


def overrides(colors: dict[str, str]) -> dict[str, str]:
    return {
        **{key: value for key, value in colors.items() if key not in {"background", "text"}},
        "cardForeground": colors["text"], "popover": colors["card"],
        "popoverForeground": colors["text"], "secondaryForeground": colors["text"],
        "accent": colors["secondary"], "accentForeground": colors["text"],
    }


def variables(colors: dict[str, str]) -> str:
    values = {"background-base": colors["background"], "background": colors["background"],
              "midground-base": colors["text"], "midground": colors["text"]}
    for key, value in overrides(colors).items():
        name = "".join("-" + c.lower() if c.isupper() else c for c in key)
        values["color-" + name] = value
    return ";".join(f"--{key}:{value}!important" for key, value in values.items())


def theme(mode: str) -> dict[str, object]:
    colors = DARK if mode == "dark" else LIGHT
    css = ":root{color-scheme:" + ("dark" if mode == "dark" else "light") + "}"
    if mode == "system":
        css += "@media(prefers-color-scheme:dark){:root{" + variables(DARK) + ";color-scheme:dark}}"
    return {
        "name": "gratitude-" + mode,
        "label": "Gratitude — " + {"light": "Clair", "dark": "Sombre", "system": "Système"}[mode],
        "description": "Habillage Gratitude du dashboard Hermes, navigation native conservée.",
        "palette": {"background": {"hex": colors["background"], "alpha": 1},
                    "midground": {"hex": colors["text"], "alpha": 1},
                    "foreground": {"hex": "#ffffff", "alpha": 0},
                    "warmGlow": "rgba(212,93,54,0.16)", "noiseOpacity": 0},
        "layout": {"radius": "0.75rem", "density": "comfortable"},
        "colorOverrides": overrides(colors), "customCSS": css,
    }


def install_themes(home: Path) -> None:
    destination = home / "dashboard-themes"
    destination.mkdir(mode=0o700, exist_ok=True)
    for mode in ("light", "dark", "system"):
        path = destination / ("gratitude-" + mode + ".yaml")
        # JSON est du YAML valide ; ne jamais écraser une personnalisation.
        if not path.exists():
            with path.open("x", encoding="utf-8") as stream:
                json.dump(theme(mode), stream, ensure_ascii=False, indent=2)
            path.chmod(0o600)


def configure() -> None:
    from hermes_cli.config import atomic_config_write, load_config

    home = Path(os.environ["HERMES_HOME"])
    install_themes(home)
    existing = (home / "config.yaml").exists()
    config = load_config()
    initialized = home / ".yunohost-gratitude-initialized"
    changed = False
    # PM peut créer config.yaml avant ce helper. Son thème générique ne doit
    # pas empêcher l'habillage demandé ; une migration unique préserve ensuite
    # tous les choix de l'utilisateur, y compris un retour à Hermes Teal.
    if not initialized.exists() and config.get("dashboard", {}).get("theme") in (None, "default"):
        config.setdefault("dashboard", {})["theme"] = "gratitude-system"
        changed = True
    if not existing:
        config.setdefault("terminal", {})["cwd"] = str(home)
        changed = True
    if changed:
        atomic_config_write(home / "config.yaml", config)
    if not initialized.exists():
        with initialized.open("x", encoding="utf-8") as stream:
            stream.write("gratitude-initialized-v1\n")
        initialized.chmod(0o600)
    (home / "config.yaml").chmod(0o600)
    for name in (".env", "auth.json"):
        secret_file = home / name
        if secret_file.exists():
            secret_file.chmod(0o600)


if __name__ == "__main__":
    configure()
