# CircleLogic OS v07 - test report

**Version:** 0.7.0  
**Run date:** 2 October 2026  
**Scope:** Google Calendar read-only connector added to the existing local development pilot.

## Results

| Layer | Result | Method |
| --- | --- | --- |
| Backend regression | **206 passed** | pytest with isolated databases, FastAPI TestClient and synthetic provider responses. |
| v07 browser workflow | **36 passed, 0 page errors** | Actual frontend + backend through a TestClient fetch bridge in Chromium; synthetic Google OAuth/Calendar responses. |
| Real loopback HTTP | **21 passed** | Uvicorn started by `run.py`, real local HTTP/cookies via httpx; no external provider requests. |
| JavaScript syntax | **Passed** | `node --check` on `app.js` and `guides.js`. |

## Google coverage

Tests cover client-ID setup, one-field client-secret paste, secret non-disclosure, OAuth URL host/scope/offline parameters, state ownership, callback token exchange, primary-calendar request shape, pagination, all-day events, updates, successful empty imports, 401 refresh, safe error mapping, private per-user data, dashboard source labels and disconnect cleanup.

The UI checks verify Google appears as the sixth source, Microsoft remains available, the Google key window has exactly one masked credential field and no JSON upload, the setup guide contains the client ID and exact redirect URI, imported synthetic events reach the dashboard, and the six-source layout does not overflow on mobile.

## Not yet proven

No real Google account, OAuth client, provider consent screen or customer calendar was used. The embedded-browser tests do not prove native browser redirects, HTTPS or Google's real consent journey. The next acceptance test is to run the app locally, create a Google OAuth Web application, authorise a dedicated test account, then import/update/delete one fabricated event.

This remains a development pilot, not a production security certification.
