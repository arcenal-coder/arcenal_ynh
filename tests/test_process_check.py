import importlib.util
from pathlib import Path
import sys
import unittest


spec = importlib.util.spec_from_file_location(
    "process_check", Path(__file__).parents[1] / "scripts/process_check.py"
)
checker = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = checker
spec.loader.exec_module(checker)


class ProcessCheckTests(unittest.TestCase):
    def test_real_session_managers_do_not_block(self):
        processes = checker.parse_processes("1890 1 Ss systemd\n1907 1890 S (sd-pam)\n")
        self.assertEqual(checker.application_processes(processes, lambda pid: "/usr/lib/systemd/systemd"), [])

    def test_python_writer_is_not_ignored(self):
        processes = checker.parse_processes("1890 1 Ss systemd\n1907 1890 S (sd-pam)\n2010 1 Sl python3\n")
        remaining = checker.application_processes(processes, lambda pid: "/usr/lib/systemd/systemd")
        self.assertEqual([process.pid for process in remaining], [2010])

    def test_names_cannot_impersonate_system_managers(self):
        processes = checker.parse_processes("1890 1 Ss systemd\n1907 1890 S (sd-pam)\n")
        remaining = checker.application_processes(processes, lambda pid: "/usr/bin/python3")
        self.assertEqual([process.pid for process in remaining], [1890, 1907])

    def test_orphan_pam_process_is_not_ignored(self):
        processes = checker.parse_processes("1907 999 S (sd-pam)\n")
        self.assertEqual(len(checker.application_processes(processes, lambda pid: "/usr/lib/systemd/systemd")), 1)

    def test_unreadable_executable_remains_blocking(self):
        def denied(pid):
            raise PermissionError("fixture")

        processes = checker.parse_processes("1890 1 Ss systemd\n")
        self.assertEqual(len(checker.application_processes(processes, denied)), 1)

    def test_exited_processes_cannot_write(self):
        processes = checker.parse_processes("2010 1 Z python3\n")
        self.assertEqual(checker.application_processes(processes, lambda pid: "/usr/bin/python3"), [])


if __name__ == "__main__":
    unittest.main()
