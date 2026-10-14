"""One-time provider identifiers plus one pasted secret.

Only implemented Brain providers are supported. These functions never contact a
provider, infer missing identifiers, log input, or treat a login as an API key.
"""
from __future__ import annotations
import re
from uuid import UUID
from fastapi import HTTPException

SETUP_FIELDS = {
    "microsoft": [("client_id", "Application client ID"),
                  ("directory_id", "Directory (tenant) ID")],
    "rea": [("client_id", "Partner client ID"), ("agency_id", "REA agency ID")],
    "google": [("client_id", "Google OAuth client ID")],
}

def setup_fields(provider: str) -> list[dict[str, str]]:
    if provider not in SETUP_FIELDS:
        raise HTTPException(422, "Direct key entry is not available for this connector yet. Open its setup guide.")
    return [{"key": key, "label": label} for key, label in SETUP_FIELDS[provider]]

def validate_setup(provider: str, values: dict[str, str]) -> dict[str, str]:
    fields = setup_fields(provider)
    if set(values) != {field["key"] for field in fields}:
        raise HTTPException(400, "Complete only the identifier fields in the setup guide. Do not put a secret in this form.")
    result = {key: value.strip() for key, value in values.items()}
    if any(not value or len(value) > 512 or not re.fullmatch(r"[A-Za-z0-9_.@-]+", value)
           for value in result.values()):
        raise HTTPException(400, "Enter the provider identifiers, not a URL, password or credential file.")
    if any(value.lower() in {"testing123", "testing12345"} for value in result.values()):
        raise HTTPException(400, "testing123 is a CircleLogic login, not a provider identifier. Copy the IDs from your provider account.")
    if provider == "microsoft":
        for field, label in [("client_id", "Application client ID"), ("directory_id", "Directory (tenant) ID")]:
            try:
                if str(UUID(result[field])) != result[field].lower():
                    raise ValueError()
            except (ValueError, AttributeError):
                raise HTTPException(400, "Copy the Microsoft " + label + " from the app registration Overview, not a username or URL.") from None
    if provider == "google" and not re.fullmatch(r"[A-Za-z0-9._-]+\.apps\.googleusercontent\.com", result["client_id"]):
        raise HTTPException(400, "Copy the OAuth client ID for a Web application from Google Cloud. It should end in .apps.googleusercontent.com.")
    if provider == "rea" and not re.fullmatch(r"[A-Za-z0-9_-]{1,150}", result["agency_id"]):
        raise HTTPException(400, "Use the agency ID authorised by REA, not a URL or agency name.")
    return result

def validate_key(value: str) -> str:
    key = value.strip()
    if not key or len(key) > 16000 or any(ord(c) < 32 or ord(c) == 127 for c in key):
        raise HTTPException(400, "Paste one API key or client secret, on a single line.")
    if key.lower() in {"testing123", "testing12345", "123456"}:
        raise HTTPException(400, "That is a CircleLogic test login or code, not an API key. Use the provider's client secret Value.")
    if key.startswith(("{", "[")):
        raise HTTPException(400, "Paste only the client secret Value, not a JSON file or the full connection details.")
    return key
