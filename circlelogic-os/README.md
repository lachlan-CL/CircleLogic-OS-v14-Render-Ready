# CircleLogic OS / Real Estate Brain / v07

Runnable Python/FastAPI backend with a plain HTML/CSS/JavaScript frontend. The workspace has two pages: **Dashboard** and **API Connections**.

v07 adds a **read-only Google Calendar OAuth connector** alongside Microsoft Calendar. The compact connection window still contains only the software name, Setup guide, one masked secret field and Save key. There is no JSON credential upload.

Start with **START-HERE.md**. No live Google account, customer data or provider secret is bundled with this package.

## Current tests

```sh
python -m pytest backend/tests -q
python scripts/http_v07.py --output docs/evidence-v07/http-report.json
python scripts/browser_v07.py --chromium /path/to/chromium --output docs/evidence-v07/ui
```

The Google browser harness uses the real frontend/backend with synthetic Google OAuth and Calendar responses. It does not prove a real Google consent round-trip; that is the next acceptance test on an approved local installation.

## Google Calendar design

- OAuth 2.0 Web application client ID is stored once in the Setup guide.
- The connection window accepts the matching client secret in a single masked field.
- The user is redirected to Google to consent; the backend never treats the client secret as calendar access by itself.
- Scope: `https://www.googleapis.com/auth/calendar.events.readonly`.
- Import: signed-in user's `primary` calendar, next 30 days, read-only.
- Calendar data and credentials are private to the connecting CircleLogic login.
- Google and Microsoft calendar snapshots can coexist in the dashboard.

Agentbox, Australian RP Data and Proping remain gated pending supported integration contracts. REA listing-performance remains implemented as before.

For deployment limitations see `docs/DEPLOYMENT.md` and `docs/RELEASE-CHECKLIST.md`.
