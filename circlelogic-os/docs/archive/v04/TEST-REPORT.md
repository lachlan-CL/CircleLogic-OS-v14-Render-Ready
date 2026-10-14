# CircleLogic OS v04 - test report

**Run date: 25 September 2026. Version: 0.4.0.**

## Results

| Test layer | Result | Method |
| --- | --- | --- |
| Backend regressions and v04 acceptance | **111 passed** | pytest against isolated SQLite databases, FastAPI TestClient and synthetic provider fixtures. |
| Interface and UI-to-backend checks | **45 passed** | Embedded Chromium rendering the actual frontend; standalone preview plus a separate real backend through an explicit TestClient bridge. |
| Real loopback HTTP smoke checks | **19 passed** | A separate Uvicorn process, real localhost HTTP requests and cookie handling via httpx. |
| Browser JavaScript errors in the UI run | **0** | Page-error capture during desktop/mobile workflows. |

No real provider credentials, customer identities or customer data were used. These are test cases/checks, not independent certifications. Counts must not be represented as a penetration test or production acceptance.

## Backend coverage

The 76 earlier regression cases were updated for v04's deliberate no-samples/calendar-only scope. Thirty-five new cases cover testing account bootstrap, unique usernames, mandatory MFA, production rejection of the known account, operator tenant provisioning, migration preservation, exactly five connections, null versus successful zero, credential redaction, gated adapters, failed/partial import preservation, cross-tenant query attempts, roles, per-user calendar privacy, event filtering, stale/disconnect semantics, restricted calendar scopes, absence of fixtures from the live bundle, documented REA metric parsing and wrong-agency report rejection.

Existing cases include TOTP reference vectors/replay protection, session rotation, one-use recovery codes, CSRF/origin checks, encrypted credential context, role enforcement, audit redaction, provider pagination, OAuth state ownership/reuse/expiry, token refresh and sync concurrency guards.

## Interface coverage

The UI run exercised login-first rendering, invalid preview login, clearly labelled simulated MFA, only two navigation choices, five empty KPI cards, fictional example toggle and record disclaimers, date filtering, five source rows, disabled preview secret intake, all five help guides, mobile overflow/dialog fit, actual backend first-login TOTP and recovery codes, gated connection notices, invalid and valid JSON form fill, save-not-live status, no returned secrets, disconnect cleanup, exact Microsoft callback display, logout, returning MFA and one-use recovery login. It also exercised a synthetic REA import through the real backend, rendered documented report counts without invented buyer scores, preserved a failed refresh as stale and deleted the imported records on disconnect.

Desktop screenshots were reviewed at 1536 pixels wide; mobile checks used 390 by 844. Screenshot files show this application, not generated or authenticated third-party vendor screens. QR secrets and recovery codes are not included in distributed screenshots.

## Transport limitation

Direct browser navigation is blocked by the authoring environment. Browser tests therefore render the actual HTML with `page.set_content` and route fetch calls through a TestClient bridge. They do **not** prove native browser networking, cookie transport, CSP enforcement at a deployed origin, redirects, TLS or a provider consent journey. A separate real loopback HTTP harness covers server startup, static assets, session cookies, MFA gates, empty-state responses, CSRF/origin boundaries and logout using httpx rather than a browser.

## Not tested / not delivered

Real REA or Microsoft account imports; externally deployed OAuth round trips; gated Agentbox/RP Data/Proping connectors; buyer-intent scoring; Google Calendar; provider write-back; email delivery/ingestion; Docker builds; public hosting; independent security review; production load, disaster recovery, full accessibility audit or customer acceptance. The legacy Team frontend is removed and its old UI harness is historical, not part of the v04 result.

## Reproduce

```bash
python -m pytest backend/tests -q
python scripts/build_preview.py
python -m pip install playwright
python scripts/browser_v04.py --output docs/ui-test-output
python scripts/http_v04.py --output docs/http-test-output.json
```

The UI harness expects Chromium at `/usr/bin/chromium`; adjust its executable setting for another approved environment. Playwright's browser download was not required here. Current evidence is in `pytest-result.txt`, `browser-report.json` and `http-report.json`.
