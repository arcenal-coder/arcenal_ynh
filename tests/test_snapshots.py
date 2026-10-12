"""Teste les vrais scripts et tar ; seuls les appels YunoHost sont simulés."""

import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest


PACKAGE = Path(__file__).parents[1]
HARNESS = r'''
source() {
    case "$1" in
        /usr/share/yunohost/helpers) return 0 ;;
        ../settings/scripts/_common.sh) builtin source "$COMMON" ;;
        *) builtin source "$@" ;;
    esac
}
systemctl() { return 0; }
ynh_systemctl() { printf '%s\n' "$*" >> "$EVENTS"; }
ynh_backup() { printf '%s\n' "$*" >> "$EVENTS"; }
ynh_restore() {
    if [ "$1" = "$data_dir" ]; then
        python3 -c 'import os, shutil; shutil.rmtree(os.environ["data_dir"])'
    fi
}
ynh_abort_if_errors() { set -e; }
ynh_app_setting_get() { printf '%s\n' fixture-node; }
ynh_app_setting_set() { printf '%s\n' "$*" >> "$EVENTS"; }
ynh_config_add_systemd() { return 0; }
test() { if [ "$1" = -x ]; then return 0; else builtin test "$@"; fi; }
ynh_permission_url() { return 0; }
ynh_permission_update() { printf '%s\n' "$*" >> "$EVENTS"; }
ynh_die() { printf '%s\n' "$*" >&2; exit 1; }
yunohost() { printf '%s\n' '{"allowed":["admins","all_users"]}'; }
pgrep() {
    case "$WRITER" in
        active) return 0 ;;
        error) return 2 ;;
        transient)
            local count=0
            if [ -f "$POLL_COUNT" ]; then read -r count < "$POLL_COUNT"; fi
            count=$((count + 1))
            printf '%s\n' "$count" > "$POLL_COUNT"
            test "$count" -lt 3
            ;;
        *) return 1 ;;
    esac
}
sleep() { return 0; }
ps() { return 0; }
chown() { return 0; }
curl() { return 0; }
builtin source "$SCRIPT"
'''


def execute(script, home, writer="none"):
    env = dict(os.environ, app="fixture", install_dir=str(home / "app"),
               data_dir=str(home / "data"), domain="example.test", path="/arcenal",
               port="9119", COMMON=str(PACKAGE / "scripts/_common.sh"),
               SCRIPT=str(PACKAGE / "scripts" / script), EVENTS=str(home / "events"),
               WRITER=writer, POLL_COUNT=str(home / "polls"))
    return subprocess.run(["bash", "-c", HARNESS], env=env, capture_output=True, text=True)


class SnapshotTests(unittest.TestCase):
    def test_waits_for_transient_processes_before_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / "app").mkdir()
            (home / "data").mkdir()
            result = execute("backup", home, writer="transient")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((home / "app/.ynh-data-snapshot.tar").exists())
            self.assertEqual(int((home / "polls").read_text()), 3)

    def test_refuses_snapshot_if_process_check_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / "app").mkdir()
            (home / "data").mkdir()
            result = execute("backup", home, writer="error")
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((home / "app/.ynh-data-snapshot.tar").exists())

    def test_restores_frozen_database_not_late_live_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / "app").mkdir()
            (home / "data").mkdir()
            database = home / "data/state.db"
            with sqlite3.connect(database) as connection:
                connection.execute("create table messages (content text)")
                connection.execute("insert into messages values ('avant sauvegarde')")
            backup = execute("backup", home)
            self.assertEqual(backup.returncode, 0, backup.stderr)
            self.assertEqual((home / "app/.ynh-data-snapshot.tar").stat().st_mode & 0o777, 0o600)
            with sqlite3.connect(database) as connection:
                connection.execute("insert into messages values ('après sauvegarde')")
            large = home / "data/large-user-file"
            with large.open("wb") as stream:
                stream.truncate(500_000_001)
            restore = execute("restore", home)
            self.assertEqual(restore.returncode, 0, restore.stderr)
            with sqlite3.connect(database) as connection:
                self.assertEqual(connection.execute("pragma integrity_check").fetchone()[0], "ok")
                self.assertEqual(connection.execute("select content from messages").fetchall(),
                                 [("avant sauvegarde",)])
            self.assertTrue(list(home.glob("data.before-restore.*/data/state.db")))
            preserved = list(home.glob("data.before-restore.*/data/large-user-file"))
            self.assertEqual(preserved[0].stat().st_size, 500_000_001)
            self.assertIn("--remove=all_users", (home / "events").read_text())
            self.assertIn("/fixture-node/bin/node", (home / "events").read_text())

    def test_invalid_archive_keeps_original_data(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / "app").mkdir()
            (home / "data").mkdir()
            original = home / "data/original.txt"
            original.write_text("À préserver")
            (home / "app/.ynh-data-snapshot.tar").write_text("Archive invalide")
            result = execute("restore", home)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(original.read_text(), "À préserver")

    def test_refuses_live_writers_and_restarts_dashboard(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / "app").mkdir()
            (home / "data").mkdir()
            result = execute("backup", home, writer="active")
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((home / "app/.ynh-data-snapshot.tar").exists())
            self.assertIn("--action=start", (home / "events").read_text())


if __name__ == "__main__":
    unittest.main()
