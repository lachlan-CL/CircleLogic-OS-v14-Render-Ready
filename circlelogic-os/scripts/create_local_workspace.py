"""Create a private local owner login. Passwords are read interactively, never as command arguments."""
from pathlib import Path
import getpass
import os
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]
from run import load_env
from app.config import Settings
from app.db import Store
from app.provision import create_workspace
load_env()
os.environ.setdefault("DATA_DIR", str(ROOT / "data"))
s = Settings.load()
if s.environment == "production":
    raise SystemExit("Use the reviewed operator provisioning route for production, not this local wizard.")
print("Create a separate local test workspace with a private login.")
print("No email is sent. Use only an approved test mailbox when connecting a provider.")
try:
    agency = input("Workspace name: ").strip()
    name = input("Your display name: ").strip()
    username = input("Choose a username (not testing123): ").strip()
    email = input("Your work email: ").strip()
    password = getpass.getpass("Choose a private password (at least 12 characters): ")
    if password != getpass.getpass("Repeat password: "):
        raise ValueError("Passwords did not match. No account was created.")
    result = create_workspace(Store(s.database), agency=agency, name=name, username=username, email=email, password=password)
except (KeyboardInterrupt, EOFError):
    raise SystemExit("Cancelled. No account was created.") from None
except Exception as error:
    raise SystemExit(getattr(error,"detail",None) or str(error)) from None
print("\nPrivate workspace created. Sign in at " + s.public_origin)
print("Username: " + result["username"])
print("First login requires your own authenticator. Keep the recovery codes private.")
