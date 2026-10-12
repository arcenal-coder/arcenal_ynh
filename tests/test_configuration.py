"""Contrats de configuration exécutés avec le runtime Hermes réel."""

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "package_configuration", Path(__file__).parents[1] / "conf" / "configure.py"
)
configuration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(configuration)


class ConfigurationTests(unittest.TestCase):
    def test_primary_text_has_aa_contrast(self):
        def luminance(hex_color):
            channels = [int(hex_color[offset:offset + 2], 16) / 255 for offset in (1, 3, 5)]
            linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
            return sum(weight * channel for weight, channel in zip((0.2126, 0.7152, 0.0722), linear))

        for colors in (configuration.LIGHT, configuration.DARK):
            values = sorted((luminance(colors["primary"]), luminance(colors["primaryForeground"])))
            self.assertGreaterEqual((values[1] + 0.05) / (values[0] + 0.05), 4.5)

    def test_preserves_existing_themes_and_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            secret = home / ".env"
            secret.write_text("EXAMPLE_KEY=fixture-only\n")
            configuration.install_themes(home)
            custom = home / "dashboard-themes" / "gratitude-light.yaml"
            custom.write_text('{"name":"gratitude-light","label":"Personnalisé"}')
            configuration.install_themes(home)
            self.assertEqual(json.loads(custom.read_text())["label"], "Personnalisé")
            self.assertEqual(secret.read_text(), "EXAMPLE_KEY=fixture-only\n")
            self.assertEqual((home / "dashboard-themes/gratitude-dark.yaml").stat().st_mode & 0o777, 0o600)

    def test_initial_configuration_uses_native_hermes_loader(self):
        from hermes_cli.config import cfg_get, load_config

        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            with patch.dict(os.environ, {"HERMES_HOME": directory}):
                configuration.configure()
                config = load_config()
                self.assertEqual(cfg_get(config, "dashboard", "theme"), "gratitude-system")
                self.assertEqual(cfg_get(config, "terminal", "cwd"), directory)
                self.assertEqual((home / "config.yaml").stat().st_mode & 0o777, 0o600)

    def test_preserves_existing_hermes_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            config = home / "config.yaml"
            original = "# Personnalisation conservée\ndashboard:\n  theme: midnight\n"
            config.write_text(original)
            with patch.dict(os.environ, {"HERMES_HOME": directory}):
                configuration.configure()
            self.assertEqual(config.read_text(), original)

    def test_bootstrap_default_theme_is_initialized_to_gratitude(self):
        from hermes_cli.config import cfg_get, load_config

        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / "config.yaml").write_text("dashboard:\n  theme: default\n")
            with patch.dict(os.environ, {"HERMES_HOME": directory}):
                configuration.configure()
                self.assertEqual(cfg_get(load_config(), "dashboard", "theme"), "gratitude-system")

    def test_manual_default_theme_after_initialization_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            with patch.dict(os.environ, {"HERMES_HOME": directory}):
                configuration.configure()
                original = "# Choix utilisateur après installation\ndashboard:\n  theme: default\n"
                (home / "config.yaml").write_text(original)
                configuration.configure()
            self.assertEqual((home / "config.yaml").read_text(), original)

    def test_palettes_are_accepted_by_hermes(self):
        from hermes_cli.web_server_dashboard import _normalise_theme_definition

        for mode in ("light", "dark", "system"):
            with self.subTest(mode=mode):
                result = _normalise_theme_definition(configuration.theme(mode))
                self.assertIsNotNone(result)
                self.assertEqual(result["layoutVariant"], "standard")
                self.assertEqual(result["colorOverrides"]["primary"],
                                 configuration.theme(mode)["colorOverrides"]["primary"])
                if mode == "system":
                    self.assertIn("prefers-color-scheme:dark", result["customCSS"])


if __name__ == "__main__":
    unittest.main()
