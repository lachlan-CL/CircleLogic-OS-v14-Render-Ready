# Test report - 25 September 2026

## Result

**59 backend tests passed**, plus the preview and UI/API smoke checks described below. No real provider credentials or client data were used. Test databases and authenticators were synthetic and temporary.

The tests establish behaviour against the implemented contract and synthetic responses. They do not establish that an agency's live provider account exposes the same permissions, fields, licences, quotas or pagination behaviour.

## Backend suite

Command: `python -m pytest backend/tests -q`

Coverage includes six official SHA-1 RFC 6238 test-vector values, OTP replay/time windows, context-bound encryption, pre-MFA access denial, Origin/CSRF controls, password/session storage, session rotation, one-use recovery codes, recent-MFA checks, cross-tenant detail/search/export/update/assignment denial, four restricted roles, member revocation, email-bound invitation use, rate limits, credential redaction, refusal to collect gated-connector secrets, formula-safe exports and switching off samples.

Sync/OAuth tests cover credential-save versus live-state distinction, successful empty imports, incomplete/duplicate/missing-ID rejection, preservation of stale data on failure, snapshot age, disconnection/deletion, disconnect during sync, concurrent sync rejection, authoritative source isolation, PKCE/state binding, state replay and reconfiguration, denial handling and user-private Microsoft records.

Adapter tests cover mock responses for all seven implemented providers, expected authentication headers, selected field mappings, pagination, account verification, DocuSign discovered base URI and relative next-page URI, Microsoft metadata selection, refresh persistence before a later data failure, host/path/HTTPS pagination guards, upstream error redaction and rate-limit retries.

## Browser preview checks

Command: `python scripts/browser_smoke.py --chromium /path/to/chromium`

Chromium rendered the standalone HTML via `set_content`; local URL/file navigation was blocked by the authoring browser environment. The check therefore embedded the owned HTML rather than navigating to a deployed website. It exercised all 18 routes, desktop metrics, table search, record details, Escape dismissal, blocked credential collection in preview, task creation/completion, global search, and mobile navigation at 390 pixels without page-level horizontal overflow. No uncaught JavaScript errors were observed.

## UI-to-API integration checks

Command: `python scripts/browser_api_smoke.py --chromium /path/to/chromium`

Chromium ran the actual frontend against FastAPI through an in-process test bridge. The bridge used the real routes, persistence, CSRF headers and server session logic, while managing transport cookies in the Python test client. The following flows passed: workspace creation, TOTP enrolment, recovery-code presentation, dashboard access, persisted task creation, credential JSON loading and encrypted save, redacted integration status, no premature live transition, team invitation, sample-data settings, logout, password login and recovery-code MFA.

**This bridge did not test the browser's real network/cookie enforcement, HTTPS or third-party redirects.** It is not represented as a deployed browser end-to-end test. A local HTTP health check and static route check also succeeded, but do not establish production networking.

## Not tested / release gates

Live provider contracts and real tokens; actual provider consent screens and refresh expiry; public hosting/DNS/TLS; real-browser Secure/SameSite cookie behaviour across OAuth redirects; Docker builds; dependency vulnerability scanning; penetration testing; load testing; provider aggregate quota behaviour; monitoring/alert delivery; backup scheduling/restoration; tenant deletion/retention; disaster recovery; accessibility conformance; and the three unimplemented connectors.

Screenshots are visual review evidence, not security evidence. The preview contains no real customers, properties, phone numbers or financial balances. The included test fixtures contain deliberately labelled synthetic credentials only.
