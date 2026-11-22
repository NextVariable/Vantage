"""Build a wheel, install it in a fresh venv and exercise both launchers."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def check(*args, cwd):
    subprocess.run([str(part) for part in args], cwd=cwd, check=True)


def main():
    with tempfile.TemporaryDirectory(prefix="vantage-wheel-") as folder:
        workspace = Path(folder)
        check(sys.executable, "-m", "pip", "wheel", "--no-deps", str(ROOT), "-w", workspace, cwd=workspace)
        wheel, = workspace.glob("sourceglint-*.whl")
        environment = workspace / "fresh"
        check(sys.executable, "-m", "venv", environment, cwd=workspace)
        win = os.name == "nt"
        bin_dir = environment / ("Scripts" if win else "bin")
        python = bin_dir / ("python.exe" if win else "python")
        check(python, "-m", "pip", "install", wheel, cwd=workspace)
        check(python, "-m", "pip", "check", cwd=workspace)
        for name in ("vantage", "sourceglint"):
            check(bin_dir / (name + (".exe" if win else "")), "--help", cwd=workspace)
        check(python, ROOT / "scripts" / "check_installed_runtime.py", cwd=workspace)


if __name__ == "__main__":
    main()
