"""Local setup/readiness facts. Never returns credentials or calendar contents."""
from __future__ import annotations
import json
import time
from urllib.parse import urlparse
from .catalog import CATALOG
from .services import conn_context

VERSION = "0.7.0"

def readiness(store, vault, settings, user):
    database_ok = store.one("SELECT 1 AS ready")["ready"] == 1
    probe = {"purpose": "in-memory-vault-check"}
    vault_ok = vault.open("readiness", vault.seal("readiness", probe)) == probe
    tenant = store.one("SELECT settings FROM tenants WHERE id=?", (user["tenant_id"],))
    config = json.loads(tenant["settings"]) if tenant else {}
    local = urlparse(settings.public_origin).hostname in ("localhost", "127.0.0.1", "::1")
    testing = bool(config.get("testing")) or user.get("username") == "testing123"
    return {
        "version": VERSION,
        "backend_running": True,
        "database_available": database_ok,
        "vault_roundtrip_ok": vault_ok,
        "environment": settings.environment,
        "local_origin": local,
        "https": settings.secure,
        "configured_origin": settings.public_origin,
        "testing_workspace": testing,
        "mfa_enabled": bool(user["mfa_enabled"]),
        "microsoft_callback": settings.public_origin + "/api/oauth/microsoft/callback",
        "google_callback": settings.public_origin + "/api/oauth/google/callback",
        "warning": ("This workspace uses the published testing login. Use it only with fabricated data. "
                    "Run CREATE-PRIVATE-WORKSPACE before connecting an approved test mailbox." if testing else
                    "Use only an approved test mailbox here. This check is not a provider login or a security certification."),
        "provider_requests_made": False,
    }

def diagnostics(store, vault, settings, user, provider, connection, owner):
    meta = CATALOG[provider]
    c = connection or {}
    has_credentials = bool(c.get("credentials"))
    credentials = {}
    vault_ok = True
    if has_credentials:
        try:
            credentials = vault.open(conn_context(user["tenant_id"], provider, owner), c["credentials"])
        except Exception:
            vault_ok = False  # Do not expose encryption errors or stored material.
    is_oauth = meta["auth"] == "oauth"
    access = bool(credentials.get("access_token"))
    refresh = bool(credentials.get("refresh_token"))
    expires = credentials.get("expires_at", 0)
    try:
        expires_soon = float(expires) < time.time() + 60
    except (ValueError, TypeError):
        expires_soon = True
    if not meta["implemented"]:
        next_action = "connector_pending"
    elif not has_credentials:
        next_action = "save_credentials"
    elif not vault_ok:
        next_action = "replace_credentials"
    elif is_oauth and (not access or (expires_soon and not refresh)):
        next_action = "authorise"
    else:
        next_action = "sync"
    snapshots = []
    if c.get("id"):
        for s in store.all("SELECT kind,synced_at FROM snapshots WHERE connection_id=?", (c["id"],)):
            count = store.one("SELECT COUNT(*) AS n FROM records WHERE tenant_id=? AND connection_id=? AND owner_id=? AND kind=?",
                              (user["tenant_id"], c["id"], owner, s["kind"]))["n"]
            snapshots.append({"kind": s["kind"], "records": count, "synced_at": s["synced_at"]})
    return {
        "provider": provider,
        "name": meta["name"],
        "implemented": meta["implemented"],
        "private_to_login": bool(meta.get("private")),
        "credentials_saved": has_credentials,
        "stored_credentials_readable": vault_ok if has_credentials else None,
        "authorisation_present": access if is_oauth else None,
        "refresh_available": refresh if is_oauth else None,
        "access_refresh_due": expires_soon if access else None,
        "callback": settings.public_origin + "/api/oauth/" + provider + "/callback" if is_oauth else None,
        "requested_permissions": (["Calendars.ReadBasic", "offline_access"] if provider == "microsoft" else
                                  ["https://www.googleapis.com/auth/calendar.events.readonly"] if provider == "google" else []),
        "next_action": next_action,
        "status": c.get("status", "not_connected"),
        "last_success": c.get("last_success") if c.get("status") != "disconnected" else None,
        "last_error": c.get("error"),
        "snapshots": snapshots,
        "provider_requests_made": False,
        "note": "These are local setup facts, not proof of provider access. Test and sync performs the actual read-only import.",
    }
