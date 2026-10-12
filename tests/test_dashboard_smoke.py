"""Vérifie le serveur HTTP Hermes réel, sans fournisseur ni serveur YunoHost."""

import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class DashboardSmokeTests(unittest.TestCase):
    def test_native_dashboard_prefix_and_themes(self):
        import hermes_cli

        source = Path(hermes_cli.__file__).parent.parent
        if not (source / "hermes_cli/web_dist/index.html").exists():
            self.skipTest("Le dashboard doit être construit avant ce test HTTP.")
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryFile() as logs:
            env = dict(PATH=os.environ.get("PATH", ""), HOME=directory, HERMES_HOME=directory,
                       HERMES_RUNTIME_DIR=str(Path(directory) / "tools"),
                       HERMES_NODE=shutil.which("node") or "", PYTHONPATH=str(source))
            prepare = Path(__file__).parents[1] / "conf/configure.py"
            # Reproduit le fichier générique déjà créé par l'amorçage PM.
            (Path(directory) / "config.yaml").write_text("dashboard:\n  theme: default\n")
            subprocess.run([sys.executable, str(prepare)], env=env, check=True, stdout=logs, stderr=logs)
            command = ("from hermes_cli.web_server import start_server; "
                       f"start_server(port={port}, open_browser=False, isolated=True)")
            server = subprocess.Popen([sys.executable, "-c", command], env=env,
                                      stdout=logs, stderr=logs, cwd=directory)
            try:
                root = self.wait_for_server(server, port)
                self.assertIn('/arcenal/assets/', root)
                self.assertIn('__HERMES_BASE_PATH__="/arcenal"', root)
                match = re.search(r'__HERMES_SESSION_TOKEN__="([^"]+)"', root)
                self.assertIsNotNone(match, "Le bootstrap de session Hermes est absent.")
                request = Request(f"http://127.0.0.1:{port}/api/dashboard/themes",
                                  headers={"Authorization": "Bearer " + match.group(1)})
                with urlopen(request, timeout=10) as response:
                    catalog = json.load(response)
                names = {theme["name"] for theme in catalog["themes"]}
                self.assertTrue({"gratitude-light", "gratitude-dark", "gratitude-system"} <= names)
                self.assertEqual(catalog["active"], "gratitude-system")
                with self.assertRaises(HTTPError) as refused:
                    urlopen(f"http://127.0.0.1:{port}/api/config", timeout=10)
                self.assertIn(refused.exception.code, (401, 403))
                refused.exception.close()
            finally:
                server.terminate()
                try:
                    server.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()

    def wait_for_server(self, server, port):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and server.poll() is None:
            request = Request(f"http://127.0.0.1:{port}/", headers={"X-Forwarded-Prefix": "/arcenal"})
            try:
                with urlopen(request, timeout=2) as response:
                    return response.read().decode()
            except (URLError, TimeoutError):
                time.sleep(0.1)
        self.fail("Le serveur Hermes n'a pas démarré dans l'environnement temporaire.")


if __name__ == "__main__":
    unittest.main()
