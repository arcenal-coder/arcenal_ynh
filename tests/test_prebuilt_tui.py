"""Le service géré doit lancer le TUI construit sans préparer de dépendances."""

import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch


PACKAGE = Path(__file__).parents[1]


class PrebuiltTuiTests(unittest.TestCase):
    def test_service_selects_prebuilt_tui_without_runtime_build(self):
        from hermes_cli.main_tui_launch import _make_tui_argv

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tui = root / "ui-tui"
            (tui / "dist").mkdir(parents=True)
            (tui / "dist/entry.js").write_text("// built fixture\n")
            rendered = (PACKAGE / "conf/arcenal.service").read_text().replace("__INSTALL_DIR__", directory)
            environment = {key: value for line in rendered.splitlines()
                           if line.startswith("Environment=")
                           for key, value in [line.removeprefix("Environment=").split("=", 1)]}
            environment["HERMES_NODE"] = shutil.which("node") or "/missing/node"
            with patch.dict(os.environ, environment), \
                    patch("hermes_cli.main_tui_launch._tui_need_rebuild", return_value=True) as freshness, \
                    patch("hermes_cli.source_build.source_build_env", side_effect=RuntimeError("Runtime build attempted")) as build:
                argv, cwd = _make_tui_argv(tui, tui_dev=False)
            self.assertEqual(argv[-1], str(tui / "dist/entry.js"))
            self.assertEqual(cwd, tui)
            freshness.assert_not_called()
            build.assert_not_called()


if __name__ == "__main__":
    unittest.main()
