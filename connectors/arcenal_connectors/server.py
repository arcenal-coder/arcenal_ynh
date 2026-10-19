"""Deux surfaces HTTP sur sockets Unix distincts : humain et agent."""

import argparse
import grp
from http.server import BaseHTTPRequestHandler
import json
import os
from pathlib import Path
import socketserver
import socket
import struct
import threading
from urllib.parse import parse_qs, urlsplit

from .contracts import Denied, fields, identifier, require
from .network import Network
from .plugins import registry
from .plugins.yunohost import LocalHelper
from .store import Store


class Authority:
    def __init__(self, config_file, plugins=None, clock=None):
        self.config_file = Path(config_file)
        self.plugins = plugins
        self.clock = clock
        self.stores = {}
        self.lock = threading.Lock()

    def settings(self):
        try:
            return json.loads(self.config_file.read_text())
        except (OSError, ValueError):
            raise Denied("autorite_indisponible") from None

    def store(self, profile, settings):
        identifier(profile)
        with self.lock:
            plugins = self.plugins or registry(Network(settings.get("allowed_private_networks", [])), LocalHelper())
            if profile not in self.stores:
                options = {"clock": self.clock} if self.clock else {}
                self.stores[profile] = Store(settings["vault_root"], profile, plugins, **options)
            else:
                self.stores[profile].plugins = plugins
            return self.stores[profile]

    def health(self):
        settings = self.settings()
        require(settings.get("schema") == 1 and settings.get("profile_uids"), "autorite_non_provisionnee")
        for profile in settings["profile_uids"]:
            self.store(profile, settings).list("health")
        return {"ready": True}

    def recover_interrupted(self):
        settings = self.settings()
        for profile in settings.get("profile_uids", {}):
            self.store(profile, settings).recover_interrupted()

    def dispatch(self, surface, headers, method, url, body, peer_uid=None):
        headers = {k.lower(): v for k, v in headers.items()}
        settings = self.settings()  # Révocations d'identité prises en compte à chaque appel.
        parsed = urlsplit(url)
        query = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True)
        require(query.keys() <= {"profile"} and len(query.get("profile", [])) <= 1)
        parts = parsed.path.strip("/").split("/")
        require(parts[0] == "v1" and len(parts) <= 4)
        if surface == "admin":
            # X-ARCenal-User est remplacé par Nginx depuis YNH_USER fourni par SSOwat.
            actor = headers.get("x-arcenal-user", "")
            principal = settings.get("principals", {}).get(actor)
            require(principal and principal.get("role") == "admin", "administrateur_requis")
            if method == "GET" and parts == ["v1", "identity"] and not query:
                return {"actor": actor, "profiles": principal.get("profiles", [])}
            profile = query.get("profile", ["default"])[0]
            require(profile in principal.get("profiles", []), "profil_non_autorise")
            if method != "GET":
                require(headers.get("origin") == settings["origin"]
                        and headers.get("x-arcenal-intent") == "manage", "origine_refusee")
        else:
            require(surface == "agent" and not query, "surface_refusee")
            actor = "agent"
            require(type(peer_uid) is int and peer_uid > 0, "identite_systeme_du_client_refusee")
            profiles = [name for name, uid in settings.get("profile_uids", {}).items() if uid == peer_uid]
            require(len(profiles) == 1, "identite_systeme_du_client_refusee")
            profile = profiles[0]
        store = self.store(profile, settings)
        require(method in ("GET", "POST"))
        if method == "GET":
            require(surface == "admin", "surface_refusee")
            if parts == ["v1", "state"]:
                return store.list(actor)
            if len(parts) == 3 and parts[:2] == ["v1", "audit"]:
                return store.audit(actor, parts[2])
        if method == "POST":
            require(isinstance(body, dict))
            if surface == "agent":
                if parts == ["v1", "actions", "status"]:
                    fields(body, ("id",))
                    return store.action_status(body["id"])
                if parts == ["v1", "actions"]:
                    fields(body, ("connector", "operation", "target", "data", "session"))
                    return store.propose(body["connector"], body["operation"], body["target"], body["data"], body["session"])
                if parts == ["v1", "sessions", "end"]:
                    fields(body, ("session",))
                    return store.end_session(body["session"])
                raise Denied("surface_refusee")
            if parts == ["v1", "configuration"]:
                fields(body, ("connector", "config"))
                if body["connector"] == "yunohost":
                    require(body["config"].get("url", "").rstrip("/") == "https://" + urlsplit(settings["origin"]).hostname,
                            "serveur_yunohost_non_autorise")
                return store.plan_configuration(actor, body["connector"], body["config"])
            if len(parts) == 4 and parts[1] == "configuration" and parts[3] == "decision":
                fields(body, ("accept",))
                return store.confirm_configuration(actor, parts[2], body["accept"])
            if len(parts) == 4 and parts[1] == "actions" and parts[3] == "decision":
                fields(body, ("accept",), ("mode", "expires"))
                return store.decide(actor, parts[2], body["accept"], body.get("mode", "once"), body.get("expires"))
            if len(parts) == 4 and parts[1] == "connectors":
                fields(body, (), ("confirmed",))
                return store.manage(actor, parts[2], parts[3], body.get("confirmed", False))
            if len(parts) == 4 and parts[1] == "grants" and parts[3] == "revoke":
                fields(body, ("confirmed",))
                return store.revoke(actor, parts[2], body["confirmed"])
        raise Denied("route_absente")


