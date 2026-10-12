import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest


spec = importlib.util.spec_from_file_location(
    "repair_process_check", Path(__file__).parents[1] / "scripts/repair_process_check.py"
)
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)


class RepairTests(unittest.TestCase):
    def test_replaces_only_quiescence_function(self):
        original = (b"#!/bin/bash\nhermes_build() { echo unchanged; }\n"
                    b"hermes_quiescent_data() {\n return 1\n}\n\n"
                    b"hermes_retire_privileges() { echo unchanged; }\n")
        fixed = b"hermes_quiescent_data() {\n return 0\n}\n"
        result = repair.replace_function(original, fixed)
        self.assertTrue(result.startswith(b"#!/bin/bash\nhermes_build() { echo unchanged; }\n"))
        self.assertTrue(result.endswith(b"hermes_retire_privileges() { echo unchanged; }\n"))
        self.assertIn(fixed, result)
        executed = subprocess.run(["bash"], input=result + b"hermes_quiescent_data\n", capture_output=True)
        self.assertEqual(executed.returncode, 0, executed.stderr)

    def test_refuses_unknown_installed_script(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            original = b"# Personnalisation utilisateur\n"
            (home / "_common.sh").write_bytes(original)
            with self.assertRaises(ValueError):
                repair.repair(home, b"pass\n", b"placeholder")
            self.assertEqual((home / "_common.sh").read_bytes(), original)
            self.assertFalse((home / "process_check.py").exists())


if __name__ == "__main__":
    unittest.main()
