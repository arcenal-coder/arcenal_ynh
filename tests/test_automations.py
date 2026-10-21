"""Flux complet par HTTP authentifié simulant les produits, sans modèle ni root."""

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import base64
import http.client
import json
import sqlite3
import shutil
from pathlib import Path
import sys
import tempfile
import tarfile
import threading
import unittest
from urllib.parse import parse_qs, unquote, urlsplit
from unittest.mock import patch


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "connectors"))
from arcenal_connectors.automations import Automations  # noqa: E402
from arcenal_connectors.contracts import Denied  # noqa: E402
from arcenal_connectors.plugins import registry  # noqa: E402
from arcenal_connectors.server import Authority, handler  # noqa: E402
from arcenal_connectors.store import Store  # noqa: E402
from arcenal_connectors.operations import Operations  # noqa: E402


SPEC = {"id": "project-onboarding", "projects": ["42"], "status_field": "opp_status",
        "from_status": "prospection", "to_statuses": ["won"], "base_folder": "ARCenal",
        "folders": ["01_Admin", "02_Technique"], "share_group": "arcenal-team",
        "link_field": "options_nextcloud_url", "interval": 30, "ksaar_required": False}
SECRET = "fixture-only-server-secret"


class Products:
    def __init__(self):
        self.project = {"id": "42", "opp_status": "prospection", "array_options": {}}
        self.folders = {"ARCenal": "1"}
        self.shares = []
        self.writes = []
        self.lost_share_reply = False
        self.no_share_reply = False
        self.lost_project_reply = False
        self.after_mkdir = None
        self.after_missing_lookup = None


class LoopbackTransport:
    """Transport de test injecté ; la production reste HTTPS/IP épinglée."""

    def __init__(self, port):
        self.port = port

    def request(self, config, method, suffix, headers=None, body=None):
        return self.request_response(config, method, suffix, headers, body)[1]

    def request_response(self, config, method, suffix, headers=None, body=None, accepted=()):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.request(method, urlsplit(config["url"]).path + suffix, body=body, headers=headers or {})
            response = connection.getresponse()
            content = response.read()
            if not 200 <= response.status < 300 and response.status not in accepted:
                raise Denied("connexion_ou_action_refusee")
            return response.status, content
        except (OSError, http.client.HTTPException):
            raise Denied("connexion_impossible") from None
        finally:
            connection.close()


