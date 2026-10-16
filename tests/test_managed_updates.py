import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class ManagedUpdatesTests(unittest.TestCase):
    def test_external_install_disallows_local_dashboard_updates(self):
        from hermes_cli import web_server, web_server_files

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "install-stamp.json").write_text(json.dumps({"updateMechanism": "external"}))
            with patch.object(web_server, "PROJECT_ROOT", root):
                self.assertTrue(web_server_files._dashboard_local_update_managed_externally())


if __name__ == "__main__":
    unittest.main()
