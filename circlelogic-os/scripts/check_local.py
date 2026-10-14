"""Check this installation without contacting Microsoft or any other provider."""
from pathlib import Path
import json
import os
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]
from run import load_env, local_address
from app.config import Settings
from app.db import Store
from app.security import Vault
load_env()
os.environ.setdefault("DATA_DIR", str(ROOT / "data"))
s = Settings.load()
try:
    local_address(s.public_origin)
except ValueError as error:
    raise SystemExit(str(error)) from None
store = Store(s.database)
vault = Vault(s.vault_key)
checks = {
    "python_311_or_newer": sys.version_info >= (3, 11),
    "database_available": store.one("SELECT 1 AS ok")["ok"] == 1,
    "vault_roundtrip": vault.open("setup", vault.seal("setup", {"test": True})) == {"test": True},
    "local_origin": s.public_origin,
    "microsoft_web_callback": s.public_origin + "/api/oauth/microsoft/callback",
    "provider_requests_made": False,
}
print(json.dumps(checks, indent=2))
print("This checks local setup only. It does not prove API access, data accuracy or production readiness.")
