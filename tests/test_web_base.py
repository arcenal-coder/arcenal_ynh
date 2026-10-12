import importlib.util
from pathlib import Path
import tempfile
import unittest


spec = importlib.util.spec_from_file_location(
    "prepare_web_base", Path(__file__).parents[1] / "conf/prepare_web_base.py"
)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class WebBaseTests(unittest.TestCase):
    def test_root_and_subpath_are_normalized(self):
        self.assertEqual(adapter.normalize_base("/"), "/")
        self.assertEqual(adapter.normalize_base("/arcenal"), "/arcenal/")
        self.assertEqual(adapter.normalize_base("/arcenal/"), "/arcenal/")

    def test_config_adapter_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "vite.config.ts"
            config.write_text("import { defineConfig } from 'vite';\nexport default defineConfig({\n  plugins: [],\n});\n")
            adapter.configure_base(config, "/arcenal")
            initial = config.read_text()
            adapter.configure_base(config, "/arcenal/")
            self.assertEqual(config.read_text(), initial)
            adapter.configure_base(config, "/")
            self.assertEqual(config.read_text().count(adapter.MARKER), 1)

    def test_unexpected_configuration_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "vite.config.ts"
            initial = "export default {};\n"
            config.write_text(initial)
            with self.assertRaises(ValueError):
                adapter.configure_base(config, "/arcenal")
            self.assertEqual(config.read_text(), initial)

    def test_invalid_base_is_rejected(self):
        for value in ("relative", "//outside.test", "/../assets", "/arcenal?x=1", "/arcenal\n"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                adapter.normalize_base(value)


if __name__ == "__main__":
    unittest.main()
