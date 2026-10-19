"""Contrats réels du service central ; seules les applications externes sont simulées."""

from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from http.server import HTTPServer
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "connectors"))
from arcenal_connectors.contracts import Denied, service_url  # noqa: E402
from arcenal_connectors.network import Network, PinnedHTTPS  # noqa: E402
from arcenal_connectors.plugins import registry  # noqa: E402
from arcenal_connectors.server import Authority, handler  # noqa: E402
from arcenal_connectors.store import Store  # noqa: E402


SECRET = 'fixture-only-connector-secret-"-123456'


class FakePlugin:
    def __init__(self):
        self.calls = []
        self.fail = False

    def test(self, config, secret, profile):
        if self.fail:
            raise RuntimeError(SECRET)

    def execute(self, config, secret, name, target, data, profile, *, request_id=None):
        self.calls.append((profile, name, target, data))
        if self.fail:
            raise RuntimeError(SECRET)
        return {"ok": True, "state": "active", "forbidden": SECRET}


class ConnectorFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now = 1000
        self.plugin = FakePlugin()
        self.plugins = {name: self.plugin for name in ("dolibarr", "nextcloud", "yunohost")}
        self.store = Store(self.tmp.name, "client_a", self.plugins, clock=lambda: self.now)

    def configured(self, store=None, connector="nextcloud"):
        store = store or self.store
        if connector == "nextcloud":
            value = {"url": "https://nextcloud.example.test", "account": "arcenal-client-a", "secret": SECRET,
                     "scope": {name: ["ARCenal"] for name in ("file.mkdir", "file.write", "file.delete")}}
        else:
            value = {"url": "https://yunohost.example.test", "account": "arcenal-connectors",
                     "scope": {name: ["arcenal"] for name in ("service.status", "service.restart", "backup.create")}}
        plan = store.plan_configuration("admin", connector, value)
        self.assertNotIn(SECRET, json.dumps(plan))
        store.confirm_configuration("admin", plan["id"], True)
        store.manage("admin", connector, "test")
        return value

    def propose(self, name="file.mkdir", target="ARCenal/dossier", data=None, session="session_a"):
        return self.store.propose("nextcloud", name, target, data or {}, session)


