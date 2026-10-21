"""Clients plugins Hermes : demande seulement, jamais validation ni secret métier."""

import http.client
import json
import re
import socket
import secrets
import threading

from .contracts import CATALOG, Denied, fields, validate_action


_sessions = {}
_session_lock = threading.Lock()


def session_key(session_id, close=False):
    # Un UID/runtime = un client central. Les hooks de clôture peuvent être
    # émis hors d'un scope de profil Hermes : ne pas dériver la clé de l'env.
    key = session_id
    with _session_lock:
        if close:
            return _sessions.pop(key, None)
        return _sessions.setdefault(key, session_id + "_" + secrets.token_hex(12))


class UnixConnection(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect("/run/arcenal-connectors/agent.sock")


def call(path, body):
    connection = UnixConnection("localhost", timeout=15)
    try:
        connection.request("POST", path, body=json.dumps(body), headers={
            "Content-Type": "application/json"})
        response = connection.getresponse()
        content = response.read(65537)
        if len(content) > 65536:
            return {"error": "autorite_indisponible"}
        return json.loads(content)
    except Exception:
        return {"error": "autorite_indisponible"}
    finally:
        connection.close()


def register(ctx, connector):
    operations = list(CATALOG[connector]["operations"])
    if connector == "yunohost":
        operations.append("action.status")
        from .yunohost_prompt import CONTENT
        ctx.register_system_prompt_section("arcenal.yunohost", CONTENT, position="after_memory", max_chars=2000)

    def propose(args, **kwargs):
        try:
            fields(args, ("operation", "target", "data"))
            status_query = connector == "yunohost" and args["operation"] == "action.status"
            if status_query:
                if not isinstance(args["target"], str) or not re.fullmatch(r"[a-f0-9]{32}", args["target"]) or args["data"] != {}:
                    raise Denied("arguments_non_autorises")
            else:
                validate_action(connector, args["operation"], args["target"], args["data"])
        except (Denied, ValueError, TypeError):
            return json.dumps({"error": "arguments_non_autorises"})
        session = kwargs.get("session_id")
        if not session:
            return json.dumps({"error": "session_requise"})
        if status_query:
            return json.dumps(call("/v1/actions/status", {"id": args["target"]}))
        # Le session_id vient du runtime, jamais des arguments du modèle.
        body = {"connector": connector, "operation": args.get("operation"),
                "target": args.get("target"), "data": args.get("data", {}), "session": session_key(session)}
        return json.dumps(call("/v1/actions", body))

    def end(session_id=None, **kwargs):
        if session_id:
            key = session_key(session_id, close=True)
            if key:
                call("/v1/sessions/end", {"session": key})

    ctx.register_tool(
        name="arcenal_" + connector,
        toolset="arcenal_" + connector,
        schema={"name": "arcenal_" + connector,
                "description": ("Administrer YunoHost nativement : inventaire, état/démarrage/arrêt/redémarrage des services, sauvegarde et suivi d'une demande. Mutations validées humainement."
                                if connector == "yunohost" else "Demander une opération au connecteur central autorisé. Les écritures attendent une validation humaine dans Connecteurs."),
                "parameters": {"type": "object", "additionalProperties": False,
                               "properties": {"operation": {"type": "string", "enum": operations},
                                              "target": {"type": "string", "description": {
                                                  "dolibarr": "company:123 pour créer ; contact:45 pour supprimer.",
                                                  "nextcloud": "Chemin DAV relatif dans un sous-arbre autorisé, sans / initial.",
                                                  "yunohost": "server pour l'inventaire ; nom exact pour un service/application ; identifiant de demande pour action.status."}[connector]},
                                              "data": {"type": "object", "additionalProperties": False,
                                                       "description": {
                                                           "dolibarr": "contact.create exige lastname ; firstname est facultatif. Objet vide pour supprimer.",
                                                           "nextcloud": "file.write exige content (texte, 8 Kio maximum). Objet vide pour les autres opérations.",
                                                           "yunohost": "Objet vide ; aucun argument système libre."}[connector],
                                                       "properties": {name: {"type": "string"} for name in {
                                                           "dolibarr": ("lastname", "firstname", "field", "url"),
                                                           "nextcloud": ("content", "group"), "yunohost": ()}[connector]}}},
                               "required": ["operation", "target", "data"]}},
        handler=propose,
    )
    # on_session_end est aussi émis à chaque tour par v0.22.2 : ce n'est pas
    # la frontière de conversation. Les deux hooks ci-dessous le sont.
    ctx.register_hook("on_session_finalize", end)
    ctx.register_hook("on_session_reset", end)