@contextmanager
def products_server(products):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            return

        def authenticated(self):
            expected = "Basic " + base64.b64encode(("arcenal-nc:" + SECRET).encode()).decode()
            if self.path.startswith("/erp/"):
                valid = self.headers.get("DOLAPIKEY") == SECRET
            else:
                valid = self.headers.get("Authorization") == expected
            if not valid:
                self.respond(401, {})
            return valid

        def respond(self, code, value, mime="application/json"):
            content = json.dumps(value).encode() if mime == "application/json" else value
            self.send_response(code)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def body(self):
            return self.rfile.read(int(self.headers.get("Content-Length", "0")))

        def ocs(self, data):
            self.respond(200, {"ocs": {"meta": {"statuscode": 100}, "data": data}})

        def do_GET(self):
            if not self.authenticated():
                return
            if self.path == "/erp/projects/42":
                self.respond(200, products.project)
            elif self.path.startswith("/ocs/v2.php/apps/files_sharing/"):
                self.ocs(products.shares)
            else:
                self.respond(404, {})

        def do_PROPFIND(self):
            if not self.authenticated():
                return
            name = unquote(self.path.split("/files/arcenal-nc/", 1)[1])
            if name not in products.folders:
                if products.after_missing_lookup:
                    products.after_missing_lookup()
                self.respond(404, {})
                return
            xml = ('<d:multistatus xmlns:d="DAV:" xmlns:o="http://owncloud.org/ns"><d:response><d:propstat>'
                   '<d:prop><d:resourcetype><d:collection/></d:resourcetype><o:fileid>' + products.folders[name] +
                   '</o:fileid></d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response></d:multistatus>')
            self.respond(207, xml.encode(), "application/xml")

        def do_MKCOL(self):
            if not self.authenticated():
                return
            name = unquote(self.path.split("/files/arcenal-nc/", 1)[1])
            if name in products.folders:
                self.respond(405, {})
                return
            products.folders[name] = str(len(products.folders) + 1)
            products.writes.append(("mkdir", name))
            if products.after_mkdir:
                products.after_mkdir()
            self.respond(201, {})

        def do_POST(self):
            if not self.authenticated():
                return
            value = parse_qs(self.body().decode())
            if products.no_share_reply:
                self.close_connection = True
                return
            path = value["path"][0].lstrip("/")
            share = {"id": str(len(products.shares) + 1), "share_type": 1, "share_with": value["shareWith"][0],
                     "permissions": 1, "uid_owner": "arcenal-nc", "file_source": products.folders[path]}
            products.shares.append(share)
            products.writes.append(("share", path))
            if products.lost_share_reply:
                products.lost_share_reply = False
                self.close_connection = True
                return
            self.ocs(share)

        def do_PUT(self):
            if not self.authenticated():
                return
            value = json.loads(self.body())
            products.project["array_options"].update(value["array_options"])
            products.writes.append(("project", "42"))
            if products.lost_project_reply:
                products.lost_project_reply = False
                self.close_connection = True
                return
            self.respond(200, products.project)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class AutomationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.products = Products()
        self.server = products_server(self.products)
        self.port = self.server.__enter__()
        self.addCleanup(lambda: self.server.__exit__(None, None, None))
        self.now = 1000
        self.owner_valid = True
        self.plugins = registry(LoopbackTransport(self.port), None)
        self.store = Store(self.tmp.name, "default", self.plugins, clock=lambda: self.now)
        values = {
            "dolibarr": {"url": "https://erp.test/erp", "account": "arcenal-dol", "secret": SECRET,
                         "scope": {"project.read": ["project:42"], "project.update_link": ["project:42"]},
                         "project_link_fields": ["options_nextcloud_url"]},
            "nextcloud": {"url": "https://nc.test", "account": "arcenal-nc", "secret": SECRET,
                          "scope": {"file.mkdir": ["ARCenal"], "file.share_group": ["ARCenal"]},
                          "share_groups": ["arcenal-team"]},
        }
        for name, value in values.items():
            plan = self.store.plan_configuration("owner", name, value)
            self.store.confirm_configuration("owner", plan["id"], True)
            with self.store.transaction("test") as db:
                connection = self.store._read(db, "connector", name)
                connection["state"] = "connecte"
                self.store._write(db, "connector", name, connection)
        self.engine = Automations(self.store, lambda actor: actor == "owner" and self.owner_valid)

    def activate(self, spec=None):
        item = self.engine.save("owner", spec or SPEC, True)
        self.engine.activate("owner", item["id"], item["version"], True)

    def transition(self):
        self.engine.tick()  # baseline, no retroactive trigger
        self.products.project["opp_status"] = "won"
        self.now += 31
        self.engine.tick()

    def test_full_authorized_flow_runs_without_per_execution_approval_and_no_duplicates(self):
        self.activate()
        self.assertFalse(self.products.writes)
        self.transition()
        state = self.engine.state("owner")
        self.assertEqual(len(state["runs"]), 1)
        self.assertEqual(state["runs"][0]["state"], "done")
        self.assertEqual(state["runs"][0]["steps"]["ksaar"]["state"], "not_applicable")
        self.assertEqual(self.products.project["array_options"]["options_nextcloud_url"], "https://nc.test/index.php/f/2")
        self.assertEqual([op for op, _ in self.products.writes].count("mkdir"), 3)
        self.assertEqual([op for op, _ in self.products.writes].count("share"), 1)
        self.assertEqual([op for op, _ in self.products.writes].count("project"), 1)
        before = list(self.products.writes)
        for _ in range(3):
            self.now += 31
            self.engine.tick()
        self.assertEqual(self.products.writes, before)
        self.products.project["opp_status"] = "prospection"
        self.now += 31
        self.engine.tick()
        self.products.project["opp_status"] = "won"
        self.now += 31
        self.engine.tick()
        self.assertEqual(len(self.engine.state("owner")["runs"]), 2)
        self.assertEqual(self.products.writes, before)
        self.assertNotIn(SECRET, json.dumps(state))
        self.assertNotIn("index.php/f/", json.dumps(self.store.audit("owner", "nextcloud")))

    def test_one_operation_consent_covers_creation_and_activation(self):
        operations = Operations(self.store, lambda actor: actor == "owner", lambda: {})
        pending = operations.prepare({"summary": "Créer et activer la définition validée", "consequences": ["Le flux s'exécutera seul dans son périmètre."],
                                      "rollback": "Désactiver le flux sans supprimer ses effets.",
                                      "steps": [{"kind": "automation", "definition": SPEC}]})
        self.assertEqual(self.engine.state("owner")["automations"], [])
        result = operations.decide("owner", pending["id"], pending["digest"], True)
        self.assertEqual(result["state"], "done")
        self.assertTrue(self.engine.state("owner")["automations"][0]["enabled"])
        self.assertFalse(self.products.writes)

    def test_owner_confirmation_and_ksaar_contract_are_not_faked(self):
        with self.assertRaises(Denied):
            self.engine.save("owner", SPEC)
        item = self.engine.save("owner", SPEC | {"ksaar_required": True}, True)
        with self.assertRaises(Denied):
            self.engine.activate("owner", item["id"], item["version"], True)
        self.assertFalse(self.products.writes)

    def test_disable_during_execution_blocks_all_following_steps(self):
        self.activate()
        self.products.after_mkdir = lambda: self.engine.disable("owner", SPEC["id"], True)
        self.transition()
        run = self.engine.state("owner")["runs"][0]
        self.assertEqual(run["state"], "failed")
        self.assertEqual(run["step"], "folder_0")
        self.assertEqual(len(self.products.writes), 1)

    def test_revocation_after_lookup_blocks_the_write_not_yet_dispatched(self):
        self.activate()
        self.products.after_missing_lookup = lambda: self.engine.disable("owner", SPEC["id"], True)
        self.transition()
        self.assertFalse(self.products.writes)

    def test_preview_and_duplicate_activation_have_no_business_effect(self):
        item = self.engine.save("owner", SPEC, True)
        self.assertTrue(self.engine.preview("owner", item["id"], "42")["dry_run"])
        self.engine.activate("owner", item["id"], 1, True)
        self.engine.tick()
        before = self.engine.state("owner")["automations"][0]["epoch"]
        self.engine.activate("owner", item["id"], 1, True)
        self.assertEqual(self.engine.state("owner")["automations"][0]["epoch"], before)
        self.assertFalse(self.products.writes)
        with self.assertRaises(Denied):
            self.engine.activate("owner", item["id"], True, True)

    def test_system_actions_and_undeclared_project_scope_are_refused(self):
        with self.assertRaises(Denied):
            self.engine.save("owner", SPEC | {"operations": ["yunohost:service.restart"]}, True)
        item = self.engine.save("owner", SPEC | {"projects": ["99"]}, True)
        with self.assertRaises(Denied):
            self.engine.activate("owner", item["id"], 1, True)
        self.assertFalse(self.products.writes)

    def test_automation_definitions_and_runs_cannot_cross_profiles(self):
        self.activate()
        self.transition()
        other_store = Store(self.tmp.name, "other_client", self.plugins, clock=lambda: self.now)
        other = Automations(other_store, lambda actor: True)
        self.assertEqual(other.state("owner")["automations"], [])
        self.assertEqual(other.state("owner")["runs"], [])
        with self.assertRaises(Denied):
            other.activate("owner", SPEC["id"], 1, True)

    def test_changed_connector_requires_new_activation(self):
        self.activate()
        self.engine.tick()
        with self.store.transaction("test") as db:
            value = self.store._read(db, "connector", "nextcloud")
            value["revision"] += 1
            self.store._write(db, "connector", "nextcloud", value)
        self.products.project["opp_status"] = "won"
        self.now += 31
        self.engine.tick()
        self.assertFalse(self.products.writes)
        self.assertEqual(self.engine.state("owner")["poll_errors"][SPEC["id"]]["code"], "connecteur_modifie_reactivation_requise")

    def test_unavailable_audit_blocks_writes(self):
        self.activate()
        self.engine.tick()
        self.products.project["opp_status"] = "won"
        self.now += 31
        with patch.object(self.store, "_audit", side_effect=sqlite3.OperationalError("fixture")):
            with self.assertRaises(Denied):
                self.engine.tick()
        self.assertFalse(self.products.writes)

    def test_lost_post_reply_is_reconciled_without_another_share(self):
        self.activate()
        self.products.lost_share_reply = True
        self.transition()
        self.assertEqual(len(self.products.shares), 1)
        self.now += 61
        self.engine.tick()
        self.assertEqual(self.engine.state("owner")["runs"][0]["state"], "done")
        self.assertEqual(len(self.products.shares), 1)

    def test_lost_project_reply_is_read_back_without_second_update(self):
        self.activate()
        self.products.lost_project_reply = True
        self.transition()
        self.assertEqual([op for op, _ in self.products.writes].count("project"), 1)
        self.now += 61
        self.engine.tick()
        self.assertEqual(self.engine.state("owner")["runs"][0]["state"], "done")
        self.assertEqual([op for op, _ in self.products.writes].count("project"), 1)

    def test_restore_keeps_secrets_but_requires_new_owner_activation(self):
        from arcenal_connectors.backup import restore

        self.activate()
        root = Path(self.tmp.name)
        source = root / "snapshot-source/var/lib/arcenal-connectors"
        (source / "profiles").mkdir(parents=True)
        shutil.copytree(self.store.home, source / "profiles/default")
        archive = root / "automations.tar"
        with tarfile.open(archive, "w") as tar:
            tar.add(source, arcname="var/lib/arcenal-connectors")
        target = root / "restored"
        restore(archive, target)
        recovered = Store(target / "var/lib/arcenal-connectors/profiles", "default", self.plugins)
        status = Automations(recovered, lambda actor: True).state("owner")
        self.assertFalse(status["automations"][0]["enabled"])
        self.assertTrue(recovered.list("owner")["connectors"][0]["has_secret"])

    def test_unknown_share_outcome_never_causes_a_blind_post_retry(self):
        self.activate()
        self.products.no_share_reply = True
        self.transition()
        self.now += 61
        self.engine.tick()
        run = self.engine.state("owner")["runs"][0]
        self.assertEqual(run["state"], "needs_review")
        self.assertEqual(run["step"], "share")
        self.assertEqual(run["error"], "partage_incertain_a_verifier")
        self.assertFalse(self.products.shares)

    def test_owner_revocation_or_new_version_cannot_inherit_old_approval(self):
        self.activate()
        self.engine.tick()
        self.owner_valid = False
        self.products.project["opp_status"] = "won"
        self.now += 31
        self.engine.tick()
        self.assertFalse(self.products.writes)
        self.owner_valid = True
        newer = self.engine.save("owner", SPEC | {"folders": ["Nouveau"]}, True)
        self.assertEqual(newer["version"], 2)
        self.engine.tick()
        self.assertFalse(self.products.writes)
        with self.assertRaises(Denied):
            self.engine.activate("other-owner", SPEC["id"], 2, True)

    def test_restart_reclaims_a_run_after_lease_without_duplicate_effects(self):
        self.activate()
        original = self.engine._checkpoint

        def lose_process(run, item, step, result=None):
            if step == "share" and result is not None:
                raise SystemExit("simulated process loss after remote share creation")
            return original(run, item, step, result)

        with patch.object(self.engine, "_checkpoint", side_effect=lose_process):
            with self.assertRaises(SystemExit):
                self.transition()
        self.assertEqual(len(self.products.shares), 1)
        self.now += 121
        reopened = Store(self.tmp.name, "default", self.plugins, clock=lambda: self.now)
        Automations(reopened, lambda actor: actor == "owner").tick()
        self.assertEqual(self.engine.state("owner")["runs"][0]["state"], "done")
        self.assertEqual(len(self.products.shares), 1)

    def test_admin_http_contract_denies_activation_from_agent_surface(self):
        policy = Path(self.tmp.name) / "policy.json"
        policy.write_text(json.dumps({"schema": 1, "origin": "https://agent.test:9443", "vault_root": self.tmp.name,
                         "principals": {"owner": {"role": "admin", "profiles": ["default"]}}, "profile_uids": {"default": 1234}}))
        authority = Authority(policy, self.plugins, clock=lambda: self.now)
        headers = {"X-ARCenal-User": "owner", "Origin": "https://agent.test:9443", "X-ARCenal-Intent": "manage"}
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler(authority, "admin"))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            client.request("POST", "/v1/automations", json.dumps({"definition": SPEC, "confirmed": True}),
                           headers=headers | {"Content-Type": "application/json"})
            response = client.getresponse()
            self.assertEqual(response.status, 200)
            version = json.loads(response.read())["version"]
            client.close()
            authority.dispatch("admin", headers, "POST", "/v1/automations/" + SPEC["id"] + "/activate",
                               {"version": version, "confirmed": True})
            with self.assertRaises(Denied):
                authority.dispatch("agent", {}, "POST", "/v1/automations/" + SPEC["id"] + "/activate",
                                   {"version": version, "confirmed": True}, peer_uid=1234)
            authority.automation_tick()
            self.products.project["opp_status"] = "won"
            self.now += 31
            authority.automation_tick()
            self.assertEqual(authority.automations("default", authority.settings()).state("owner")["runs"][0]["state"], "done")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
