"""Exécute la configuration Bash avec les réponses standard de l'API YunoHost."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


PACKAGE = Path(__file__).parents[1]
HARNESS = r'''
set -e
source "$COMMON"
install() { return 0; }
chmod() { return 0; }
ynh_exec_as_app() { return 0; }
ynh_config_add_nginx() { return 0; }
hermes_admin_permission() { return 0; }
hermes_connectors_configure() { return 0; }
hermes_connectors_install_layer() { return 0; }
ynh_config_add_systemd() { return 0; }
yunohost() {
    case "$1 $2" in
        "service add") return 0 ;;
        "app info") printf '%s\n' "$APP_INFO" ;;
        "app change-label") printf '%s\n' "$3" "$4" > "$EVENTS" ;;
        *) return 1 ;;
    esac
}
hermes_configure
'''


class AppLabelTests(unittest.TestCase):
    def check_label(self, info, expected):
        with tempfile.TemporaryDirectory() as directory:
            events = Path(directory) / "events"
            env = dict(os.environ, COMMON=str(PACKAGE / "scripts/_common.sh"),
                       APP_INFO=json.dumps(info), EVENTS=str(events), app="arcenal",
                       install_dir=directory, data_dir=directory, hermes_python="fixture")
            result = subprocess.run(["bash", "-c", HARNESS], env=env,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(events.read_text().splitlines() if events.exists() else [], expected)

    def test_migrates_standard_default_name(self):
        self.check_label({"id": "arcenal", "name": "Hermes Agent"}, ["arcenal", "ARCenal Agent"])

    def test_preserves_custom_or_already_migrated_name(self):
        for name in ("Assistant personnel", "ARCenal Agent", ""):
            with self.subTest(name=name):
                self.check_label({"id": "arcenal", "name": name}, [])

    def test_does_not_infer_a_default_name_from_missing_metadata(self):
        self.check_label({"id": "arcenal"}, [])
