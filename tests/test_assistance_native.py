"""Exercise the actual pinned, prepared Hermes dashboard, not a substitute app."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parents[1] / "conf"))
from arcenal_assistance import store


class NativeAssistanceTests(unittest.TestCase):
    def test_actual_dashboard_mount_and_native_auth_survive(self):
        from hermes_cli.web_server import app
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "config.json"
            config.write_text(json.dumps({"applications": {"arcenal-matos": {"key": "native-key", "verify_url": "https://matos.example.test/verify/"}},
                "proxy_key": "proxy-key", "state_dir": str(root / "state")}))
            with patch.object(store, "CONFIG", config):
                client = TestClient(app)
                response = client.post("/assistance/service", json={"application": "arcenal-matos", "operation": "pair"}, headers={"Authorization": "Bearer native-key"})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["state"], "pending")
                self.assertEqual(client.get("/assistance/", headers={"Remote-User": "admin"}).status_code, 401)
                self.assertEqual(client.get("/api/config").status_code, 401)


if __name__ == "__main__":
    unittest.main()