class ConnectorsTests(ConnectorFixture):
    def test_configuration_is_write_only_encrypted_and_modifiable(self):
        config = self.configured()
        self.assertNotIn(SECRET.encode(), self.store.path.read_bytes())
        self.assertNotIn(SECRET, json.dumps(self.store.list("admin")))
        config.pop("secret")
        config["url"] = "https://nextcloud2.example.test"
        with self.assertRaises(Denied):
            self.store.plan_configuration("admin", "nextcloud", config)
        config["secret"] = SECRET
        plan = self.store.plan_configuration("admin", "nextcloud", config)
        self.store.confirm_configuration("admin", plan["id"], True)
        self.assertEqual(self.store.list("admin")["connectors"][1]["state"], "a_tester")
        self.store.manage("admin", "nextcloud", "test")
        self.assertEqual(self.store.list("admin")["connectors"][1]["config"]["url"], config["url"])

    def test_configuration_requires_distinct_human_confirmation(self):
        value = {"url": "https://nextcloud.example.test", "account": "arcenal-a", "secret": SECRET,
                 "scope": {"file.mkdir": ["ARCenal"]}}
        plan = self.store.plan_configuration("admin", "nextcloud", value)
        self.assertEqual(self.store.list("admin")["connectors"][1]["state"], "non_configure")
        self.store.confirm_configuration("admin", plan["id"], False)
        with self.assertRaises(Denied):
            self.store.confirm_configuration("admin", plan["id"], True)

    def test_successful_and_failed_connection_are_sanitized(self):
        self.configured()
        self.assertEqual(self.store.list("admin")["connectors"][1]["state"], "connecte")
        self.plugin.fail = True
        self.assertEqual(self.store.manage("admin", "nextcloud", "test"), {"ok": False})
        self.assertEqual(self.store.list("admin")["connectors"][1]["state"], "erreur")
        self.assertNotIn(SECRET, json.dumps(self.store.audit("admin", "nextcloud")))

    def test_write_without_approval_never_executes(self):
        self.configured()
        request = self.propose()
        self.assertTrue(request["approval_required"])
        self.assertEqual(self.plugin.calls, [])

    def test_once_is_consumed_and_not_replayable(self):
        self.configured()
        request = self.propose()
        result = self.store.decide("admin", request["id"], True)
        self.assertTrue(result["ok"])
        self.assertEqual(len(self.plugin.calls), 1)
        with self.assertRaises(Denied):
            self.store.decide("admin", request["id"], True)
        self.assertTrue(self.propose()["approval_required"])
        self.assertNotIn(SECRET, json.dumps(result))

    def test_concurrent_approval_does_not_execute_twice(self):
        self.configured()
        request = self.propose()
        barrier = threading.Barrier(2)

        def approve():
            barrier.wait(timeout=5)
            try:
                return self.store.decide("admin", request["id"], True)["state"]
            except Denied:
                return "denied"

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: approve(), range(2)))
        self.assertCountEqual(results, ["done", "denied"])
        self.assertEqual(len(self.plugin.calls), 1)

    def test_always_validate_cannot_be_overridden_by_session_mode(self):
        self.configured()
        request = self.propose()
        self.store.decide("admin", request["id"], True, "always")
        pending = self.propose()
        self.assertTrue(self.store.list("admin")["requests"][0]["always_required"])
        with self.assertRaises(Denied):
            self.store.decide("admin", pending["id"], True, "session")
        self.assertEqual(len(self.plugin.calls), 1)

    def test_missing_central_plugin_and_unknown_actions_fail_closed(self):
        for connector, op in (("other", "file.mkdir"), ("nextcloud", "shares.create"), ("yunohost", "user.create")):
            with self.subTest(connector=connector, op=op), self.assertRaises(Denied):
                self.store.propose(connector, op, "target", {}, "session_a")
        self.assertFalse(self.plugin.calls)

    def test_refusal_and_expiration_never_execute(self):
        self.configured()
        request = self.propose()
        self.store.decide("admin", request["id"], False)
        with self.assertRaises(Denied):
            self.store.decide("admin", request["id"], True)
        request = self.propose()
        self.now += 901
        with self.assertRaises(Denied):
            self.store.decide("admin", request["id"], True)
        self.assertFalse(self.plugin.calls)

    def test_session_ends_and_does_not_cover_other_targets_or_sessions(self):
        self.configured()
        request = self.propose()
        self.store.decide("admin", request["id"], True, mode="session")
        self.assertTrue(self.propose()["ok"])
        self.assertTrue(self.propose(session="session_b")["approval_required"])
        self.assertTrue(self.propose(target="ARCenal/autre")["approval_required"])
        self.store.end_session("session_a")
        with self.assertRaises(Denied):
            self.propose()
        self.assertTrue(self.propose(session="session_a_reopened")["approval_required"])

    def test_limited_delegation_is_exact_and_expires(self):
        self.configured()
        request = self.propose("file.write", data={"content": "contenu validé"})
        self.store.decide("admin", request["id"], True, mode="limited", expires=self.now + 60)
        self.assertTrue(self.propose("file.write", data={"content": "contenu validé"})["ok"])
        self.assertTrue(self.propose("file.write", data={"content": "autre contenu"})["approval_required"])
        self.now += 61
        self.assertTrue(self.propose("file.write", data={"content": "contenu validé"})["approval_required"])

    def test_revocation_takes_effect_immediately(self):
        self.configured()
        request = self.propose()
        self.store.decide("admin", request["id"], True, mode="limited", expires=self.now + 60)
        grant = self.store.list("admin")["grants"][0]
        self.store.revoke("admin", grant["id"], confirmed=True)
        self.assertTrue(self.propose()["approval_required"])

    def test_revocation_does_not_wait_for_an_inflight_network_call(self):
        self.configured()
        request = self.propose()
        self.store.decide("admin", request["id"], True, mode="limited", expires=self.now + 60)
        grant = self.store.list("admin")["grants"][0]
        started, release, revoked = threading.Event(), threading.Event(), threading.Event()
        errors = []

        def blocked(*args, **kwargs):
            started.set()
            if not release.wait(10):
                raise RuntimeError("fixture timeout")
            return {"ok": True}

        def revoke():
            try:
                self.store.revoke("admin", grant["id"], confirmed=True)
                revoked.set()
            except Exception as error:
                errors.append(error)

        with patch.object(self.plugin, "execute", side_effect=blocked):
            worker = threading.Thread(target=self.propose)
            worker.start()
            revoker = threading.Thread(target=revoke)
            try:
                self.assertTrue(started.wait(5))
                revoker.start()
                self.assertTrue(revoked.wait(5), "La révocation attend à tort le réseau.")
                self.assertTrue(self.propose()["approval_required"])
            finally:
                release.set()
                worker.join(timeout=5)
                if revoker.ident is not None:
                    revoker.join(timeout=5)
        self.assertFalse(errors)

    def test_connection_result_cannot_restore_a_revoked_secret(self):
        self.configured()
        started, release = threading.Event(), threading.Event()

        def test_connection(*args):
            started.set()
            release.wait(10)

        with patch.object(self.plugin, "test", side_effect=test_connection):
            worker = threading.Thread(target=lambda: self.store.manage("admin", "nextcloud", "test"))
            worker.start()
            try:
                self.assertTrue(started.wait(5))
                self.store.manage("admin", "nextcloud", "revoke_secret", confirmed=True)
            finally:
                release.set()
                worker.join(timeout=5)
        connector = self.store.list("admin")["connectors"][1]
        self.assertEqual(connector["state"], "desactive")
        self.assertFalse(connector["has_secret"])

    def test_destructive_operations_refuse_reusable_approval(self):
        self.configured()
        request = self.propose("file.delete")
        for mode in ("session", "limited"):
            with self.subTest(mode=mode), self.assertRaises(Denied):
                self.store.decide("admin", request["id"], True, mode=mode, expires=self.now + 60)
        self.assertFalse(self.plugin.calls)
        self.assertTrue(self.store.decide("admin", request["id"], True)["ok"])

    def test_yunohost_mutations_always_require_explicit_once_approval(self):
        self.configured(connector="yunohost")
        for name in ("service.restart", "backup.create"):
            request = self.store.propose("yunohost", name, "arcenal", {}, "session_a")
            before = len(self.plugin.calls)
            with self.assertRaises(Denied):
                self.store.decide("admin", request["id"], True, "session")
            self.assertEqual(len(self.plugin.calls), before)
            self.store.decide("admin", request["id"], True, "once")
            self.assertEqual(len(self.plugin.calls), before + 1)

    def test_configuration_change_invalidates_pending_and_existing_grants(self):
        value = self.configured()
        request = self.propose()
        self.store.decide("admin", request["id"], True, "session")
        pending = self.propose(target="ARCenal/autre")
        plan = self.store.plan_configuration("admin", "nextcloud", value)
        self.store.confirm_configuration("admin", plan["id"], True)
        self.store.manage("admin", "nextcloud", "test")
        with self.assertRaises(Denied):
            self.store.decide("admin", pending["id"], True)
        self.assertTrue(self.propose()["approval_required"])

    def test_disabled_or_revoked_connector_fails_closed(self):
        self.configured()
        self.store.manage("admin", "nextcloud", "revoke_secret", confirmed=True)
        with self.assertRaises(Denied):
            self.propose()
        self.assertFalse(self.store.list("admin")["connectors"][1]["has_secret"])

    def test_audit_failure_prevents_any_execution(self):
        self.configured()
        request = self.propose()
        with patch.object(self.store, "_audit", side_effect=sqlite3.OperationalError("fixture")):
            with self.assertRaises(Denied):
                self.store.decide("admin", request["id"], True)
        self.assertFalse(self.plugin.calls)
        self.assertEqual(self.store.list("admin")["requests"][0]["state"], "pending")

    def test_audit_tampering_prevents_execution(self):
        self.configured()
        request = self.propose()
        with closing(sqlite3.connect(self.store.path)) as db, db:
            db.execute("update audit set event='{}' where seq=1")
        with self.assertRaises(Denied):
            self.store.decide("admin", request["id"], True)
        self.assertFalse(self.plugin.calls)

    def test_network_error_does_not_replay_and_does_not_leak(self):
        self.configured()
        request = self.propose()
        self.plugin.fail = True
        result = self.store.decide("admin", request["id"], True)
        self.assertEqual(result["state"], "error")
        self.assertNotIn(SECRET, json.dumps(result))
        with self.assertRaises(Denied):
            self.store.decide("admin", request["id"], True)
        self.assertEqual(len(self.plugin.calls), 1)

    def test_profile_cannot_approve_other_profile_request(self):
        self.configured()
        request = self.propose()
        other = Store(self.tmp.name, "client_b", self.plugins)
        self.configured(other)
        with self.assertRaises(Denied):
            other.decide("admin", request["id"], True)
        self.assertNotEqual(self.store.key, other.key)
        self.assertFalse(self.plugin.calls)

    def test_secret_cannot_be_reflected_in_action_fields_or_audit(self):
        self.configured()
        with self.assertRaises(Denied):
            self.propose("file.write", data={"content": SECRET})
        self.assertNotIn(SECRET, json.dumps(self.store.list("admin")))
        self.assertNotIn(SECRET, json.dumps(self.store.audit("admin", "nextcloud")))

    def test_server_restart_preserves_existing_vault_and_hermes_data(self):
        hermes = Path(self.tmp.name) / "hermes"
        hermes.mkdir()
        original = {"config.yaml": b"# intact\nmodel: fixture\n", ".env": b"EXISTING_SECRET=fixture\n",
                    "state.db": b"historical sessions", "skills/test.md": b"existing skill"}
        for name, content in original.items():
            target = hermes / name
            target.parent.mkdir(exist_ok=True)
            target.write_bytes(content)
        self.configured()
        restarted = Store(self.tmp.name, "client_a", self.plugins)
        self.assertEqual(restarted.list("admin")["connectors"][1]["state"], "connecte")
        self.assertEqual(restarted.key, self.store.key)
        self.assertEqual({name: (hermes / name).read_bytes() for name in original}, original)

    def test_url_and_path_injection_are_refused(self):
        for url in ("http://service.test", "https://user:password@service.test", "https://service.test/?token=x",
                    "https://service.test/#secret", "https://service.test/a/../b", "https://service.test/%2e"):
            with self.subTest(url=url), self.assertRaises(Denied):
                service_url(url)
        self.configured()
        for path in ("ARCenal/../private", "/ARCenal", "ARCenal/%2e%2e/private", "ARCenal\\private", "OTHER/path"):
            with self.subTest(path=path), self.assertRaises(Denied):
                self.propose(target=path)


