"""Loopback-only development launcher. Does not publish the application."""
from pathlib import Path
import argparse
import os
import sys
from urllib.parse import urlparse
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))

def load_env():
    file = ROOT / ".env"
    if not file.exists():
        return
    for raw in file.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise SystemExit("Invalid .env line; expected NAME=value.")
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))

def local_address(origin):
    parsed = urlparse(origin)
    if (parsed.scheme != "http" or parsed.hostname not in ("localhost", "127.0.0.1")
            or parsed.username or parsed.password or parsed.path not in ("", "/")
            or parsed.query or parsed.fragment):
        raise ValueError("Local startup requires an http://localhost:PORT or http://127.0.0.1:PORT PUBLIC_ORIGIN. Use the reviewed deployment route for HTTPS hosting.")
    try:
        port = parsed.port or 80
    except ValueError:
        raise ValueError("The local port is invalid.") from None
    if not 1024 <= port <= 65535:
        raise ValueError("Use a local port between 1024 and 65535, such as 8000.")
    return "127.0.0.1", port

def open_after_start(origin, expected_version, *, attempts=80, interval=0.25):
    """Open the browser when this backend is ready, not a hard-coded old release.

    expected_version comes from the same backend module as /api/health.
    A failed browser hand-off never stops the server; print the manual address.
    """
    import json
    import time
    import urllib.request
    import webbrowser

    # This is still a local-only launcher. Do not probe arbitrary remote hosts.
    local_address(origin)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for attempt in range(attempts):
        healthy = False
        try:
            with opener.open(origin + "/api/health", timeout=1) as response:
                health = json.load(response)
            healthy = (isinstance(health, dict) and health.get("ok") is True
                       and health.get("version") == expected_version)
        except (OSError, ValueError, TypeError):
            pass
        if healthy:
            try:
                opened = bool(webbrowser.open(origin))
            except (webbrowser.Error, OSError):
                opened = False
            if not opened:
                print("The backend is ready. Open this address manually: " + origin,
                      flush=True)
            return opened
        # Back off on non-ready responses too, not only connection errors.
        if attempt + 1 < attempts:
            time.sleep(interval)
    print("Could not confirm browser readiness. Check the terminal for startup "
          "errors, then open: " + origin, flush=True)
    return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-browser", action="store_true", help="Do not open the default browser")
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        raise SystemExit("Python 3.11 or newer is required.")
    load_env()
    os.environ.setdefault("DATA_DIR", str(ROOT / "data"))
    try:
        import uvicorn
        from app.config import Settings
        from app.pilot import VERSION as backend_version
        settings = Settings.load()
        host, port = local_address(settings.public_origin)
    except ImportError:
        raise SystemExit("Run START-CIRCLELOGIC or install backend/requirements.txt first.") from None
    except (ValueError, RuntimeError) as error:
        raise SystemExit(str(error)) from None
    if settings.environment == "production":
        raise SystemExit("This launcher is local development only, not a production server.")
    # Check before bootstrapping: do not accidentally open another service's page.
    import socket
    try:
        with socket.socket() as probe:
            if os.name != "nt":
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind((host, port))
    except OSError:
        raise SystemExit("That local port is already in use. Close the existing server window, or change PUBLIC_ORIGIN in .env and the registered Microsoft callback.") from None
    from app.provision import bootstrap_testing_account
    if os.getenv("BOOTSTRAP_TESTING_ACCOUNT", "true").lower() == "true":
        bootstrap_testing_account(settings)
    print("\nCircleLogic OS " + backend_version + " - STARTING BACKEND, not the HTML preview", flush=True)
    print("Open: " + settings.public_origin, flush=True)
    print("This server listens on this computer only. Keep this window open.", flush=True)
    print("The testing123 login is for fabricated data only. CREATE-PRIVATE-WORKSPACE creates your own login.", flush=True)
    print("Use only an approved test mailbox. Press Ctrl+C to stop.\n", flush=True)
    if not args.no_browser:
        import threading
        threading.Thread(target=open_after_start,args=(settings.public_origin, backend_version),daemon=True).start()
    uvicorn.run("app.main:create_app", factory=True, host=host, port=port,
                access_log=False, proxy_headers=False)
