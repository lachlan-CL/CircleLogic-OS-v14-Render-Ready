# Test report - CircleLogic OS v03

Date: 25 September 2026.

## Results

**76 backend tests passed.** All 59 v02 tests continue to pass, alongside 17 added tests for named invitations, reissue/revocation, permissions, task assignment, identity preservation and migration.

Three embedded Chromium scripts also passed with **no uncaught JavaScript errors**. Only synthetic test identities, temporary databases and synthetic credentials/authenticators were used. No real people were invited and no messages were sent.

## Backend

Run `python -m pytest backend/tests -q`.

The original suite covers TOTP vectors/replay, password/secret handling, pre-MFA denial, Origin/CSRF, sessions/recovery, permission and tenant boundaries, redaction, exports, source selection, sync/OAuth state and seven mocked read-only adapters. See the retained V02-TEST-REPORT.md for that original coverage; it is historical evidence, not a separate new production validation.

New tests cover:

- Named invitation visibility without token disclosure; duplicate-email rejection; rotation and single-use semantics; revocation; expiry and reissue.
- Tenant isolation and privilege checks for invitation edits/revocation, including administrators trying to downgrade an owner's invitation.
- Recipient-owned password/authenticator onboarding, no access before MFA, no task assignment until eligible, and open-task counts.
- Display-name updates without changing login emails, password hashes, authenticator secrets or tenant IDs; local-task label updates; no self-demotion or self-deactivation.
- Assignment/reassignment controls, Viewer exclusion, recent-MFA and CSRF requirements, trimmed-name validation.
- Additive, idempotent migration from the old invitation schema while preserving existing token hashes and tenant data.

## Embedded preview regression

`python scripts/browser_smoke.py --chromium /path/to/chromium`

Passed: all 18 routes, desktop metrics, search and record details, preview secret-collection block, draft task creation/completion, global search, 390px mobile layout and navigation. This uses `page.set_content` with the standalone HTML, not a deployed browser page.

## Embedded UI / API regression

`python scripts/browser_api_smoke.py --chromium /path/to/chromium`

Passed: signup, own authenticator enrolment, recovery codes, persisted tasks, credential JSON processing, encrypted/redacted configuration, no premature live data, named invitation creation, settings, logout and recovery-code login. Fetch is bridged to FastAPI TestClient; cookies/transport are managed in the test client.

## Team UI / onboarding checks

`python scripts/browser_team_v03.py --chromium /path/to/chromium`

Passed: replacing sample owner/agent, stable IDs, sidebar name updates, adding a profile, duplicate rejection, name/assignment propagation, reassignment, mobile Add person usability, reset, named invitation creation/reissue, expired old-link screen, prefilled join form, incomplete-MFA exclusion, completed onboarding, role-limited navigation, task assignment, and session revocation on deactivation.

Preview serialization and fresh-document restoration were tested with an **explicit in-memory Storage adapter**. This checks the application persistence logic, not the browser's actual localStorage availability or file-origin behaviour. UI-to-backend operations use independent FastAPI TestClients.

Screenshots were inspected for desktop/mobile team layout, logo rendering and sign-in branding. A mobile screenshot captured mid-transition was retaken after allowing the navigation transition to settle.

## Blocked / not validated

An attempted real local-HTTP browser test returned `net::ERR_BLOCKED_BY_ADMINISTRATOR` before the first page loaded. No administrator policy was changed. `scripts/browser_team_http.py` is supplied as an optional test for an approved environment, but **it did not pass or validate a deployed workflow here**.

Actual browser network/cookie/TLS enforcement; true localStorage persistence including file URLs; email delivery; public hosting/DNS; real provider accounts and OAuth redirects; Docker builds; dependency/security scanning; penetration/load testing; backup restoration; other browsers/operating systems; accessibility conformance; and the unimplemented adapters remain unverified.

Passing tests establishes the exercised application behaviour only. It is not a security audit, production sign-off, email delivery confirmation or live-provider certification.