class ApiTests(ConnectorFixture):
    def setUp(self):
        super().setUp()
        self.policy = Path(self.tmp.name) / "policy.json"
        self.settings = {"schema": 1, "origin": "https://server.example.test:9443", "vault_root": self.tmp.name,
                         "principals": {"admin_a": {"role": "admin", "profiles": ["client_a"]}},
                         "profile_uids": {"client_a": 1234}}
        self.policy.write_text(json.dumps(self.settings))
        self.authority = Authority(self.policy, self.plugins, clock=lambda: self.now)
        self.admin_headers = {"X-ARCenal-User": "admin_a", "Origin": self.settings["origin"], "X-ARCenal-Intent": "manage"}
        self.agent_headers = {}

    def test_health_checks_the_actual_profile_audit_before_reporting_ready(self):
        self.configured()
        self.assertTrue(self.authority.health()["ready"])
        with closing(sqlite3.connect(self.store.path)) as db, db:
            db.execute("update audit set signature='invalid' where seq=1")
        with self.assertRaises(Denied):
            self.authority.health()

    def test_agent_reads_yunohost_approval_status_but_cannot_validate_it(self):
        self.store.initialize_yunohost("https://server.example.test", {"service.status": ["arcenal"], "service.restart": ["nginx"]})
        request = self.store.propose("yunohost", "service.restart", "nginx", {}, "session_a")
        status = self.authority.dispatch("agent", {}, "POST", "/v1/actions/status", {"id": request["id"]}, peer_uid=1234)
        self.assertEqual(status["state"], "pending")
        with self.assertRaises(Denied):
            self.authority.dispatch("agent", {}, "POST", "/v1/actions/status", {"id": request["id"], "accept": True}, peer_uid=1234)
        self.assertFalse(self.plugin.calls)

    def test_agent_cannot_use_admin_routes_or_choose_another_profile(self):
        for path in ("/v1/actions/forged/decision", "/v1/configuration", "/v1/actions?profile=client_b"):
            with self.subTest(path=path), self.assertRaises(Denied):
                self.authority.dispatch("agent", self.agent_headers, "POST", path, {}, peer_uid=1234)

    def test_forged_headers_cannot_override_the_kernel_identity(self):
        self.configured()
        body = {"connector": "nextcloud", "operation": "file.mkdir", "target": "ARCenal/test", "data": {}, "session": "session_a"}
        with self.assertRaises(Denied):
            self.authority.dispatch("agent", {"X-ARCenal-User": "admin_a", "Authorization": "Bearer forged"},
                                    "POST", "/v1/actions", body, peer_uid=5678)
        self.assertTrue(self.authority.dispatch("agent", self.agent_headers, "POST", "/v1/actions", body, peer_uid=1234)["approval_required"])

    def test_hermes_browser_origin_cannot_confirm_even_with_valid_sso(self):
        headers = dict(self.admin_headers, Origin="https://server.example.test")
        with self.assertRaises(Denied):
            self.authority.dispatch("admin", headers, "POST", "/v1/actions/forged/decision?profile=client_a", {"accept": True})

    def test_sso_identity_profile_binding_and_origin_are_required(self):
        for headers, profile in (({}, "client_a"), (self.admin_headers, "client_b")):
            with self.assertRaises(Denied):
                self.authority.dispatch("admin", headers, "GET", "/v1/state?profile=" + profile, None)
        headers = dict(self.admin_headers, Origin="https://evil.example.test")
        with self.assertRaises(Denied):
            self.authority.dispatch("admin", headers, "POST", "/v1/configuration?profile=client_a", {})
        self.settings["principals"] = {}
        self.policy.write_text(json.dumps(self.settings))
        with self.assertRaises(Denied):
            self.authority.dispatch("admin", self.admin_headers, "GET", "/v1/state?profile=client_a", None)

    def test_real_http_api_never_returns_secret_or_raw_exception(self):
        self.configured()
        server = HTTPServer(("127.0.0.1", 0), handler(self.authority, "admin"))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/v1/state?profile=client_a"
            with urlopen(Request(url, headers=self.admin_headers), timeout=5) as response:
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.assertNotIn(SECRET.encode(), response.read())
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(url, data=json.dumps({"secret": SECRET}).encode(), headers={
                    **self.admin_headers, "Content-Type": "application/json"}), timeout=5)
            with error.exception:
                self.assertNotIn(SECRET.encode(), error.exception.read())
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)


