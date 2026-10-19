"""Provisionnement et restauration sur chemins temporaires ; aucune identité OS créée."""

import io
import hashlib
import json
import os
from pathlib import Path
import sys
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import Mock


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "connectors"))
from arcenal_connectors.backup import restore  # noqa: E402
from arcenal_connectors.contracts import Denied  # noqa: E402
from arcenal_connectors.provision import bootstrap, install_plugins  # noqa: E402


class ConnectorMigrationTests(unittest.TestCase):
    def test_backup_is_private_before_tar_and_keeps_last_snapshot_on_failure(self):
        program = r'''
set -e
source "$COMMON"
ynh_app_setting_get() { printf '%s\n' 1; }
ynh_backup() { return 0; }
tar() {
    python3 -c 'import os,sys; from pathlib import Path; assert os.stat(sys.argv[1]).st_mode & 0o777 == 0o600; print("private-before-write"); Path(sys.argv[1]).write_bytes(b"partial")' "${2#--file=}"
    return 1
}
hermes_connectors_backup
'''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            previous = root / ".ynh-connectors-snapshot.tar"
            previous.write_bytes(b"previous-good-backup")
            previous.chmod(0o600)
            result = subprocess.run(["bash", "-c", program], text=True, capture_output=True,
                env=dict(os.environ, COMMON=str(ROOT / "scripts/_connectors.sh"), install_dir=directory, app="fixture"))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("private-before-write", result.stdout, result.stderr)
            self.assertEqual(previous.read_bytes(), b"previous-good-backup")
            self.assertEqual(list(root.glob(".ynh-connectors-snapshot.??????")), [])

    def test_bootstrap_preserves_existing_secrets_and_revocations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "hermes"
            home.mkdir()
            if os.getuid() == 0:
                os.chown(home, 65534, 65534)
            (home / ".env").write_text("# intact\nEXISTING_KEY=fixture-only\n")
            (home / "config.yaml").write_text("# modèle conservé\nmodel: fixture\n")
            policy = root / "etc/policy.json"
            bootstrap(policy, str(root / "vault"), home, "client_a", ["admin.a"], "https://server.test:9443")
            env = (home / ".env").read_bytes()
            saved = json.loads(policy.read_text())
            saved["principals"] = {}
            policy.write_text(json.dumps(saved))
            bootstrap(policy, str(root / "vault"), home, "client_a", ["admin.a"], "https://server.test:9443")
            self.assertEqual((home / ".env").read_bytes(), env)
            self.assertTrue(env.startswith(b"# intact\nEXISTING_KEY=fixture-only\n"))
            self.assertEqual(json.loads(policy.read_text())["principals"], {})
            self.assertEqual((home / "config.yaml").read_text(), "# modèle conservé\nmodel: fixture\n")

    def test_two_clients_cannot_share_a_runtime_uid(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, b = root / "a", root / "b"
            a.mkdir()
            b.mkdir()
            if os.getuid() == 0:
                os.chown(a, 65534, 65534)
                os.chown(b, 65534, 65534)
            policy = root / "policy.json"
            bootstrap(policy, str(root / "vault"), a, "client_a", ["admin"], "https://server.test:9443")
            with self.assertRaises(Denied):
                bootstrap(policy, str(root / "vault"), b, "client_b", ["admin"], "https://server.test:9443")
            self.assertFalse((b / ".env").exists())

    def test_plugin_install_is_idempotent_and_refuses_custom_code(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            source = ROOT / "connectors/hermes-plugins"
            install_plugins(source, home, "https://server.test:9443")
            install_plugins(source, home, "https://server.test:9443")
            entry = home / "plugins/arcenal-connectors/dashboard/dist/index.js"
            entry.write_text("// personnalisation à préserver")
            original_hash = hashlib.sha256(entry.read_bytes()).digest()
            with self.assertRaises(Denied):
                install_plugins(source, home, "https://server.test:9443")
            self.assertEqual(hashlib.sha256(entry.read_bytes()).digest(), original_hash)

    def test_rollback_snapshot_keeps_vault_and_invalidates_old_host_uids(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            (source / "var/lib/arcenal-connectors/client_a").mkdir(parents=True)
            (source / "var/lib/arcenal-connectors/client_a/vault.key").write_bytes(b"fixture-vault-key")
            (source / "etc/arcenal-connectors").mkdir(parents=True)
            (source / "etc/arcenal-connectors/policy.json").write_text(json.dumps({
                "profile_uids": {"client_a": 999}, "principals": {"admin": {}}}))
            archive = root / "snapshot.tar"
            with tarfile.open(archive, "w") as tar:
                tar.add(source / "var/lib/arcenal-connectors", arcname="var/lib/arcenal-connectors")
                tar.add(source / "etc/arcenal-connectors", arcname="etc/arcenal-connectors")
            target = root / "restore"
            (target / "var/lib/arcenal-connectors").mkdir(parents=True)
            (target / "var/lib/arcenal-connectors/after-upgrade").write_text("à préserver")
            restore(archive, target)
            self.assertEqual((target / "var/lib/arcenal-connectors/client_a/vault.key").read_bytes(), b"fixture-vault-key")
            copies = list((target / "var/lib").glob("arcenal-connectors.before-restore-*"))
            self.assertEqual((copies[0] / "after-upgrade").read_text(), "à préserver")
            restored_policy = json.loads((target / "etc/arcenal-connectors/policy.json").read_text())
            self.assertEqual(restored_policy["profile_uids"], {})
            self.assertEqual(restored_policy["principals"], {"admin": {}})

    def test_restore_refuses_path_traversal_and_preserves_existing_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "bad.tar"
            with tarfile.open(archive, "w") as tar:
                member = tarfile.TarInfo("../../etc/passwd")
                member.size = 3
                tar.addfile(member, io.BytesIO(b"bad"))
            target = root / "restore"
            target.mkdir()
            with self.assertRaises(Denied):
                restore(archive, target)
            self.assertEqual(list(target.iterdir()), [])

    def test_restore_never_resurrects_a_revoked_delegation(self):
        from arcenal_connectors.store import Store

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            profiles = source / "var/lib/arcenal-connectors/profiles"
            plugin = Mock()
            plugin.execute.return_value = {"ok": True}
            store = Store(profiles, "client_a", {"nextcloud": plugin})
            plan = store.plan_configuration("admin", "nextcloud", {"url": "https://nextcloud.test", "account": "arcenal-a",
                 "secret": "fixture-only-secret", "scope": {"file.mkdir": ["ARCenal"]}})
            store.confirm_configuration("admin", plan["id"], True)
            store.manage("admin", "nextcloud", "test")
            request = store.propose("nextcloud", "file.mkdir", "ARCenal/test", {}, "session_a")
            store.decide("admin", request["id"], True, "limited", expires=store.clock() + 100)
            archive = root / "snapshot.tar"
            with tarfile.open(archive, "w") as tar:
                tar.add(source / "var/lib/arcenal-connectors", arcname="var/lib/arcenal-connectors")
            store.revoke("admin", store.list("admin")["grants"][0]["id"], confirmed=True)
            target = root / "restore"
            restore(archive, target)
            recovered = Store(target / "var/lib/arcenal-connectors/profiles", "client_a", {"nextcloud": plugin})
            self.assertTrue(recovered.list("admin")["grants"][0]["revoked"])
            connector = recovered.list("admin")["connectors"][1]
            self.assertTrue(connector["has_secret"])
            self.assertEqual(connector["state"], "a_tester")

    def test_private_vault_file_modes(self):
        from arcenal_connectors.store import Store

        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory, "client_a", {})
            self.assertEqual(os.stat(store.home).st_mode & 0o777, 0o700)
            self.assertEqual(os.stat(store.home / "vault.key").st_mode & 0o777, 0o600)
            self.assertEqual(os.stat(store.path).st_mode & 0o777, 0o600)
