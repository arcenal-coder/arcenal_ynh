"""Définition fermée du flux projet : aucune commande ni expression exécutable."""

import re

from .contracts import dav_path, fields, identifier, require


ACTION_REGISTRY = {
    "dolibarr:project.read": {"category": "read", "authorization": "activated_definition"},
    "nextcloud:file.mkdir": {"category": "business", "authorization": "activated_definition", "scope": "declared_paths"},
    "nextcloud:file.share_group": {"category": "business", "authorization": "activated_definition", "scope": "one_group_read_only"},
    "dolibarr:project.update_link": {"category": "business", "authorization": "activated_definition", "scope": "one_declared_extrafield"},
}
ACTIONS = tuple(ACTION_REGISTRY)


def definition(value):
    fields(value, ("id", "projects", "status_field", "from_status", "to_statuses", "base_folder",
                   "folders", "share_group", "link_field", "interval", "ksaar_required"))
    identifier(value["id"])
    require(isinstance(value["projects"], list) and 0 < len(value["projects"]) <= 20)
    require(all(isinstance(p, str) and re.fullmatch(r"[1-9][0-9]{0,9}", p) for p in value["projects"]))
    require(isinstance(value["status_field"], str) and (value["status_field"] in ("statut", "opp_status") or
            re.fullmatch(r"array_options\.options_[a-z0-9_]{1,48}", value["status_field"])))
    require(isinstance(value["from_status"], str) and 0 < len(value["from_status"]) <= 80)
    require(isinstance(value["to_statuses"], list) and 0 < len(value["to_statuses"]) <= 20
            and all(isinstance(v, str) and 0 < len(v) <= 80 and v != value["from_status"] for v in value["to_statuses"]))
    dav_path(value["base_folder"])
    require(isinstance(value["folders"], list) and len(value["folders"]) <= 12)
    for name in value["folders"]:
        dav_path(name)
        require("/" not in name, "sous_dossier_simple_requis")
    require(isinstance(value["share_group"], str) and re.fullmatch(r"[a-zA-Z0-9_.@-]{1,64}", value["share_group"]))
    require(isinstance(value["link_field"], str) and re.fullmatch(r"options_[a-z0-9_]{1,48}", value["link_field"]))
    require(type(value["interval"]) is int and 30 <= value["interval"] <= 3600)
    require(type(value["ksaar_required"]) is bool)
    result = dict(value)
    result["projects"] = sorted(set(value["projects"]))
    result["folders"] = sorted(set(value["folders"]))
    result["to_statuses"] = sorted(set(value["to_statuses"]))
    return result


def paths(spec, project_id):
    root = spec["base_folder"] + "/project-" + project_id
    return [root, *[root + "/" + name for name in spec["folders"]]]