class PluginContractTests(unittest.TestCase):
    def test_pinned_https_keeps_hostname_certificate_validation(self):
        with patch("socket.create_connection") as connect, patch("ssl.create_default_context") as context:
            client = PinnedHTTPS("nextcloud.example.test", "203.0.113.1")
            client.connect()
            connect.assert_called_once_with(("203.0.113.1", 443), timeout=10)
            context.return_value.wrap_socket.assert_called_once_with(connect.return_value,
                                                                      server_hostname="nextcloud.example.test")

    def test_plugins_use_only_declared_methods_and_no_secret_in_url(self):
        class FakeNetwork:
            calls = []

            def request(self, config, method, suffix, headers=None, body=None):
                self.calls.append((method, suffix, headers, body))
                return json.dumps({"login": config["account"], "ocs": {"meta": {"statuscode": 100},
                                   "data": {"id": config["account"]}}}).encode()

        network = FakeNetwork()
        plugins = registry(network, None)
        config = {"url": "https://fixture.test", "account": "arcenal-fixture", "entity": 1}
        plugins["dolibarr"].test(config, SECRET, "client_a")
        plugins["nextcloud"].test(config, SECRET, "client_a")
        plugins["dolibarr"].execute(config, SECRET, "contact.create", "company:1", {"lastname": "Exemple"}, "client_a")
        plugins["nextcloud"].execute(config, SECRET, "file.mkdir", "ARCenal/dossier", {}, "client_a")
        self.assertEqual([call[0] for call in network.calls], ["GET", "GET", "POST", "MKCOL"])
        self.assertTrue(all(SECRET not in call[1] for call in network.calls))

    def test_ssrf_is_refused_before_http(self):
        answers = [(2, 1, 6, "", ("169.254.169.254", 443))]
        with patch("socket.getaddrinfo", return_value=answers), patch("arcenal_connectors.network.PinnedHTTPS") as client:
            with self.assertRaises(Denied):
                Network().request({"url": "https://service.test"}, "GET", "/")
            client.assert_not_called()

    def test_yunohost_helper_has_no_generic_command_or_argument(self):
        loader = importlib.machinery.SourceFileLoader("arcenal_helper_fixture", str(ROOT / "connectors/yunohost-helper"))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        policy = {"yunohost_targets": {"client_a": {"service.restart": ["nginx"]}}}
        request = {"profile": "client_a", "operation": "service.restart", "target": "nginx", "request_id": "a" * 32}
        self.assertEqual(module.build_command(request, policy), ["/usr/bin/yunohost", "service", "restart", "nginx"])
        for update in ({"target": "ssh"}, {"operation": "user.create"}, {"target": "arcenal;id"}, {"profile": "client_b"}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                module.build_command(dict(request, **update), policy)
