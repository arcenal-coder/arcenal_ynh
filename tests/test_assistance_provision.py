import grp
import importlib.machinery
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

LOADER = importlib.machinery.SourceFileLoader("assistance_provision", str(Path(__file__).parents[1] / "conf/arcenal-assistance-provision"))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
helper = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(helper)


class ProvisionTests(unittest.TestCase):
    def test_order_of_install_or_restore_and_key_persistence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            install = root / "matos"
            install.mkdir()
            configs = {"arcenal": {"domain": "agent.example.test", "path": "/arcenal", "data_dir": str(root / "data"), "assistance_proxy_key": "proxy-key"}}
            with patch.object(helper, "settings", side_effect=lambda _, app: configs.get(app)), \
                    patch.object(helper.grp, "getgrnam", return_value=grp.getgrgid(os.getgid())), patch.object(helper.os, "fchown"):
                helper.provision(root, root / "registry")
                self.assertEqual(json.loads((root / "registry/agent.json").read_text())["applications"], {})
                configs["arcenal-matos"] = {"domain": "matos.example.test", "install_dir": str(install)}
                helper.provision(root, root / "registry")
                first = json.loads((install / ".assistance.json").read_text())
                configs["arcenal"]["domain"] = "new.example.test"
                helper.provision(root, root / "registry")
                second = json.loads((install / ".assistance.json").read_text())
                central = json.loads((root / "registry/agent.json").read_text())
                self.assertEqual(first["key"], second["key"])
                self.assertEqual(second["key"], central["applications"]["arcenal-matos"]["key"])
                self.assertEqual(second["sso_url"], "https://new.example.test/arcenal/assistance/")
                self.assertEqual((install / ".assistance.json").stat().st_mode & 0o777, 0o640)

    def test_old_agent_without_contract_does_not_fabricate_connection(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(helper, "settings", return_value={"domain": "old.example.test"}):
            root = Path(temporary)
            helper.provision(root, root / "registry")
            self.assertFalse((root / "registry").exists())


if __name__ == "__main__":
    unittest.main()
