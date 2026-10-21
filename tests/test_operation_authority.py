"""Une approbation du plan couvre ses étapes, sans auto-approbation du modèle."""

import json
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "connectors"))
from arcenal_connectors.authority_policy import QUESTION  # noqa: E402
from arcenal_connectors.cli_authority import execute, invoke, validate  # noqa: E402
from arcenal_connectors.contracts import Denied  # noqa: E402
from arcenal_connectors.operations import Operations  # noqa: E402
from arcenal_connectors.store import Store  # noqa: E402
from arcenal_connectors.server import Authority  # noqa: E402


HOST_ACTIONS = {"user": {"actions": {
    "create": {"api": "POST /users", "arguments": {"-p": {"full": "--password", "extra": {"password": "ask_password"}}}},
    "info": {"api": "GET /users/<user>"}, "delete": {"api": "DELETE /users/<user>"}}},
    "app": {"actions": {"install": {"api": "POST /apps"}, "shell": {"api": "GET /apps/<app>/shell"}}},
    "service": {"actions": {"restart": {"api": "PUT /services/<names>/restart"}, "status": {"api": "GET /services/<names>"}}}}


class Backend:
    def __init__(self):
        self.calls = []
        self.fail_proof = False

    def execute(self, config, secret, name, target, data, profile, *, request_id=None):
        self.calls.append((name, target))
        return {"ok": True, "exists": not self.fail_proof, "not_public": secret}


def connector_step(target):
    return {"kind": "connector", "connector": "nextcloud", "operation": "file.mkdir", "target": target, "data": {},
            "verify": {"action": {"kind": "connector", "connector": "nextcloud", "operation": "file.exists", "target": target, "data": {}},
                       "expected": {"exists": True}}}


class OperationAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.backend = Backend()
        self.now = 1000
        self.store = Store(self.tmp.name, "default", {"nextcloud": self.backend}, clock=lambda: self.now)
        config = {"url": "https://nc.test", "account": "arcenal-team", "scope": {"file.mkdir": ["ARCenal"]}}
        with self.store.transaction("fixture") as db:
            self.store._write(db, "connector", "nextcloud", {"config": config, "secret": "fixture-only-secret", "revision": 1, "state": "connecte"})
        self.allowed = True
        self.operations = Operations(self.store, lambda actor: actor == "owner" and self.allowed, lambda: HOST_ACTIONS)
        self.plan = {"summary": "Créer les deux dossiers demandés", "consequences": ["Deux dossiers seront ajoutés dans ARCenal."],
                     "rollback": "Retirer uniquement ces dossiers s'ils sont vides, après autorisation.",
                     "steps": [connector_step("ARCenal/A"), connector_step("ARCenal/B")]}

    def test_one_explicit_approval_executes_and_verifies_the_whole_operation(self):
        pending = self.operations.prepare(self.plan)
        self.assertEqual(pending["question"], "Est-ce que je peux le faire ?")
        self.assertEqual(pending["question"], QUESTION)
        self.assertFalse(self.backend.calls)
        result = self.operations.decide("owner", pending["id"], pending["digest"], True)
        self.assertEqual(result["state"], "done")
        self.assertEqual(self.backend.calls, [("file.mkdir", "ARCenal/A"), ("file.exists", "ARCenal/A"),
                                             ("file.mkdir", "ARCenal/B"), ("file.exists", "ARCenal/B")])
        self.assertEqual(len(result["results"]), 2)
        self.assertTrue(all(item["verified"] for item in result["results"]))
        self.assertNotIn("fixture-only-secret", json.dumps(result))
        with self.assertRaises(Denied):
            self.operations.decide("owner", pending["id"], pending["digest"], True)

    def test_refusal_wrong_actor_or_changed_plan_never_execute(self):
        pending = self.operations.prepare(self.plan)
        with self.assertRaises(Denied):
            self.operations.decide("agent", pending["id"], pending["digest"], True)
        with self.assertRaises(Denied):
            self.operations.decide("owner", pending["id"], "wrong", True)
        self.operations.decide("owner", pending["id"], pending["digest"], False)
        with self.assertRaises(Denied):
            self.operations.decide("owner", pending["id"], pending["digest"], True)
        second = self.operations.prepare(self.plan)
        self.now += 901
        self.assertFalse(self.backend.calls)
        self.assertEqual(self.operations.decide("owner", second["id"], second["digest"], True)["state"], "done")

    def test_failed_proof_is_not_a_success_and_stops_following_steps(self):
        pending = self.operations.prepare(self.plan)
        self.backend.fail_proof = True
        result = self.operations.decide("owner", pending["id"], pending["digest"], True)
        self.assertEqual(result["state"], "error")
        self.assertEqual(result["failed_step"], 0)
        self.assertEqual(len(self.backend.calls), 2)
        self.assertFalse(result["results"][0]["verified"])
        self.assertTrue(result["rollback"])

    def test_changed_connector_requires_a_new_announced_plan(self):
        pending = self.operations.prepare(self.plan)
        with self.store.transaction("fixture") as db:
            connection = self.store._read(db, "connector", "nextcloud")
            connection["revision"] += 1
            self.store._write(db, "connector", "nextcloud", connection)
        with self.assertRaises(Denied):
            self.operations.decide("owner", pending["id"], pending["digest"], True)
        self.assertFalse(self.backend.calls)

    def test_model_cannot_send_a_confirmed_flag_as_consent(self):
        with self.assertRaises(Denied):
            self.operations.prepare(self.plan | {"confirmed": True})
        self.assertFalse(self.backend.calls)

    def test_authenticated_application_not_agent_supplies_the_single_consent(self):
        policy = Path(self.tmp.name) / "policy.json"
        policy.write_text(json.dumps({"schema": 1, "origin": "https://agent.test:9443", "vault_root": self.tmp.name,
                         "profile_uids": {"default": 1234}, "principals": {"owner": {"role": "admin", "profiles": ["default"]}}}))
        authority = Authority(policy, {"nextcloud": self.backend})
        pending = authority.dispatch("agent", {}, "POST", "/v1/operations", {"plan": self.plan}, peer_uid=1234)
        body = {"digest": pending["digest"], "accept": True}
        path = "/v1/operations/" + pending["id"] + "/decision"
        with self.assertRaises(Denied):
            authority.dispatch("agent", {}, "POST", path, body, peer_uid=1234)
        headers = {"X-ARCenal-User": "owner", "Origin": "https://agent.test:9443", "X-ARCenal-Intent": "manage"}
        self.assertEqual(authority.dispatch("admin", headers, "POST", path, body)["state"], "done")
        self.assertEqual(len(self.backend.calls), 4)

    def test_capability_description_comes_from_the_host_without_execution(self):
        descriptor = self.operations.describe_cli(["user", "create"])
        self.assertEqual(descriptor["api"], "POST /users")
        self.assertEqual(descriptor["arguments"]["-p"]["full"], "--password")
        self.assertFalse(self.backend.calls)

    def test_official_cli_is_not_restricted_to_the_old_six_actions(self):
        step = {"kind": "yunohost_cli", "argv": ["user", "create", "service-user", "--password", "@server-secret"],
                "generate_secrets": ["--password"], "verify": {"argv": ["user", "info", "service-user"], "expected": {"username": "service-user"}}}
        pending = self.operations.prepare(self.plan | {"steps": [step]})
        helper = type("Helper", (), {})()
        helper.approved_cli = lambda *args: {"ok": True, "verified": True}
        self.store.plugins["yunohost"] = type("YunoHost", (), {"helper": helper})()
        result = self.operations.decide("owner", pending["id"], pending["digest"], True)
        self.assertEqual(result["state"], "done")
        self.assertNotIn("generated_values", json.dumps(self.operations.state("owner")))

    def test_interrupted_operation_is_not_replayed(self):
        pending = self.operations.prepare(self.plan)
        with patch.object(self.operations, "_execute", side_effect=SystemExit("process loss")):
            with self.assertRaises(SystemExit):
                self.operations.decide("owner", pending["id"], pending["digest"], True)
        self.operations.recover_interrupted()
        self.assertEqual(self.operations.status(pending["id"])["state"], "unknown")
        self.assertFalse(self.backend.calls)


