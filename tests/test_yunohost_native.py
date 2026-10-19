"""Capacité native : enrôlement, inventaire minimal, suivi et validation réelle."""

import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "connectors"))
from arcenal_connectors.contracts import Denied  # noqa: E402
from arcenal_connectors.inventory import READ_COMMANDS, collect, filtered  # noqa: E402
from arcenal_connectors.provision import bootstrap  # noqa: E402
from arcenal_connectors.store import Store  # noqa: E402


INVENTORY = {"applications": ["arcenal", "nextcloud"],
             "services": ["arcenal", "nginx", "php8.2-fpm", "slapd"], "domains": ["server.test"]}
SCOPE = {"server.inventory": ["server"], "service.status": ["arcenal", "php8.2-fpm"],
         "service.start": ["php8.2-fpm"], "service.stop": ["php8.2-fpm"],
         "service.restart": ["nginx"], "backup.create": ["nextcloud"]}


class Backend:
    def __init__(self):
        self.tests = 0
        self.calls = []

    def test(self, config, secret, profile):
        self.tests += 1

    def execute(self, config, secret, operation, target, data, profile, *, request_id=None):
        self.calls.append((operation, target, request_id))
        if operation == "server.inventory":
            return {"ok": True, "inventory": INVENTORY, "password": "fixture-secret-not-returned"}
        return {"ok": True, "state": "active"}


class NativeYunoHostTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.backend = Backend()
        self.store = Store(self.tmp.name, "default", {"yunohost": self.backend})

    def test_ready_for_first_inventory_without_entering_any_secret(self):
        self.assertTrue(self.store.initialize_yunohost("https://server.test", SCOPE))
        result = self.store.propose("yunohost", "server.inventory", "server", {}, "session_a")
        self.assertTrue(result["ok"])
        self.assertEqual(result["inventory"], INVENTORY)
        self.assertEqual(self.backend.tests, 1)
        self.assertNotIn("fixture-secret-not-returned", json.dumps(result))
        connector = self.store.list("admin")["connectors"][2]
        self.assertEqual(connector["state"], "connecte")
        self.assertFalse(connector["has_secret"])
        self.assertEqual(self.store.action_status(result["id"]), result)

    def test_native_writes_still_require_unique_human_confirmation(self):
        self.store.initialize_yunohost("https://server.test", SCOPE)
        for operation, target in (("service.start", "php8.2-fpm"), ("service.stop", "php8.2-fpm"),
                                  ("service.restart", "nginx"), ("backup.create", "nextcloud")):
            with self.subTest(operation=operation):
                before = len(self.backend.calls)
                request = self.store.propose("yunohost", operation, target, {}, "session_a")
                self.assertTrue(request["approval_required"])
                self.assertEqual(len(self.backend.calls), before)
                self.assertEqual(self.store.action_status(request["id"])["state"], "pending")
                with self.assertRaises(Denied):
                    self.store.decide("admin", request["id"], True, "session")
                completed = self.store.decide("admin", request["id"], True)
                self.assertTrue(completed["ok"])
                self.assertEqual(self.store.action_status(request["id"]), completed)
                self.assertEqual(len(self.backend.calls), before + 1)
                with self.assertRaises(Denied):
                    self.store.decide("admin", request["id"], True)

    def test_reinitialization_does_not_reenable_a_disabled_connector(self):
        self.store.initialize_yunohost("https://server.test", SCOPE)
        self.store.manage("admin", "yunohost", "disable", confirmed=True)
        self.assertFalse(self.store.initialize_yunohost("https://server.test", SCOPE))
        with self.assertRaises(Denied):
            self.store.propose("yunohost", "server.inventory", "server", {}, "session_a")
        self.assertEqual(self.backend.tests, 0)
        self.assertFalse(self.backend.calls)

    def test_failed_native_probe_never_turns_into_a_mutation(self):
        self.store.initialize_yunohost("https://server.test", SCOPE)
        with patch.object(self.backend, "test", side_effect=RuntimeError("fixture-private-error")):
            with self.assertRaises(Denied):
                self.store.propose("yunohost", "service.restart", "nginx", {}, "session_a")
        self.assertFalse(self.backend.calls)
        self.assertEqual(self.store.list("admin")["connectors"][2]["state"], "erreur")

    def test_status_read_cannot_cross_client_profiles(self):
        self.store.initialize_yunohost("https://server.test", SCOPE)
        request = self.store.propose("yunohost", "service.restart", "nginx", {}, "session_a")
        other = Store(self.tmp.name, "other_client", {"yunohost": self.backend})
        with self.assertRaises(Denied):
            other.action_status(request["id"])

    def test_recovery_exposes_unknown_outcome_without_replaying_a_write(self):
        self.store.initialize_yunohost("https://server.test", SCOPE)
        request = self.store.propose("yunohost", "service.restart", "nginx", {}, "session_a")
        with patch.object(self.store, "_execute", side_effect=SystemExit("simulate process loss")):
            with self.assertRaises(SystemExit):
                self.store.decide("admin", request["id"], True)
        self.assertEqual(self.store.action_status(request["id"])["state"], "executing")
        self.store.recover_interrupted()
        self.assertEqual(self.store.action_status(request["id"])["state"], "unknown")
        self.assertFalse(self.backend.calls)
        with self.assertRaises(Denied):
            self.store.decide("admin", request["id"], True)

    def test_inventory_uses_only_official_read_commands_and_drops_settings(self):
        secret = "fixture-do-not-expose"
        payloads = [
            {"apps": [{"id": "nextcloud", "password": secret}]},
            {"nginx": {"password": secret}},
            {"domains": ["server.test"], "password": secret},
        ]
        responses = [subprocess.CompletedProcess([], 0, json.dumps(value), secret) for value in payloads]
        with patch("arcenal_connectors.inventory.subprocess.run", side_effect=responses) as run:
            inventory = collect()
        self.assertEqual([call.args[0] for call in run.call_args_list], list(READ_COMMANDS.values()))
        self.assertNotIn(secret, json.dumps(inventory))
        self.assertEqual(filtered(inventory, {"applications": [], "services": ["nginx"], "domains": []}),
                         {"applications": [], "services": ["nginx"], "domains": []})

    def test_first_enrollment_scopes_control_and_preserves_later_restrictions(self):
        root = Path(self.tmp.name)
        home = root / "hermes"
        home.mkdir()
        if os.getuid() == 0:
            os.chown(home, 65534, 65534)
        (home / ".env").write_text("EXISTING_SECRET=fixture-unchanged\n")
        policy_path = root / "etc/policy.json"
        policy = bootstrap(policy_path, str(root / "vault"), home, "default", ["admin"],
                           "https://server.test:9443", INVENTORY)
        ceiling = policy["yunohost_targets"]["default"]
        self.assertEqual(ceiling["service.stop"], ["php8.2-fpm"])
        self.assertNotIn("arcenal", ceiling["backup.create"])
        self.assertEqual(ceiling["server.inventory"], ["server"])
        policy["yunohost_targets"]["default"]["service.restart"] = []
        policy["principals"] = {}
        policy_path.write_text(json.dumps(policy))
        again = bootstrap(policy_path, str(root / "vault"), home, "default", ["admin"],
                          "https://server.test:9443", INVENTORY)
        self.assertEqual(again["principals"], {})
        self.assertEqual(again["yunohost_targets"]["default"]["service.restart"], [])
        self.assertEqual((home / ".env").read_text(), "EXISTING_SECRET=fixture-unchanged\n")

    def test_helper_protects_the_control_plane_even_if_policy_is_misconfigured(self):
        loader = importlib.machinery.SourceFileLoader("native_yunohost_helper", str(ROOT / "connectors/yunohost-helper"))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        helper = importlib.util.module_from_spec(spec)
        loader.exec_module(helper)
        request = {"profile": "default", "operation": "service.stop", "target": "nginx", "request_id": "a" * 32}
        policy = {"yunohost_targets": {"default": {"service.stop": ["nginx", "php8.2-fpm"]}}}
        with self.assertRaises(ValueError):
            helper.build_command(request, policy)
        request["target"] = "php8.2-fpm"
        self.assertEqual(helper.build_command(request, policy), ["/usr/bin/yunohost", "service", "stop", "php8.2-fpm"])
