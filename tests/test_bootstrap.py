"""Contrats d'amorçage du paquet, sans modifier le Python de l'hôte."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import tomllib
import unittest


PACKAGE = Path(__file__).parents[1]
HARNESS = r'''
set -e
builtin source "$COMMON"
ynh_setup_source() {
    printf '%s\n' "$*" >> "$EVENTS"
    if [[ "$*" == *--source_id=python* ]] && [ "$MISSING" != yes ]; then
        mkdir -p "$install_dir/.bootstrap-python/bin"
        cp "$FIXTURE_PYTHON" "$install_dir/.bootstrap-python/bin/python3"
    fi
}
ynh_exec_as_app() {
    local arg old=false modern=false pm=false
    for arg in "$@"; do
        [ "$arg" != python3 ] || old=true
        [ "$arg" != "$install_dir/.bootstrap-python/bin/python3" ] || modern=true
        [ "$arg" != pm.build_env ] || pm=true
    done
    printf '%s\n' "$*" >> "$EVENTS"
    if $pm && { $old || ! $modern; }; then
        printf '%s\n' "TarFile.extractall() got an unexpected keyword argument 'filter'" >&2
        return 1
    fi
}
ynh_app_setting_set() { return 0; }
ynh_app_setting_get() { printf '%s\n' 22.23.1; }
test() {
    if [ "$1" = -x ] && [[ "$2" == /opt/node_n/* ]]; then return 0; fi
    builtin test "$@"
}
ynh_die() { printf '%s\n' "$*" >&2; exit 1; }
chown() { return 0; }
chmod() { return 0; }
python3() { return 0; }
hermes_build
'''


class BootstrapTests(unittest.TestCase):
    def execute(self, directory, missing="no"):
        home = Path(directory)
        (home / "app").mkdir()
        (home / "data").mkdir()
        fixture = home / "fixture-python"
        fixture.write_text("#!/bin/sh\nexit 0\n")
        fixture.chmod(0o755)
        env = dict(os.environ, app="fixture", path="/arcenal", install_dir=str(home / "app"),
                   data_dir=str(home / "data"), COMMON=str(PACKAGE / "scripts/_common.sh"),
                   FIXTURE_PYTHON=str(fixture), EVENTS=str(home / "events"), MISSING=missing)
        return subprocess.run(["bash", "-c", HARNESS], env=env, text=True, capture_output=True)

    def test_pm_uses_pinned_bootstrap_instead_of_host_python(self):
        with tempfile.TemporaryDirectory(prefix="Hermes bootstrap ") as directory:
            result = self.execute(directory)
            self.assertEqual(result.returncode, 0, result.stderr)
            events = (Path(directory) / "events").read_text()
            self.assertIn("--source_id=python", events)
            self.assertIn(".bootstrap-python/bin/python3 -m pm.build_env", events)

    def test_missing_bootstrap_aborts_before_pm(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.execute(directory, missing="yes")
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("pm.build_env", (Path(directory) / "events").read_text())

    def test_bootstrap_archives_match_the_hermes_tool_lock(self):
        import hermes_cli

        source = Path(hermes_cli.__file__).parent.parent
        lock = json.loads((source / "pm/lock.json").read_text())
        manifest = tomllib.loads((PACKAGE / "manifest.toml").read_text())
        bootstrap = manifest["resources"]["sources"]["python"]
        for architecture, target in (("amd64", "linux-x64"), ("arm64", "linux-arm64")):
            artifact = lock["packages"]["python"]["artifacts"][target]
            self.assertEqual(bootstrap[architecture]["url"], artifact["url"])
            self.assertEqual(bootstrap[architecture]["sha256"], artifact["sha256"])


if __name__ == "__main__":
    unittest.main()
