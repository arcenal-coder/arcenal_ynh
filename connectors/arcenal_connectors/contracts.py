"""Contrats fermés et validation aux frontières des trois plugins centraux."""

from dataclasses import dataclass
from pathlib import PurePosixPath
import re
from typing import TypedDict
from urllib.parse import urlsplit


class Denied(Exception):
    """Code public stable : ne jamais inclure l'entrée ou l'exception distante."""

    def __init__(self, code="operation_refusee"):
        self.code = code
        super().__init__(code)


def require(condition, code="entree_invalide"):
    if not condition:
        raise Denied(code)


def identifier(value):
    require(isinstance(value, str) and re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", value))
    return value


def fields(value, required, optional=()):
    require(isinstance(value, dict) and set(required) <= value.keys()
            and value.keys() <= set(required) | set(optional))


def service_url(value):
    require(isinstance(value, str) and len(value) <= 512)
    parsed = urlsplit(value)
    require(parsed.scheme == "https" and parsed.hostname and not parsed.username
            and not parsed.password and not parsed.query and not parsed.fragment
            and parsed.port in (None, 443))
    require(not any(part in (".", "..") for part in parsed.path.split("/")))
    require(not any(c in value for c in ("%", "\\", "\r", "\n", "\x00")))
    return value.rstrip("/")


def dav_path(value):
    require(isinstance(value, str) and 0 < len(value) <= 256)
    require(not value.startswith("/") and not value.endswith("/")
            and "//" not in value and not any(c in value for c in ("%", "\\", "\x00", "?", "#", "\r", "\n")))
    require(all(part not in (".", "..") for part in value.split("/")))
    require(str(PurePosixPath(value)) == value)
    return value


@dataclass(frozen=True)
class Operation:
    name: str
    consequence: str
    sensitive: bool = False
    writes: bool = True


class ConnectorSpec(TypedDict):
    plugin: str
    label: str
    operations: dict[str, Operation]


CATALOG: dict[str, ConnectorSpec] = {
    "dolibarr": {
        "plugin": "arcenal-dolibarr", "label": "Dolibarr",
        "operations": {
            "project.read": Operation("Lire un projet autorisé", "Le projet autorisé sera consulté.", writes=False),
            "project.update_link": Operation("Renseigner le lien du projet", "Le seul extrachamp déclaré du projet sera renseigné."),
            "contact.create": Operation("Créer un contact", "Un contact sera créé dans la société autorisée."),
            "contact.delete": Operation("Supprimer un contact", "Le contact sera supprimé.", True),
        },
    },
    "nextcloud": {
        "plugin": "arcenal-nextcloud", "label": "Nextcloud",
        "operations": {
            "file.share_group": Operation("Partager un dossier au groupe autorisé", "Un partage de lecture au groupe déclaré sera créé.", True),
            "file.exists": Operation("Vérifier l'existence d'une cible", "La cible sera vérifiée en lecture.", writes=False),
            "file.mkdir": Operation("Créer un dossier", "Un dossier sera créé dans le sous-arbre autorisé."),
            "file.write": Operation("Écrire un fichier", "Le contenu du fichier sera créé ou remplacé."),
            "file.delete": Operation("Supprimer un fichier ou dossier", "La cible et son éventuel contenu seront supprimés.", True),
        },
    },
    "yunohost": {
        "plugin": "arcenal-yunohost", "label": "YunoHost",
        "operations": {
            "server.inventory": Operation("Consulter l'inventaire YunoHost", "Les identifiants autorisés des applications, services et domaines seront consultés.", writes=False),
            "service.status": Operation("Lire l'état d'un service", "L'état du service sera consulté.", writes=False),
            "service.start": Operation("Démarrer un service", "Le service autorisé sera démarré.", True),
            "service.stop": Operation("Arrêter un service", "Le service et les applications qui en dépendent seront indisponibles.", True),
            "service.restart": Operation("Redémarrer un service", "Le service sera interrompu puis redémarré.", True),
            "backup.create": Operation("Sauvegarder une application", "Une sauvegarde de l'application sera créée.", True),
        },
    },
}


def operation(connector, name):
    require(isinstance(connector, str) and isinstance(name, str) and connector in CATALOG
            and name in CATALOG[connector]["operations"], "operation_non_autorisee")
    return CATALOG[connector]["operations"][name]


def validate_action(connector, name, target, data):
    operation(connector, name)
    require(isinstance(target, str) and isinstance(data, dict))
    if connector == "dolibarr":
        if name.startswith("project."):
            require(re.fullmatch(r"project:[1-9][0-9]{0,9}", target))
            if name == "project.read":
                fields(data, ())
            else:
                fields(data, ("field", "url"))
                require(isinstance(data["field"], str) and re.fullmatch(r"options_[a-z0-9_]{1,48}", data["field"]))
                service_url(data["url"])
            return
        prefix = "company:" if name == "contact.create" else "contact:"
        require(re.fullmatch(re.escape(prefix) + r"[1-9][0-9]{0,9}", target))
        if name == "contact.create":
            fields(data, ("lastname",), ("firstname",))
            require(all(isinstance(v, str) and 0 < len(v) <= 80 and
                        not any(ord(c) < 32 for c in v) for v in data.values()))
        else:
            fields(data, ())
    elif connector == "nextcloud":
        dav_path(target)
        if name == "file.share_group":
            fields(data, ("group",))
            require(isinstance(data["group"], str) and re.fullmatch(r"[a-zA-Z0-9_.@-]{1,64}", data["group"]))
        elif name == "file.write":
            fields(data, ("content",))
            require(isinstance(data["content"], str) and len(data["content"].encode()) <= 8192)
        else:
            fields(data, ())
    else:
        fields(data, ())
        if name == "server.inventory":
            require(target == "server")
        elif name.startswith("service."):
            require(re.fullmatch(r"[a-z][a-z0-9_.@-]{0,79}", target) and not target.endswith(".service"))
        else:
            require(re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", target))


def in_scope(connector, name, target, scope):
    allowed = scope.get(name, [])
    if connector == "nextcloud":
        return any(target == root or target.startswith(root + "/") for root in allowed)
    return target in allowed


def validate_configuration(connector, value):
    require(isinstance(connector, str) and connector in CATALOG, "connecteur_non_autorise")
    fields(value, ("url", "account", "scope"), ("secret", "entity", "share_groups", "project_link_fields"))
    url = service_url(value["url"])
    account = value["account"]
    require(isinstance(account, str) and re.fullmatch(r"arcenal[-_][a-zA-Z0-9_-]{1,48}", account),
            "compte_technique_requis")
    if connector == "yunohost":
        require(account == "arcenal-connectors" and "secret" not in value)
    elif "secret" in value:
        require(isinstance(value["secret"], str) and 8 <= len(value["secret"]) <= 4096
                and not any(c in value["secret"] for c in ("\r", "\n", "\x00")))
    entity = value.get("entity")
    require(entity is None or (connector == "dolibarr" and type(entity) is int and 0 < entity < 1000000))
    scope = value["scope"]
    require(isinstance(scope, dict) and 0 < len(scope) <= len(CATALOG[connector]["operations"]))
    for name, targets in scope.items():
        operation(connector, name)
        require(isinstance(targets, list) and 0 < len(targets) <= 50)
        for target in targets:
            sample = {"lastname": "Validation"} if name == "contact.create" else {}
            if name == "project.update_link":
                sample = {"field": "options_nextcloud_url", "url": "https://nextcloud.test/index.php/f/1"}
            if name == "file.share_group":
                sample = {"group": "arcenal-team"}
            if name == "file.write":
                sample = {"content": ""}
            validate_action(connector, name, target, sample)
    result = {"url": url, "account": account, "scope": scope, "entity": entity}
    for key, app, pattern in (("share_groups", "nextcloud", r"[a-zA-Z0-9_.@-]{1,64}"),
                              ("project_link_fields", "dolibarr", r"options_[a-z0-9_]{1,48}")):
        values = value.get(key, [])
        require(isinstance(values, list) and len(values) <= 20 and
                all(isinstance(item, str) and re.fullmatch(pattern, item) for item in values))
        require(not values or connector == app)
        result[key] = values
    require("file.share_group" not in scope or bool(result["share_groups"]), "groupe_autorise_requis")
    require("project.update_link" not in scope or bool(result["project_link_fields"]), "extrachamp_autorise_requis")
    return result
