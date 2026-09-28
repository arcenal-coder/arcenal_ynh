"""Tests du catalogue fermé du broker privilégié."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch


SOURCE = Path(__file__).parents[1] / "conf/arcenal-privileged-broker"
LOADER = importlib.machinery.SourceFileLoader("arcenal_privileged_broker", str(SOURCE))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
assert SPEC and SPEC.loader
broker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(broker)


class BrokerTests(unittest.TestCase):
    def test_read_channel_accepts_yunohost_inventory(self) -> None:
        command = broker._command({"action_id": "yunohost.apps.read", "target": None}, True)

        self.assertEqual(command, ("/usr/bin/yunohost", "app", "list", "--output-as", "json"))

    def test_read_channel_rejects_mutation(self) -> None:
        with self.assertRaises(broker.BrokerContractError):
            broker._command({"action_id": "nginx.reload", "target": None}, True)

    def test_read_channel_accepts_bounded_certificate_domain(self) -> None:
        command = broker._command(
            {"action_id": "yunohost.certificate.read", "target": "example.test"},
            True,
        )

        self.assertEqual(command, ("/usr/bin/yunohost", "domain", "cert", "status", "example.test", "--output-as", "json"))

    def test_read_channel_rejects_unsafe_certificate_target(self) -> None:
        with self.assertRaises(broker.BrokerContractError):
            broker._command(
                {"action_id": "yunohost.certificate.read", "target": "../../root"},
                True,
            )

    def test_restart_accepts_only_catalogued_service(self) -> None:
        command = broker._command(
            {"action_id": "service.restart", "target": "nginx"},
            False,
        )

        self.assertEqual(command, ("/usr/bin/systemctl", "restart", "nginx"))

    def test_restart_rejects_unknown_service(self) -> None:
        with self.assertRaises(broker.BrokerContractError):
            broker._command({"action_id": "service.restart", "target": "ssh"}, False)

    def test_backup_creation_uses_the_yunohost_application_contract(self) -> None:
        command = broker._command({"action_id": "arcenal.backup.create", "target": None}, False)

        self.assertEqual(command, ("/usr/bin/yunohost", "backup", "create", "--apps", "arcenal"))

    def test_backup_restore_accepts_only_an_archive_name(self) -> None:
        command = broker._command({"action_id": "arcenal.backup.restore", "target": "arcenal-manual"}, False)

        self.assertEqual(command, ("/usr/bin/yunohost", "backup", "restore", "arcenal-manual", "--apps", "arcenal", "--force"))
        with self.assertRaises(broker.BrokerContractError):
            broker._command({"action_id": "arcenal.backup.restore", "target": "../../root"}, False)

    def test_backup_commands_receive_a_bounded_long_timeout(self) -> None:
        self.assertEqual(broker._command_timeout(("/usr/bin/yunohost", "backup", "create")), 1800)
        self.assertEqual(broker._command_timeout(("/usr/bin/systemctl", "restart", "nginx")), 120)

    def test_non_object_payload_is_rejected(self) -> None:
        with self.assertRaises(broker.BrokerContractError):
            broker._command(["nginx.reload"], False)

    def test_unknown_field_is_rejected(self) -> None:
        with self.assertRaises(broker.BrokerContractError):
            broker._command({"action_id": "nginx.reload", "target": None, "shell": "id"}, False)

    def test_target_is_rejected_when_action_has_none(self) -> None:
        with self.assertRaises(broker.BrokerContractError):
            broker._command({"action_id": "nginx.reload", "target": "nginx"}, False)

    def test_restart_is_verified_after_execution(self) -> None:
        restarted = subprocess.CompletedProcess(("/usr/bin/systemctl", "restart", "nginx"), 0, "", "")
        active = subprocess.CompletedProcess(("/usr/bin/systemctl", "is-active", "nginx"), 0, "active\n", "")

        with patch.object(broker, "_invoke", side_effect=[restarted, active]) as invoke:
            result = broker._run({"action_id": "service.restart", "target": "nginx"}, False)

        self.assertTrue(result["ok"])
        self.assertEqual(result["output"], "active")
        self.assertEqual(invoke.call_count, 2)

    def test_failed_restart_is_not_reported_as_active(self) -> None:
        failure = subprocess.CompletedProcess(("/usr/bin/systemctl", "restart", "nginx"), 1, "", "failed")

        with patch.object(broker, "_invoke", return_value=failure) as invoke:
            result = broker._run({"action_id": "service.restart", "target": "nginx"}, False)

        self.assertFalse(result["ok"])
        self.assertEqual(result["output"], "failed")
        invoke.assert_called_once()


if __name__ == "__main__":
    unittest.main()
