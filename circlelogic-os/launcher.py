"""Standard-library bootstrap for a local virtual environment. No API credentials."""
from pathlib import Path
import argparse
import hashlib
import os
import subprocess
import sys
import venv
ROOT = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "check", "create", "test"), nargs="?", default="start")
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        raise SystemExit("Install an approved Python 3.11+ interpreter, then run this launcher again.")
    os.chdir(ROOT)
    env_dir = ROOT / ".venv"
    python = env_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        print("Creating a local Python environment...", flush=True)
        venv.EnvBuilder(with_pip=True).create(env_dir)
    requirements = ROOT / "backend/requirements.txt"
    digest = hashlib.sha256(requirements.read_bytes()).hexdigest()
    stamp = env_dir / ".circlelogic-requirements"
    if not stamp.exists() or stamp.read_text().strip() != digest:
        print("Installing the pinned dependencies. This first step needs internet access to your approved Python package index.", flush=True)
        subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(requirements)],check=True)
        stamp.write_text(digest)
    commands = {
        "start": ["run.py"],
        "check": ["scripts/check_local.py"],
        "create": ["scripts/create_local_workspace.py"],
        "test": ["-m", "pytest", "backend/tests", "-q"],
    }
    return subprocess.call([str(python), *commands[args.action]], cwd=ROOT)

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nStopped.")
    except subprocess.CalledProcessError:
        raise SystemExit("Dependency installation failed. Check your approved Python package access; do not disable security tools or certificate checks.") from None
    except OSError as error:
        raise SystemExit("Local startup failed: " + str(error)) from None