def handler(authority, surface, asset_root=None):
    assets_root = Path(asset_root) if asset_root is not None else Path(__file__).parent / "ui"
    class Handler(BaseHTTPRequestHandler):
        server_version = "ARCenalConnectors"

        def log_message(self, format, *args):
            return  # Aucun chemin, header, secret ou corps dans un access log.

        def do_GET(self):
            self.respond("GET")

        def do_POST(self):
            self.respond("POST")

        def send_error(self, code, message=None, explain=None):
            self.write_response(code, b'{"error":"requete_http_invalide"}', "application/json")

        def respond(self, method):
            self.connection.settimeout(15)
            status = 200
            mime = "application/json; charset=utf-8"
            try:
                if surface == "admin" and method == "GET" and self.path == "/v1/health":
                    self.write_response(200, json.dumps(authority.health()).encode(), mime)
                    return
                assets = {"/": ("index.html", "text/html; charset=utf-8"),
                          "/app.js": ("app.js", "text/javascript; charset=utf-8"), "/style.css": ("style.css", "text/css")}
                if surface == "admin" and method == "GET" and self.path in assets:
                    authority.dispatch(surface, dict(self.headers), "GET", "/v1/identity", None)
                    name, mime = assets[self.path]
                    content = (assets_root / name).read_bytes()
                    self.write_response(200, content, mime)
                    return
                length = int(self.headers.get("Content-Length", "0"))
                require(0 <= length <= 32768 and not self.headers.get("Transfer-Encoding"))
                body = None
                if method == "POST":
                    require(self.headers.get_content_type() == "application/json")
                    body = json.loads(self.rfile.read(length))
                peer_uid = None
                if surface == "agent":
                    if hasattr(socket, "SO_PEERCRED"):
                        peer_uid = struct.unpack("3i", self.connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[1]
                    elif hasattr(self.connection, "getpeereid"):
                        peer_uid = self.connection.getpeereid()[0]
                    else:
                        raise Denied("identite_systeme_indisponible")
                result = authority.dispatch(surface, dict(self.headers), method, self.path, body, peer_uid=peer_uid)
            except Denied as error:
                result, status = {"error": error.code}, 403
                print(json.dumps({"event": "refus_api", "surface": surface, "code": error.code}), flush=True)
            except Exception:
                result, status = {"error": "requete_ou_service_indisponible"}, 503
            content = json.dumps(result, ensure_ascii=False).encode()
            self.write_response(status, content, mime)

        def write_response(self, status, content, mime):
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'; form-action 'self'")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Cross-Origin-Opener-Policy", "same-origin")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(content)
    return Handler


class UnixServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def main():
    require(os.geteuid() != 0, "autorite_non_root_requise")
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--runtime", default="/run/arcenal-connectors")
    args = parser.parse_args()
    authority = Authority(args.config)
    authority.recover_interrupted()
    servers = []
    for surface, group in (("admin", "www-data"), ("agent", "arcenal")):
        path = Path(args.runtime) / (surface + ".sock")
        if path.exists():
            require(path.is_socket(), "socket_invalide")
            path.unlink()
        server = UnixServer(str(path), handler(authority, surface))
        os.chown(path, -1, grp.getgrnam(group).gr_gid)
        path.chmod(0o660)
        servers.append(server)
        threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        threading.Event().wait()
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
