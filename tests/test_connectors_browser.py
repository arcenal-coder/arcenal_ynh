"""Vrai bundle React et API centrale dans Chrome ; le proxy simule seulement SSOwat."""

from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "connectors"))
from arcenal_connectors.server import Authority, handler  # noqa: E402


class ConnectorBrowserTests(unittest.TestCase):
    def test_central_console_bundle_and_security_headers(self):
        assets = ROOT / "connectors/arcenal_connectors/ui"
        chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        if not chrome.exists() or not (assets / "app.js").is_file():
            self.skipTest("Chrome et bundle central requis.")
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryFile() as logs:
            policy = Path(directory) / "policy.json"
            policy.write_text(json.dumps({"origin": "https://server.test:9443", "vault_root": directory,
                "principals": {"admin": {"role": "admin", "profiles": ["default"]}}, "agent_tokens": {}}))
            authority = Authority(policy)
            backend = HTTPServer(("127.0.0.1", 0), handler(authority, "admin", assets))
            threads = [threading.Thread(target=backend.serve_forever, daemon=True)]

            class Proxy(BaseHTTPRequestHandler):
                def log_message(self, *_):
                    return

                def do_GET(self):
                    if not self.path.startswith("/arcenal/"):
                        self.send_error(404)
                        return
                    path = self.path[len("/arcenal"):]
                    if path.startswith("/api/arcenal-connectors/"):
                        path = path[len("/api/arcenal-connectors"):]
                    request = Request(f"http://127.0.0.1:{backend.server_port}" + path,
                                      headers={"X-ARCenal-User": "admin"})
                    with urlopen(request, timeout=5) as response:
                        self.send_response(response.status)
                        for key in ("Content-Type", "Content-Security-Policy", "X-Frame-Options", "Cache-Control"):
                            self.send_header(key, response.headers[key])
                        self.end_headers()
                        self.wfile.write(response.read())

            proxy = ThreadingHTTPServer(("127.0.0.1", 0), Proxy)
            threads.append(threading.Thread(target=proxy.serve_forever, daemon=True))
            for thread in threads:
                thread.start()
            try:
                address = f"http://127.0.0.1:{proxy.server_port}/arcenal/"
                with urlopen(address, timeout=5) as response:
                    self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
                    self.assertEqual(response.headers["X-Frame-Options"], "DENY")
                result = subprocess.run([str(chrome), "--headless=new", "--no-first-run", "--disable-background-networking",
                    f"--user-data-dir={directory}/chrome", "--dump-dom", "--virtual-time-budget=6000", address],
                    stdout=subprocess.PIPE, stderr=logs, text=True, timeout=45)
                self.assertEqual(result.returncode, 0)
                for text in ("Connecteurs", "Dolibarr", "Nextcloud", "YunoHost", "Non configuré", "Demandes de validation", "Délégations"):
                    self.assertIn(text, result.stdout)
                self.assertNotIn("Impossible de charger", result.stdout)
                self.assertNotIn("Administration réservée", result.stdout)
            finally:
                for server in (proxy, backend):
                    server.shutdown()
                    server.server_close()
                for thread in threads:
                    thread.join(timeout=5)
