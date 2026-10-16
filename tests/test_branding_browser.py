"""Recette locale du vrai build dans Chrome, sans données ni secrets client."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from urllib.error import URLError
from urllib.request import Request, urlopen


class BrandingBrowserTests(unittest.TestCase):
    def test_brand_and_hidden_update_controls_with_real_browser(self):
        import hermes_cli

        source = Path(hermes_cli.__file__).parent.parent
        browser = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        if not browser.exists() or not (source / "hermes_cli/web_dist/index.html").exists():
            self.skipTest("Build web et Chrome local nécessaires à cette recette.")
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            backend_port = listener.getsockname()[1]

        class Proxy(BaseHTTPRequestHandler):
            def log_message(self, *args):
                return

            def do_GET(self):
                if not self.path.startswith("/arcenal/"):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.end_headers()
                    self.wfile.write(b"<title>SSO</title>")
                    return
                headers = dict(self.headers)
                headers.update({"Host": f"127.0.0.1:{backend_port}", "X-Forwarded-Prefix": "/arcenal"})
                try:
                    request = Request(f"http://127.0.0.1:{backend_port}" + self.path[len("/arcenal"):], headers=headers)
                    with urlopen(request, timeout=10) as received:
                        content = received.read()
                        self.send_response(received.status)
                        self.send_header("Content-Type", received.headers.get("Content-Type", "application/octet-stream"))
                        self.end_headers()
                        self.wfile.write(content)
                except (URLError, OSError):
                    self.send_error(502)

        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryFile() as logs:
            env = {"PATH": os.environ.get("PATH", ""), "HOME": directory,
                   "HERMES_HOME": directory, "PYTHONPATH": str(source),
                   "HERMES_RUNTIME_DIR": str(Path(directory) / "tools")}
            backend = subprocess.Popen(
                [sys.executable, "-c", f"from hermes_cli.web_server import start_server; start_server(port={backend_port}, open_browser=False, isolated=True)"],
                env=env, cwd=directory, stdout=logs, stderr=logs,
            )
            proxy = ThreadingHTTPServer(("127.0.0.1", 0), Proxy)
            worker = threading.Thread(target=proxy.serve_forever, daemon=True)
            worker.start()
            try:
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    try:
                        with urlopen(f"http://127.0.0.1:{backend_port}/", timeout=1) as ready:
                            if ready.status == 200:
                                break
                    except (URLError, TimeoutError):
                        time.sleep(0.1)
                else:
                    self.fail("Le backend local n'a pas démarré.")
                for page in ("sessions", "system"):
                    with self.subTest(page=page):
                        result = subprocess.run([
                            str(browser), "--headless=new", "--no-first-run", "--disable-background-networking",
                            f"--user-data-dir={directory}/chrome-{page}", "--dump-dom", "--virtual-time-budget=12000",
                            f"http://127.0.0.1:{proxy.server_port}/arcenal/{page}",
                        ], text=True, stdout=subprocess.PIPE, stderr=logs, timeout=45)
                        self.assertEqual(result.returncode, 0)
                        dom = result.stdout
                        self.assertTrue("<title>ARCenal Agent" in dom, "Titre ARCenal absent.")
                        sidebar = re.search(r"<aside\b[^>]*>(.*?)</aside>", dom, re.S)
                        self.assertIsNotNone(sidebar, "Navigation non rendue.")
                        sidebar_text = re.sub("<[^>]+>", "", sidebar.group(1))
                        self.assertTrue(re.search(r"ARCenal\s*Agent", sidebar_text) is not None, "Marque de navigation incorrecte.")
                        labels = [re.sub("<[^>]+>", "", value) for value in re.findall(r"<button\b[^>]*>(.*?)</button>", dom, re.S)]
                        self.assertFalse(any(re.search(r"Update Hermes|Mettre à jour Hermes|Check for updates|Apply update", value) for value in labels),
                                         "Un contrôle de mise à jour interne reste visible.")
            finally:
                backend.terminate()
                try:
                    backend.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    backend.kill()
                    backend.wait()
                proxy.shutdown()
                proxy.server_close()
