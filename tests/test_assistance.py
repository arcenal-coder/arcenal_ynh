import json
import logging
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parents[1] / "conf"))
from arcenal_assistance import api, store


class AssistanceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        config = root / "agent.json"
        config.write_text(json.dumps({"applications": {"arcenal-matos": {"key": "fixture-machine-key", "verify_url": "https://matos.example.test/verify/"}},
            "state_dir": str(root / "state"), "proxy_key": "fixture-proxy-key"}))
        self.patches = [patch.object(store, "CONFIG", config), patch.object(api.grp, "getgrnam", return_value=SimpleNamespace(gr_mem=["admin"]))]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        native = FastAPI()
        @native.get("/native")
        def native_route():
            return {"native": True}
        api.install(native)
        self.client = TestClient(native)
        self.headers = {"Remote-User": "admin", "X-ARCenal-Proxy": "fixture-proxy-key"}

    def exchange(self, operation, **values):
        return self.client.post("/assistance/service", headers={"Authorization": "Bearer fixture-machine-key"},
            json={"application": "arcenal-matos", "operation": operation, **values})

    def pair(self):
        return self.exchange("pair").json()["pair_id"]

    def approve(self, pair):
        page = self.client.get("/assistance/", params={"pair": pair}, headers=self.headers)
        self.assertEqual(page.status_code, 200)
        nonce = page.text.split('name="nonce" value="')[1].split('"')[0]
        data = {"pair": pair, "nonce": nonce, "decision": "approve"}
        self.assertEqual(self.client.post("/assistance/", data=data, headers=self.headers).status_code, 200)
        self.assertEqual(self.client.post("/assistance/", data=data, headers=self.headers).status_code, 403)

    def test_native_routes_unchanged_and_forged_sso_refused(self):
        self.assertEqual(self.client.get("/native").json(), {"native": True})
        pair = self.pair()
        for headers, status in (({}, 401), ({"Remote-User": "admin"}, 401), ({**self.headers, "Remote-User": "member"}, 403)):
            self.assertEqual(self.client.get("/assistance/", params={"pair": pair}, headers=headers).status_code, status)
        self.assertEqual(self.client.post("/assistance/service", json={"application": "arcenal-matos", "operation": "pair"}).status_code, 403)

    def test_bilateral_approval_revalidation_and_single_use(self):
        pair = self.pair()
        self.assertEqual(self.exchange("status", pair_id=pair).json()["state"], "pending")
        self.assertEqual(self.exchange("request", pair_id=pair, user="member", ticket="signed-ticket").status_code, 403)
        self.approve(pair)
        reference = self.exchange("request", pair_id=pair, user="member", ticket="signed-ticket").json()["reference"]
        headers = {**self.headers, "Remote-User": "member"}
        context = {"application": "arcenal-matos", "user": "member", "intention": "read_only_help", "resource_type": "module", "resource_id": "epi"}
        with patch.object(store, "post_json", return_value=context) as callback:
            self.assertEqual(self.client.get("/assistance/", params={"reference": reference}, headers=self.headers).status_code, 403)
            response = self.client.get("/assistance/", params={"reference": reference}, headers=headers)
            self.assertEqual(response.status_code, 200)
            callback.assert_called_once_with("https://matos.example.test/verify/", "fixture-machine-key", {"ticket": "signed-ticket", "user": "member", "pair_id": pair})
            for private in ("signed-ticket", "fixture-machine-key", "fixture-proxy-key", "member"):
                self.assertNotIn(private, response.text)
            self.assertEqual(self.client.get("/assistance/", params={"reference": reference}, headers=headers).status_code, 403)

    def test_expiration_revocation_and_no_actions(self):
        pair = self.pair()
        self.approve(pair)
        reference = self.exchange("request", pair_id=pair, user="member", ticket="signed-ticket").json()["reference"]
        now = store.time.time()
        with patch.object(store.time, "time", return_value=now + 61):
            self.assertEqual(self.client.get("/assistance/", params={"reference": reference}, headers={**self.headers, "Remote-User": "member"}).status_code, 403)
        self.assertEqual(self.exchange("revoke", pair_id=pair).json()["state"], "revoked")
        self.assertEqual(self.exchange("request", pair_id=pair, user="member", ticket="signed-ticket").status_code, 403)
        self.assertEqual(self.exchange("delete_asset", pair_id=pair).status_code, 403)
        self.assertEqual(self.exchange("pair", action="write").status_code, 403)

    def test_access_logs_do_not_keep_references(self):
        filter_ = api.AccessFilter()
        record = logging.LogRecord("uvicorn.access", 20, "", 0, "%s %s %s %s %s", ("ip", "GET", "/assistance/?reference=private", "1.1", 200), None)
        self.assertFalse(filter_.filter(record))
        record.args = ("ip", "GET", "/api/status", "1.1", 200)
        self.assertTrue(filter_.filter(record))


if __name__ == "__main__":
    unittest.main()
