# CircleLogic OS v05 - Backend Pilot

An updated, runnable version of the existing application. The separate frontend and backend source directories are retained. The local starter serves both at one loopback address so authentication, cookies and the UI share an origin.

**Start with [START-HERE.md](START-HERE.md), not the archived HTML preview.** No public deployment has been performed. No real vendor credentials, customer records, enrolled accounts or databases are included.

## What is new

Windows launchers and equivalent Python/macOS commands; private local workspace creation; authenticated backend readiness checks; safe per-connection diagnostics; explicit Microsoft Test and sync; readable, redacted Microsoft errors; one bounded token-refresh retry; all-day/in-progress calendar handling; Host checks and redacted validation errors.

## Run it

On an approved computer with Python 3.11+ and package-download access:

```sh
python launcher.py start
```

Windows: extract the ZIP and double-click `START-CIRCLELOGIC.cmd`. Keep the server window open. The default address is `http://localhost:8000`. First setup installs pinned Python dependencies into `.venv`; it requires internet or an approved package mirror. Node.js and Docker are not needed for this local route.

Run `CREATE-PRIVATE-WORKSPACE.cmd` (or `python launcher.py create`) before connecting an approved test mailbox. It prompts for a private password and creates a distinct workspace. Sign in and enrol an authenticator. The published `testing123` login remains solely for fabricated-data testing.

## Live-integration scope

Microsoft 365 default calendar and REA listing-performance have implemented adapters. Both still require real provider-account acceptance. Agentbox, Australian RP Data and Proping remain gated pending access/contract confirmation and connector implementation. Google Calendar, mailbox ingestion, buyer-intent scores and write-back are not implemented in this pilot.

The real dashboard is empty until a successful import. Calendar data fills the calendar panel, not the CRM or buyer-score cards. Uploading a JSON file fills a credential form; saving, authorising and syncing are separate operations. The app never inserts the archived preview's examples into your workspace.

## Files

`frontend/` contains the two-page interface. `backend/` contains the API, logical tenant store, authentication, adapters and tests. `scripts/` includes operator tools and test harnesses. `templates/` contains blank credential examples. `deploy/` contains inherited, unexecuted separate-service deployment templates. `docs/` explains current setup and evidence; `docs/archive/` is historical, not the recommended startup route.

## Tests

```sh
python -m pytest backend/tests -q
python scripts/http_v05.py
# Optional embedded browser checks: install Playwright and an approved Chromium first.
python scripts/browser_v05.py --chromium /path/to/chromium
```

See [docs/TEST-REPORT.md](docs/TEST-REPORT.md) for actual results and limits. Browser-native Microsoft consent, HTTPS hosting, Windows execution and fresh package installation were not verified here. Real localhost HTTP and embedded browser tests were run with installed dependencies. Provider responses used in automated tests are synthetic.

## Production boundary

Local account separation is logical tenancy in SQLite, not a separate server per customer. The master vault key and records need protected disks/backups and reviewed operator access. The local HTTP route is only for approved test accounts. Use reviewed HTTPS hosting, private customer identities and a fresh production database before handling customer data. Microsoft certificate/federated credential support, independent security review and deployment acceptance are still required; the current adapter uses a client secret for testing.
