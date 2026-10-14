# v04 change log

## Requested changes implemented

- Replaced the broad CRM-style navigation with Dashboard and API Connections only.
- Rebuilt the desktop-first light interface, source cards, five KPI slots and three insight panels, with responsive mobile layouts.
- Preserved the original Circle Logic logo artwork; the active colour variant is navy. Provider marks are typographic identifiers/generic calendar icons, not claimed official logo assets.
- Made username/password the first screen. Added unique, case-insensitive usernames while preserving existing email logins.
- Added an idempotent local testing workspace using the user-requested credentials. Real TOTP enrolment and subsequent MFA are mandatory. The known account is blocked in production.
- Added operator-driven separate customer workspace provisioning. No user-controlled tenant switch is accepted.
- Removed all sample-data fallbacks from backend services. The standalone preview alone has an explicitly fictional populated example.
- Added the five-source connection status API and null/zero/stale distinctions.
- Added masked credential fields, 16 KB JSON form-fill, read-only management, recent-MFA step-up, disconnect cleanup and status details.
- Restricted Microsoft to delegated calendar read access; removed new mailbox fetching.
- Added verified public access routes for all five systems without fabricating authenticated vendor screens.
- Mapped documented REA report-period views, email enquiries and saves; never inferred buyer scores. Duplicate ambiguous totals and mismatched report agencies are rejected.

## Not implemented or not verified

Agentbox, Australian RP Data and Proping adapters remain gated. A buyer-intent feed is not implemented. Real vendor account testing, deployed OAuth round trips, native browser HTTPS/cookie testing, Docker builds, independent security review, backup restoration, customer acceptance and operational support arrangements remain outstanding.

## Compatibility

The original frontend is replaced, not maintained in parallel. Legacy backend team/task and other provider routes remain for data compatibility and regression testing. Historical UI test scripts and release documentation have been moved to explicitly labelled archives. The active frontend container does not include the preview or fictional fixtures.