class CliAuthorityTests(unittest.TestCase):
    def test_historical_identity_uses_the_same_explicit_question(self):
        directory = ROOT.parent / "arcenal-agent/plugins/arcenal-supervisor"
        if not (directory / "__init__.py").is_file():
            self.skipTest("Checkout historique absent ; politique active testée séparément.")
        spec = importlib.util.spec_from_file_location("arcenal_policy_historical", directory / "__init__.py",
                                                     submodule_search_locations=[str(directory)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

        class Context:
            def __init__(self):
                self.sections = []

            def register_system_prompt_section(self, **section):
                self.sections.append(section)

            def register_tool(self, **tool):
                return None

        context = Context()
        module.register(context)
        self.assertIn(QUESTION, context.sections[0]["content"])
        self.assertIn("administrateur opérationnel", context.sections[0]["content"])

    def test_official_entrypoint_runs_without_a_secret_in_a_child_command_line(self):
        password = "fixture-password-in-memory"

        def official_entrypoint(path, run_name):
            self.assertEqual(path, "/usr/bin/yunohost")
            self.assertEqual(sys.argv[-1], password)
            print(json.dumps({"username": "service-user", "password": password}))
            raise SystemExit(0)

        with patch("arcenal_connectors.cli_authority.runpy.run_path", side_effect=official_entrypoint):
            code, value = invoke(["user", "create", "service-user", "--password", password])
        self.assertEqual(code, 0)
        self.assertEqual(value["username"], "service-user")

    def test_generated_password_is_only_in_runner_memory_and_no_output_is_exposed(self):
        calls = []
        password = "fixture-private-generated-password"

        def runner(argv):
            calls.append(argv)
            return (0, {"username": "service-user", "password": password})

        result = execute(["user", "create", "service-user", "--password", "@server-secret"],
                         ["user", "info", "service-user"], {"username": "service-user"},
                         {"--password": password}, HOST_ACTIONS, runner)
        self.assertTrue(result["verified"])
        self.assertEqual(calls[0][-1], password)
        self.assertNotIn(password, json.dumps(result))
        self.assertEqual(calls[1][-2:], ["--output-as", "json"])

    def test_interactive_unknown_and_secret_inline_commands_are_refused(self):
        for argv in (["app", "shell", "arcenal"], ["unknown", "command"],
                     ["user", "create", "alice", "--password", "raw-password"], ["app", "install", "pkg", "--args", "password=raw"]):
            with self.subTest(argv=argv), self.assertRaises(Denied):
                validate(argv, HOST_ACTIONS)
        with self.assertRaises(Denied):
            validate(["user", "delete", "alice"], HOST_ACTIONS, verification=True)
