"""Assistance v1 state, independent of Hermes tools and administrative actions."""
import hashlib
import hmac
import json
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

CONFIG = Path("/etc/arcenal-assistance/agent.json")
MODULES = {"materiel": "Matériel", "epi": "EPI", "dosimetres": "Dosimètres passifs"}


class LinkError(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def configuration():
    try:
        return json.loads(CONFIG.read_text())
    except (OSError, ValueError):
        return {}


def authenticate(application, authorization):
    entry = configuration().get("applications", {}).get(application)
    if not entry or not hmac.compare_digest(authorization, "Bearer " + entry["key"]):
        raise LinkError("Identité applicative invalide.")
    return entry


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


@contextmanager
def database():
    base = Path(configuration()["state_dir"])
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = base / "assistance.sqlite3"
    with sqlite3.connect(path, timeout=5) as db:
        path.chmod(0o600)
        db.row_factory = sqlite3.Row
        db.execute("CREATE TABLE IF NOT EXISTS pairs (id TEXT PRIMARY KEY, application TEXT, state TEXT, expires REAL)")
        db.execute("CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, pair_id TEXT, user TEXT, ticket TEXT, expires REAL)")
        db.execute("CREATE TABLE IF NOT EXISTS confirmations (id TEXT PRIMARY KEY, pair_id TEXT, user TEXT, expires REAL)")
        db.execute("BEGIN IMMEDIATE")
        db.execute("DELETE FROM requests WHERE expires < ?", (time.time(),))
        db.execute("DELETE FROM confirmations WHERE expires < ?", (time.time(),))
        yield db


def pair_row(db, pair_id, application=None):
    row = db.execute("SELECT * FROM pairs WHERE id=?", (pair_id,)).fetchone()
    if row is None or (application is not None and row["application"] != application):
        raise LinkError("Liaison inconnue.")
    return row


def active(row):
    return row["state"] == "active" and row["expires"] > time.time()


def exchange(application, entry, payload):
    operation = payload.get("operation")
    fields = {"operation", "application", "pair_id"}
    if operation == "request":
        fields |= {"user", "ticket"}
    if set(payload) - fields:
        raise LinkError("Contexte ou action non autorisé.")
    with database() as db:
        if operation == "pair":
            db.execute("UPDATE pairs SET state='revoked' WHERE application=?", (application,))
            pair_id = secrets.token_urlsafe(32)
            db.execute("INSERT INTO pairs VALUES (?, ?, 'pending', ?)", (pair_id, application, time.time() + 600))
            return {"state": "pending", "pair_id": pair_id}
        row = pair_row(db, payload.get("pair_id", ""), application)
        if operation == "status":
            return {"state": row["state"] if row["expires"] > time.time() else "expired"}
        if operation == "revoke":
            db.execute("UPDATE pairs SET state='revoked' WHERE id=?", (row["id"],))
            return {"state": "revoked"}
        if operation != "request" or not active(row):
            raise LinkError("Liaison inactive ou action centrale interdite.")
        user, ticket = payload.get("user", ""), payload.get("ticket", "")
        if not isinstance(user, str) or not 1 <= len(user) <= 128 or not isinstance(ticket, str) or not 1 <= len(ticket) <= 2048:
            raise LinkError("Contexte invalide.")
        reference = secrets.token_urlsafe(32)
        db.execute("INSERT INTO requests VALUES (?, ?, ?, ?, ?)", (digest(reference), row["id"], user, ticket, time.time() + 60))
        return {"reference": reference}


def prepare_confirmation(pair_id, user):
    nonce = secrets.token_urlsafe(32)
    with database() as db:
        row = pair_row(db, pair_id)
        if row["state"] not in ("pending", "active") or row["expires"] <= time.time():
            raise LinkError("Demande expirée ou révoquée.")
        db.execute("INSERT INTO confirmations VALUES (?, ?, ?, ?)", (digest(nonce), pair_id, user, time.time() + 300))
    return nonce


def confirm(pair_id, user, nonce, decision):
    if decision not in ("approve", "revoke"):
        raise LinkError("Décision inconnue.")
    with database() as db:
        confirmation = db.execute("DELETE FROM confirmations WHERE id=? AND pair_id=? AND user=? AND expires>? RETURNING id",
            (digest(nonce), pair_id, user, time.time())).fetchone()
        row = pair_row(db, pair_id)
        if not confirmation or row["state"] not in ("pending", "active") or row["expires"] <= time.time():
            raise LinkError("Confirmation invalide.")
        db.execute("UPDATE pairs SET state=?, expires=? WHERE id=?",
            ("active" if decision == "approve" else "revoked", time.time() + 90 * 86400, pair_id))


def post_json(url, key, data):
    request = Request(url, json.dumps(data).encode(), {"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=3) as response:
        return json.loads(response.read(16385))


def receive(reference, user):
    with database() as db:
        request = db.execute("SELECT * FROM requests WHERE id=? AND expires>?", (digest(reference), time.time())).fetchone()
        if request is None or not hmac.compare_digest(request["user"], user):
            raise LinkError("Demande absente, expirée ou non autorisée.")
        row = pair_row(db, request["pair_id"])
        entry = configuration().get("applications", {}).get(row["application"])
        if not active(row) or not entry:
            raise LinkError("Liaison inactive.")
        context = post_json(entry["verify_url"], entry["key"], {"ticket": request["ticket"], "user": user, "pair_id": row["id"]})
        if (not isinstance(context, dict) or set(context) != {"application", "user", "intention", "resource_type", "resource_id"}
                or context["application"] != "arcenal-matos" or context["user"] != user
                or context["intention"] != "read_only_help" or context["resource_type"] != "module"
                or context["resource_id"] not in MODULES):
            raise LinkError("Contexte refusé.")
        db.execute("DELETE FROM requests WHERE id=?", (digest(reference),))
        return context
