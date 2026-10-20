"""Install the distribution overlay with one explicit, version-pinned mount."""
import argparse
import shutil
from pathlib import Path

MOUNT = "\n# ARCenal YunoHost read-only assistance overlay.\nfrom arcenal_assistance.api import install as _install_assistance\n_install_assistance(app)\n"


def prepare(source):
    target = source / "hermes_cli/web_server.py"
    text = target.read_text()
    if "app = FastAPI(" not in text or "def start_server(" not in text:
        raise ValueError("Point de montage natif absent.")
    if MOUNT not in text:
        target.write_text(text + MOUNT)
    shutil.copytree(Path(__file__).with_name("arcenal_assistance"), source / "arcenal_assistance", dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    prepare(parser.parse_args().source)
