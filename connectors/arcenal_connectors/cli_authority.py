"""Validation d'une CLI officielle déclarée par l'hôte, sans shell général."""

import contextlib
import io
import importlib
import json
from pathlib import Path
import re
import runpy
import sys

from .contracts import require


def action(argv, actions):
    require(isinstance(argv, list) and 2 <= len(argv) <= 80 and
            all(isinstance(word, str) and 0 < len(word) <= 2048 and not any(c in word for c in "\r\n\x00") for word in argv))
    node = actions.get(argv[0])
    require(isinstance(node, dict), "commande_yunohost_absente")
    index = 1
    while index < len(argv):
        word = argv[index]
        if word in node.get("actions", {}):
            definition = node["actions"][word]
            path = argv[:index + 1]
            require(path not in (["app", "shell"], ["app", "db"]), "commande_interactive_non_prise_en_charge")
            return definition
        node = node.get("subcategories", {}).get(word)
        require(isinstance(node, dict), "commande_yunohost_absente")
        index += 1
    require(False, "commande_yunohost_absente")


def host_actions():
    # PyYAML est une dépendance de YunoHost, pas du runtime Hermes.
    try:
        yaml = importlib.import_module("yaml")
        value = yaml.safe_load(Path("/usr/share/yunohost/actionsmap.yml").read_text())
    except (ImportError, OSError):
        require(False, "cli_yunohost_ou_parseur_absent")
    require(isinstance(value, dict), "contrat_cli_hote_indisponible")
    return value


def validate(argv, actions, verification=False, generated=()):
    definition = action(argv, actions)
    sensitive_flags = set()
    for flag, descriptor in definition.get("arguments", {}).items():
        descriptor = descriptor if isinstance(descriptor, dict) else {}
        extra = descriptor.get("extra") or {}
        if not isinstance(extra, dict):
            extra = {}
        full = descriptor.get("full", flag)
        if re.search(r"password|secret|token|api.?key|credential", full, re.I) or extra.get("password"):
            sensitive_flags.update((flag, full))
    for word in argv:
        require(word not in ("--debug", "--debug-all"), "journal_debug_interdit_pour_secrets")
        require(not re.search(r"(?:password|secret|token|api_key)\s*[=:]", word, re.I), "secret_serveur_requis")
        if word in sensitive_flags or word.startswith("-") and re.search(r"password|secret|token|api.?key|credential", word, re.I):
            require(word in generated and "=" not in word, "secret_serveur_requis")
    if verification:
        api = definition.get("api", [])
        if isinstance(api, str):
            api = [api]
        require(any(value.startswith("GET ") for value in api), "verification_non_lecture")
    return argv


def subset(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(key in actual and subset(actual[key], value) for key, value in expected.items())
    return actual == expected


def invoke(argv):
    """L'argv Python reste en mémoire : aucun secret dans l'argv OS d'un enfant."""
    previous = sys.argv
    stdout, stderr = io.StringIO(), io.StringIO()
    code = 0
    try:
        sys.argv = ["yunohost", *argv]
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                runpy.run_path("/usr/bin/yunohost", run_name="__main__")
            except SystemExit as exit:
                code = exit.code if type(exit.code) is int else 0 if exit.code is None else 1
    except Exception:
        code = 1
    finally:
        sys.argv = previous
    value = None
    if code == 0:
        try:
            value = json.loads(stdout.getvalue())
        except ValueError:
            pass
    return code, value


def execute(argv, verify_argv, expected, generated_values, actions=None, runner=invoke):
    actions = actions if actions is not None else host_actions()
    validate(argv, actions, generated=generated_values)
    validate(verify_argv, actions, verification=True)
    command = list(argv)
    for flag, value in generated_values.items():
        require(command.count(flag) == 1 and isinstance(value, str) and len(value) >= 16, "secret_serveur_invalide")
        index = command.index(flag)
        require(index + 1 < len(command) and command[index + 1] == "@server-secret", "emplacement_secret_invalide")
        command[index + 1] = value
    code, _ = runner(command)
    if code:
        return {"ok": False, "verified": False, "error": "commande_yunohost_echec"}
    verification = list(verify_argv)
    if "--output-as" not in verification:
        verification.extend(("--output-as", "json"))
    code, actual = runner(verification)
    verified = code == 0 and subset(actual, expected)
    return {"ok": verified, "verified": verified,
            "error": None if verified else "verification_yunohost_echec"}
