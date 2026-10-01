from __future__ import annotations

import socket
import stat
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
HELPER = ROOT / "conf" / "arcenal-control-socket-ready"


class ControlSocketReadyTest(unittest.TestCase):
    def test_rejects_missing_socket_path(self) -> None:
        result = subprocess.run([HELPER], check=False, capture_output=True, text=True)
        self.assertEqual(result.returncode, 64)

    def test_rejects_invalid_attempt_limit(self) -> None:
        result = subprocess.run([HELPER, "/tmp/absent.sock", "invalid"], check=False)
        self.assertEqual(result.returncode, 64)

    def test_fails_when_socket_never_appears(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "absent.sock"
            result = subprocess.run([HELPER, path, "1"], check=False)
        self.assertEqual(result.returncode, 1)

    def test_waits_for_socket_and_restricts_its_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "control.sock"
            process = subprocess.Popen([HELPER, path, "30"])
            try:
                time.sleep(0.2)
                with socket.socket(socket.AF_UNIX) as server:
                    server.bind(str(path))
                    self.assertEqual(process.wait(timeout=5), 0)
                    mode = stat.S_IMODE(path.stat().st_mode)
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5)
        self.assertEqual(mode, 0o660)


if __name__ == "__main__":
    unittest.main()
