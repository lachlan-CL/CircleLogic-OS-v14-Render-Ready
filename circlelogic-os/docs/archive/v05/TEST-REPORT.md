# CircleLogic OS v05 - test report

**Version: 0.5.0. Run date: 25 September 2026. Development backend pilot, not a production certification.**

## Results

| Layer | Result | What actually ran |
| --- | --- | --- |
| Backend regression and v05 acceptance | **154 passed** | pytest, isolated SQLite databases, FastAPI TestClient and synthetic provider responses through the actual adapters. |
| Existing interface regression | **45 passed** | Embedded Chromium, the historical v04 preview and updated real frontend/backend through a TestClient fetch bridge. |
| New running-app calendar workflow | **30 passed** | Embedded Chromium, actual frontend, credential-file input, real backend MFA, actual Microsoft adapter with synthetic token/calendar responses. |
| Browser JavaScript errors | **0** | Page-error capture in both embedded runs. |
| Real local HTTP acceptance | **31 passed** | A separate Uvicorn process started with run.py, loopback HTTP requests and real cookie handling via httpx. No provider requests. |
| Private-account wizard and configuration checker | **Passed** | Actual Python commands on Linux/Python 3.13.5, using synthetic piped input for the account wizard. |

The interface total is **75 checks across two harnesses**, not 75 independent end-to-end provider tests. Repeat development runs and the older 19-check HTTP harness are not added to the totals. No real provider credentials, Microsoft/REA accounts, customer records or customer identities were used.

## Coverage added in v05

The backend cases cover authenticated readiness; database and in-memory vault checks; safe connection diagnostics; credential saving distinct from authorisation and import; private calendar and cross-workspace isolation; MFA gates; Host/origin restrictions; refusal to accept secrets for unfinished connectors; validation responses without reflected credential values; supported Microsoft tenant identifiers; OAuth PKCE and account selection; fixed error-code explanations; and disconnect cleanup.

Calendar cases exercise the real adapter against simulated Microsoft endpoints: bounded 401 token refresh/retry and rotated-token persistence; no 403 refresh loop; preserved stale snapshots on repeated failure; UTC response preference; 30-day/default-calendar request shape; pagination; returned-record mapping; cancellation handling; all-day and ongoing events; update, deletion, empty imports and repeated synchronisation. No mailbox, invitation or calendar write request is enabled.

The new UI harness signs into a private synthetic workspace, completes real backend MFA, opens both pages, verifies enabled credential and file inputs, uploads JSON without saving automatically, saves credentials without marking the source connected, shows missing authorisation, inspects safe diagnostic output, completes a synthetic OAuth callback, imports through the actual adapter, displays the returned event, updates it, checks stale-data behaviour, disconnects and verifies cleanup. Desktop and mobile layouts are checked.

The real-HTTP harness starts the new local launcher on an available loopback port, retrieves the frontend/assets, exercises password and TOTP login, checks HttpOnly/SameSite cookies, credential intake, exact callback generation, redaction, invalid OAuth state, origin/CSRF/Host checks and logout. It makes **zero external provider requests**.

## Evidence

Current machine-readable reports and screenshots are under `docs/evidence-v05/`:

- `pytest-result.txt` - final 154-test backend run.
- `browser-regression.json` and `browser-pilot.json` - 45 and 30 embedded checks.
- `http-pilot.json` - 31 real loopback HTTP checks.
- `operator-cli.json` - private-account wizard and direct configuration check.
- `installed-versions.json` - interpreter and direct package versions used.
- `screenshots/` - actual application screens from the synthetic workflow.

The illustrated guide uses actual CircleLogic screenshots. Any shown account, calendar record or successful provider response is synthetic and labelled as such. No provider-console screenshots, real QR enrolment secrets, recovery codes or customer credentials are distributed.

## Transport and installation limits

A native browser navigation attempt to the local server was blocked by the authoring environment (`ERR_BLOCKED_BY_ADMINISTRATOR`). This restriction was not bypassed. Browser checks instead render actual HTML/CSS/JavaScript with Playwright `page.set_content` and a TestClient fetch bridge. They do **not** establish native browser cookie transport, deployed Content-Security-Policy behaviour, TLS, browser redirects or a real external Microsoft consent journey. Separate httpx checks establish actual loopback server/cookie behaviour, not those browser guarantees.

The first-run dependency bootstrap was attempted, but the environment could not resolve/reach its Python package host. Consequently a clean internet-based installation was **not** validated here. Tests used already installed packages matching the pinned direct requirements. The Windows `.cmd` and macOS `.command` wrappers were inspected but **not executed on those operating systems**. Their Python account and configuration commands were exercised on Linux. Do not disable company security controls to work around an installation failure; use an approved package source.

## Not tested or delivered

No live Microsoft or REA imports; no genuine provider-consent round trip; no Agentbox, Australian RP Data or Proping connector implementation; no Google Calendar; no buyer-intent scoring; no provider write-back, inbox ingestion or email delivery. No public or private external deployment was performed. Docker builds, production HTTPS, certificate/federated Microsoft client credentials, independent security review, penetration testing, production load, disaster recovery and customer acceptance remain outstanding. The local app is a development pilot and must not be presented as production approved.

Some legacy backend routes and separate-service deployment templates are retained from previous releases; their continued inclusion is not a v05 production approval. The first customer pilot needs a reviewed deployment, operator access controls, fresh private accounts and database, protected vault key/storage/backups, live-provider tests and release-checklist sign-off.

## Reproduce on approved infrastructure

From the extracted `circlelogic-os` directory, with dependencies installed:

```sh
python -m pytest backend/tests -q
python scripts/http_v05.py --output docs/http-test-output.json
```

For embedded interface checks, additionally install Playwright and an approved Chromium executable:

```sh
python scripts/browser_v05.py --chromium /path/to/chromium --output docs/ui-test-output-v05
python scripts/browser_v04.py --output docs/ui-test-output-v04
```

The regression script expects Chromium at `/usr/bin/chromium`; adjust that script's executable configuration for another approved environment. The pilot script accepts `--chromium`. These scripts use temporary synthetic workspaces, not live credentials. The historical preview stays in `docs/archive/v04/` only for reference and regression coverage; it is not the application's start route.

On Windows, `RUN-AUTOMATED-TESTS.cmd` installs the pinned requirements as needed and runs the backend cases. `CHECK-SETUP.cmd` checks the local configuration without provider traffic. A passing local check does not mean a provider has authorised the account.

## Required live acceptance

On an approved installation with a private user and test mailbox: complete native browser login/MFA; save a dedicated Microsoft app registration; finish provider consent and return; import a fabricated default-calendar appointment; compare title/time/location; edit and delete it in Outlook and resynchronise; check a recurring/all-day event and empty import; repeat sync to exclude duplicates; verify token renewal, denied access, stale-data handling and user/workspace separation. Record actual evidence in `docs/RELEASE-CHECKLIST.md`. These live cases remain **Not run**.
