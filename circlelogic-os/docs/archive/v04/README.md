# CircleLogic OS v04 - Real Estate Brain

A deliberately small read-only dashboard, revised from the earlier CircleLogic OS v03 source. Two pages, username login, mandatory TOTP, server-side workspace isolation, an empty-first dashboard and five source connection rows.

**Status: development pilot, not a live-certified five-provider product.** Read [START-HERE.md](START-HERE.md) first.

## Included

- `frontend/`: two-page HTML/CSS/JavaScript interface, original Circle Logic logo artwork in a navy colour variant, guides, credential dialogs and empty states. No synthetic dataset is shipped in the live frontend.
- `backend/`: FastAPI, SQLite, password hashing, MFA, encrypted credentials, read-only adapters and tenant-scoped snapshots.
- `preview/`: isolated, explicitly fictional design data for the standalone HTML preview. Never served by the application or copied into the frontend container.
- `scripts/`: local operator provisioning, preview build and repeatable test harnesses.
- `deploy/`: separate API/frontend service templates; Docker/HTTPS deployment has not been executed or certified here.
- `docs/`: current architecture, access routes, security limits, migration guidance, release checklist and actual test results. Historical v03 documents are labelled and archived.

## Quick start

```bash
python -m pip install -r backend/requirements.txt
python run.py
```

Then open `http://localhost:8000`. Local-only credentials are `testing123` / `testing12345`. Complete **real authenticator enrolment** and retain recovery codes. The standalone design preview uses a clearly labelled simulated MFA code instead; see the start guide.

## Scope and honest connection status

The dashboard has five source tiles, five KPI slots and panels for REA listing activity, market alerts and the user's calendar. Values are null until their source has a completed snapshot. Unavailable is not zero. It does not invent high-intent buyers from listing page views or automatically replace missing records with demo data.

The requested five sources have different readiness: REA listing-performance and Microsoft calendar adapters are implemented and mock-tested; Agentbox, Australian RP Data and Proping adapters are gated. Approval, accurate contracts, licensing and connector work remain for the gated sources. A future approved buyer-score feed also needs its own mapping and acceptance tests.

The many-page v03 UI is removed. Existing team/task/role and other provider API routes remain for migration compatibility but have no pages in the v04 navigation. This is not a claim that those backend capabilities were removed from the attack surface. Review them before deployment.

## Repeat tests

```bash
python -m pytest backend/tests -q
python scripts/build_preview.py
# Optional UI test dependencies; Chromium must also be installed by the operator.
python -m pip install playwright
python scripts/browser_v04.py --output docs/ui-test-output
python scripts/http_v04.py --output docs/http-test-output.json
```

The Chromium harness uses a FastAPI TestClient bridge because direct browser navigation is blocked in the authoring environment. It verifies actual UI behavior and server authorization, but not browser-native cookie transport, HTTPS or external OAuth redirects. The separate HTTP harness uses real loopback Uvicorn/httpx networking. See the test report for boundaries and exact counts.

## Operator provisioning

```bash
python scripts/provision_workspace.py --agency "Customer agency" --username customer.owner --email owner@example.invalid --name "Customer owner"
```

The command prompts twice for a password rather than accepting it on the command line. It creates a separate workspace and owner with MFA still required. Public signup is disabled by default. Use a fresh approved production data store; do not migrate the known testing account into it.

## Core API routes

| Route | Purpose |
| --- | --- |
| `POST /api/auth/login` | Username/email plus password; limited session only. |
| `GET /api/auth/enrolment` | First-login TOTP QR/secret; available only to the limited enrolment session. |
| `POST /api/auth/mfa` | Verify TOTP or an unused recovery code and rotate to a full session. |
| `GET /api/brain/dashboard` | Tenant- and permission-scoped real snapshots and null empty-state metrics. |
| `GET /api/brain/connections` | Five source statuses, permitted field definitions, never saved secret values. |
| `PUT /api/integrations/{provider}` | Validate and encrypt permitted credentials; requires recent MFA. |
| `POST /api/integrations/{provider}/authorise` | Start an implemented OAuth flow with session-bound state. |
| `POST /api/integrations/{provider}/sync` | Read and atomically replace a complete validated snapshot. |
| `DELETE /api/integrations/{provider}` | Delete local credentials, imported records and snapshots; separate provider revocation required. |

No AI model is called, no provider records are written, and no automatic outbound actions are enabled. Changes in this archive are not automatically applied to a previously hosted application.
