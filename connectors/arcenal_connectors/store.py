"""Coffre chiffré indépendant par profil et audit authentifié, sans export de secret."""

from contextlib import closing, contextmanager
import hashlib
import hmac
import json
import os
from pathlib import Path
import sqlite3
import threading
import time
import uuid

from cryptography.fernet import Fernet, InvalidToken

from .contracts import (CATALOG, Denied, identifier, in_scope, operation,
                        require, validate_action, validate_configuration)
from .inventory import validate_inventory


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class Store:
    def __init__(self, root, profile, plugins, clock=time.time):
        self.profile = identifier(profile)
        self.plugins = plugins
        self.clock = clock
        self.lock = threading.RLock()
        self.home = Path(root) / profile
        require(not self.home.is_symlink(), "coffre_indisponible")
        self.home.mkdir(parents=True, mode=0o700, exist_ok=True)
        self.home.chmod(0o700)
        key_file = self.home / "vault.key"
        require(not key_file.is_symlink(), "coffre_indisponible")
        if not key_file.exists():
            require(not (self.home / "vault.sqlite").exists(), "cle_du_coffre_absente")
            fd = os.open(key_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(Fernet.generate_key())
                stream.flush()
                os.fsync(stream.fileno())
        key_file.chmod(0o600)
        self.key = key_file.read_bytes()
        self.cipher = Fernet(self.key)
        self.path = self.home / "vault.sqlite"
        require(not self.path.is_symlink(), "coffre_indisponible")
        with closing(sqlite3.connect(self.path)) as db, db:
            version = db.execute("pragma user_version").fetchone()[0]
            require(version in (0, 1), "schema_du_coffre_incompatible")
            db.execute("create table if not exists items (kind text, id text, value blob not null, primary key(kind,id))")
            db.execute("create table if not exists audit (seq integer primary key, event text not null, signature text not null)")
            db.execute("pragma user_version=1")
        self.path.chmod(0o600)

    def _read(self, db, kind, key, default=None):
        row = db.execute("select value from items where kind=? and id=?", (kind, key)).fetchone()
        if row is None:
            return default
        try:
            return json.loads(self.cipher.decrypt(row[0]))
        except (InvalidToken, ValueError):
            raise Denied("coffre_altere") from None

    def _write(self, db, kind, key, value):
        encrypted = self.cipher.encrypt(canonical(value).encode())
        db.execute("insert or replace into items values (?,?,?)", (kind, key, encrypted))

    def _items(self, db, kind):
        return [(row[0], self._read(db, kind, row[0])) for row in
                db.execute("select id from items where kind=?", (kind,)).fetchall()]

    def _verify(self, db):
        previous = ""
        for _, event, signature in db.execute("select seq,event,signature from audit order by seq"):
            expected = hmac.new(self.key, (previous + event).encode(), hashlib.sha256).hexdigest()
            require(hmac.compare_digest(signature, expected), "audit_altere")
            previous = signature

    def _audit(self, db, event, actor, connector=None, request_id=None):
        # Les seules valeurs variables sont des identités authentifiées et IDs opaques.
        request = self._read(db, "request", request_id) if request_id else None
        value = canonical({"event": event, "actor": actor, "connector": connector,
                           "request_id": request_id, "time": self.clock(),
                           "operation": request["operation"] if request else None,
                           "target_hash": fingerprint(request["target"]) if request else None})
        row = db.execute("select signature from audit order by seq desc limit 1").fetchone()
        signature = hmac.new(self.key, ((row[0] if row else "") + value).encode(), hashlib.sha256).hexdigest()
        db.execute("insert into audit(event,signature) values (?,?)", (value, signature))

    @contextmanager
    def transaction(self, actor):
        with self.lock:
            db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
            try:
                db.execute("pragma synchronous=FULL")
                db.execute("begin immediate")
                self._verify(db)
                try:
                    yield db
                except Denied:
                    db.rollback()
                    db.execute("begin immediate")
                    self._verify(db)
                    self._audit(db, "refus", actor)
                    db.commit()
                    raise
                else:
                    db.commit()
            except sqlite3.Error:
                db.rollback()
                raise Denied("audit_ou_coffre_indisponible") from None
            finally:
                db.close()

    def _no_secret(self, db, value, extra=()):
        text = canonical(value)
        secrets = [c.get("secret") for _, c in self._items(db, "connector")]
        secrets.extend(d.get("secret") for _, d in self._items(db, "change"))
        require(not any(secret and canonical(secret)[1:-1] in text for secret in [*secrets, *extra]),
                "donnee_sensible_refusee")

    def list(self, actor):
        with self.transaction(actor) as db:
            connectors = []
            for name, spec in CATALOG.items():
                value = self._read(db, "connector", name, {})
                connectors.append({"id": name, "label": spec["label"], "plugin": spec["plugin"],
                                   "state": value.get("state", "non_configure"),
                                   "config": value.get("config"), "last_test": value.get("last_test"),
                                   "last_used": value.get("last_used"), "revision": value.get("revision", 0),
                                   "has_secret": bool(value.get("secret"))})
            requests = [self._public_request(v, self._read(db, "connector", v["connector"], {})) for _, v in self._items(db, "request")
                        if v["state"] == "pending" and v["expires"] > self.clock()]
            grants = [{k: v[k] for k in ("id", "connector", "operation", "target", "mode", "expires", "revoked", "validator")}
                      for _, v in self._items(db, "grant")]
            return {"profile": self.profile, "actor": actor, "connectors": connectors,
                    "requests": requests, "grants": grants, "catalog": {
                        c: {name: {"label": op.name, "consequence": op.consequence, "sensitive": op.sensitive}
                            for name, op in spec["operations"].items()} for c, spec in CATALOG.items()}}

    def plan_configuration(self, actor, connector, value):
        config = validate_configuration(connector, value)
        with self.transaction(actor) as db:
            self._no_secret(db, config, (value.get("secret"),))
            previous = self._read(db, "connector", connector)
            require(not previous or connector == "yunohost" or
                    previous["config"]["url"] == config["url"] or "secret" in value,
                    "nouveau_secret_requis_pour_changer_url")
            secret = value.get("secret", (previous or {}).get("secret"))
            require(connector == "yunohost" or bool(secret), "secret_requis")
            change_id = uuid.uuid4().hex
            self._write(db, "change", change_id, {"connector": connector, "config": config,
                        "secret": secret, "creator": actor, "expires": self.clock() + 900,
                        "revision": (previous or {}).get("revision", 0)})
            self._audit(db, "configuration_demandee", actor, connector, change_id)
            return {"id": change_id, "connector": connector, "config": config,
                    "secret_changed": "secret" in value, "consequence": "Remplacer la configuration et invalider les autorisations antérieures.",
                    "validator": actor}

    def confirm_configuration(self, actor, change_id, accept):
        require(type(accept) is bool)
        with self.transaction(actor) as db:
            change = self._read(db, "change", change_id)
            require(change and change["expires"] > self.clock(), "demande_expiree")
            connector = change["connector"]
            old = self._read(db, "connector", connector, {})
            require(old.get("revision", 0) == change["revision"], "configuration_modifiee")
            if accept:
                self._write(db, "connector", connector, {"config": change["config"], "secret": change["secret"],
                            "state": "a_tester", "revision": change["revision"] + 1, "last_test": None,
                            "last_used": old.get("last_used"), "always": old.get("always", [])})
            db.execute("delete from items where kind='change' and id=?", (change_id,))
            self._audit(db, "configuration_validee" if accept else "configuration_refusee", actor, connector, change_id)
            return {"ok": True}

    def manage(self, actor, connector, action, confirmed=False):
        require(connector in CATALOG and action in ("test", "disable", "revoke_secret"))
        with self.lock:
            with self.transaction(actor) as db:
                value = self._read(db, "connector", connector)
                require(value is not None, "connecteur_non_configure")
                if action == "test":
                    require(value["state"] != "desactive", "connecteur_desactive")
                    self._audit(db, "test_demande", actor, connector)
                else:
                    require(confirmed is True, "validation_humaine_requise")
                    value["state"] = "desactive"
                    value["revision"] += 1
                    if action == "revoke_secret":
                        value["secret"] = None
                    self._write(db, "connector", connector, value)
                    self._audit(db, "secret_revoque" if action == "revoke_secret" else "desactivation", actor, connector)
                    return {"ok": True}
        ok = True
        try:
            self.plugins[connector].test(value["config"], value["secret"], self.profile)
        except Exception:
            # Ni exception distante ni corps HTTP ne franchissent la frontière.
            ok = False
        with self.transaction(actor) as db:
            current = self._read(db, "connector", connector)
            if current["revision"] != value["revision"] or current["state"] == "desactive":
                self._audit(db, "test_obsolete", actor, connector)
                return {"ok": False}
            current["state"] = "connecte" if ok else "erreur"
            current["last_test"] = {"time": self.clock(), "ok": ok}
            self._write(db, "connector", connector, current)
            self._audit(db, "test_reussi" if ok else "test_echec", actor, connector)
        return {"ok": ok}

    def _public_request(self, value, connector):
        op = operation(value["connector"], value["operation"])
        return {k: value[k] for k in ("id", "connector", "operation", "target", "data", "session", "expires", "state")} | {
            "label": op.name, "consequence": op.consequence,
            "always_required": op.sensitive or value["operation"] in connector.get("always", [])}

    def _active_connector(self, db, name):
        value = self._read(db, "connector", name)
        require(value and value["state"] == "connecte", "connecteur_non_connecte")
        return value

    def initialize_yunohost(self, url, scope):
        """Enrôlement local par l'installateur root, sans secret ni action distante."""
        with self.transaction("installation") as db:
            if self._read(db, "connector", "yunohost") is not None:
                return False
            config = validate_configuration("yunohost", {"url": url, "account": "arcenal-connectors",
                                                        "scope": {name: targets for name, targets in scope.items() if targets}})
            self._write(db, "connector", "yunohost", {"config": config, "secret": None, "native": True,
                        "state": "a_tester", "revision": 1, "last_test": None, "last_used": None, "always": []})
            self._audit(db, "yunohost_natif_initialise", "installation", "yunohost")
        return True

    def _test_native_yunohost(self):
        with self.transaction("agent") as db:
            value = self._read(db, "connector", "yunohost", {})
            test_required = value.get("native") is True and value.get("state") == "a_tester"
        if test_required:
            self.manage("agent", "yunohost", "test")

    def _grant_matches(self, grant, request):
        return (not grant["revoked"] and grant["expires"] > self.clock()
                and all(grant[k] == request[k] for k in ("connector", "revision", "operation", "target"))
                and (grant["mode"] == "session" and grant["session"] == request["session"]
                     or grant["mode"] == "limited" and grant["data_hash"] == fingerprint(request["data"])))

    def propose(self, connector, name, target, data, session):
        validate_action(connector, name, target, data)
        require(isinstance(session, str) and 1 <= len(session) <= 128
                and all(c.isalnum() or c in "_-" for c in session))
        if connector == "yunohost":
            self._test_native_yunohost()
        with self.lock:
            with self.transaction("agent") as db:
                self._no_secret(db, {"target": target, "data": data, "session": session})
                require(not self._read(db, "closed_session", session), "session_terminee")
                value = self._active_connector(db, connector)
                require(in_scope(connector, name, target, value["config"]["scope"]), "hors_perimetre")
                request = {"id": uuid.uuid4().hex, "connector": connector, "operation": name,
                           "target": target, "data": data, "session": session, "revision": value["revision"],
                           "expires": self.clock() + 900, "state": "pending"}
                op = operation(connector, name)
                grant = None
                if op.writes and not op.sensitive and name not in value["always"]:
                    grant = next((g for _, g in self._items(db, "grant") if self._grant_matches(g, request)), None)
                self._write(db, "request", request["id"], request)
                self._audit(db, "demande", "agent", connector, request["id"])
                if not op.writes or grant:
                    self._reserve(db, request, value)
                else:
                    self._write(db, "request", request["id"], request)
                    return {"id": request["id"], "state": "pending", "approval_required": True}
        return self._execute(request, value)

    def _reserve(self, db, request, value):
        request["state"] = "executing"
        self._write(db, "request", request["id"], request)
        value["last_used"] = self.clock()
        self._write(db, "connector", request["connector"], value)
        self._audit(db, "execution_reservee", "server", request["connector"], request["id"])

    def _execute(self, request, value):
        # La réservation est consommée et journalisée AVANT l'I/O. Ne pas garder
        # le verrou pendant le réseau : une révocation doit bloquer les nouvelles
        # réservations immédiatement, sans attendre un appel déjà accepté/en vol.
        ok = True
        result = {"ok": True}
        try:
            result = self.plugins[request["connector"]].execute(value["config"], value["secret"],
                        request["operation"], request["target"], request["data"], self.profile, request_id=request["id"])
            if request["connector"] == "yunohost" and request["operation"] == "server.inventory":
                result = {"ok": True, "inventory": validate_inventory(result.get("inventory"))}
        except Exception:
            ok = False
        request["state"] = "done" if ok else "error"
        # Le retour des plugins n'est pas propagé librement.
        public = {"id": request["id"], "state": request["state"], "ok": ok,
                "service_state": result.get("state") if result.get("state") in ("active", "inactive", "failed") else None}
        if ok and request["connector"] == "yunohost" and request["operation"] == "server.inventory":
            public["inventory"] = result["inventory"]
        with self.transaction("server") as db:
            request["result"] = public
            self._write(db, "request", request["id"], request)
            self._audit(db, "execution_reussie" if ok else "execution_echec", "server", request["connector"], request["id"])
        return public

    def action_status(self, request_id):
        require(isinstance(request_id, str) and len(request_id) == 32
                and all(c in "0123456789abcdef" for c in request_id))
        with self.transaction("agent") as db:
            request = self._read(db, "request", request_id)
            require(request and request["connector"] == "yunohost", "demande_absente")
            if "result" in request:
                return request["result"]
            state = request["state"]
            if state == "pending" and request["expires"] <= self.clock():
                state = "expired"
            return {"id": request_id, "state": state, "approval_required": state == "pending"}

    def recover_interrupted(self):
        """Au démarrage du service uniquement : ne jamais rejouer une réservation."""
        with self.transaction("server") as db:
            for key, request in self._items(db, "request"):
                if request["state"] != "executing":
                    continue
                request["state"] = "unknown"
                request["result"] = {"id": key, "state": "unknown", "ok": False,
                                     "error": "verification_manuelle_requise"}
                self._write(db, "request", key, request)
                self._audit(db, "execution_interrompue", "server", request["connector"], key)

    def decide(self, actor, request_id, accept, mode="once", expires=None):
        require(type(accept) is bool and mode in ("once", "session", "limited", "always"))
        with self.lock:
            with self.transaction(actor) as db:
                request = self._read(db, "request", request_id)
                require(request and request["state"] == "pending" and request["expires"] > self.clock(), "demande_inactive")
                require(not self._read(db, "closed_session", request["session"]), "session_terminee")
                value = self._active_connector(db, request["connector"])
                require(value["revision"] == request["revision"], "configuration_modifiee")
                require(in_scope(request["connector"], request["operation"], request["target"], value["config"]["scope"]), "hors_perimetre")
                if not accept:
                    request["state"] = "denied"
                    self._write(db, "request", request_id, request)
                    self._audit(db, "refusee", actor, request["connector"], request_id)
                    return {"ok": True, "state": "denied"}
                op = operation(request["connector"], request["operation"])
                sensitive = op.sensitive or request["operation"] in value["always"]
                require(not sensitive or mode in ("once", "always"), "validation_unique_obligatoire")
                if mode == "limited":
                    require(isinstance(expires, (int, float)) and not isinstance(expires, bool)
                            and self.clock() < expires <= self.clock() + 604800,
                            "expiration_invalide")
                if mode in ("session", "limited"):
                    grant = {k: request[k] for k in ("connector", "revision", "operation", "target", "session")}
                    grant.update(id=uuid.uuid4().hex, mode=mode, validator=actor, revoked=False,
                                 data_hash=fingerprint(request["data"]),
                                 expires=expires if mode == "limited" else self.clock() + 28800)
                    self._write(db, "grant", grant["id"], grant)
                if mode == "always" and request["operation"] not in value["always"]:
                    value["always"].append(request["operation"])
                self._audit(db, "validee_" + mode, actor, request["connector"], request_id)
                self._reserve(db, request, value)
        return self._execute(request, value)

    def revoke(self, actor, grant_id, confirmed=False):
        require(confirmed is True, "validation_humaine_requise")
        with self.transaction(actor) as db:
            grant = self._read(db, "grant", grant_id)
            require(grant is not None, "delegation_absente")
            grant["revoked"] = True
            self._write(db, "grant", grant_id, grant)
            self._audit(db, "delegation_revoquee", actor, grant["connector"], grant_id)
            return {"ok": True}

    def end_session(self, session):
        require(isinstance(session, str) and 1 <= len(session) <= 128
                and all(c.isalnum() or c in "_-" for c in session))
        with self.transaction("agent") as db:
            self._no_secret(db, session)
            self._write(db, "closed_session", session, True)
            for key, grant in self._items(db, "grant"):
                if grant["mode"] == "session" and grant["session"] == session and not grant["revoked"]:
                    grant["revoked"] = True
                    self._write(db, "grant", key, grant)
                    self._audit(db, "autorisation_session_terminee", "agent", grant["connector"], key)
            for key, request in self._items(db, "request"):
                if request["session"] == session and request["state"] == "pending":
                    request["state"] = "closed"
                    self._write(db, "request", key, request)
                    self._audit(db, "session_cloturee", "agent", request["connector"], key)
            self._audit(db, "session_terminee", "agent")
        return {"ok": True}

    def audit(self, actor, connector):
        require(connector in CATALOG)
        with self.transaction(actor) as db:
            rows = db.execute("select event from audit order by seq desc limit 500").fetchall()
            return {"events": [event for (text,) in rows if (event := json.loads(text))["connector"] == connector]}
