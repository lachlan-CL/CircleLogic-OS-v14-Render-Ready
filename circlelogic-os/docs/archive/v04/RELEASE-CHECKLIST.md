# Customer release checklist

This checklist remains open until the deployment owner records evidence.

- Confirm CircleLogic-approved hosting/workspace, legal/data-handling requirements, roles and data residency.
- Remove the known testing account by using a fresh production store; provision distinct customer accounts privately.
- Verify customer-to-tenant and provider-agency bindings, least-privilege credentials and the correct Microsoft account/tenant.
- Complete Agentbox, Australian RP Data and Proping approvals, contracts, adapters and acceptance tests before enabling their credential intake. Define and verify any buyer-intent score feed separately.
- Validate REA reports and Microsoft calendar using approved real/sandbox accounts, including pagination, no records, failures, token expiry, revoked access and scopes.
- Verify native browser HTTPS login, first TOTP enrolment, recovery, later MFA, CSRF, session expiry/revocation and OAuth callbacks. The authoring UI bridge does not cover these transports.
- Build/scan/pin deployment images and dependencies; review legacy API endpoints and remove unnecessary surfaces.
- Protect master keys, disks, logs and backups; document retention/deletion, customer consent, recovery and incident response.
- Test restore of a paired database/key backup and confirm private calendars remain private after restoration.
- Complete independent security review, accessibility/usability checks with target users and documented customer acceptance.
- Assign system ownership, monitoring, support and a rollback plan. Do not market mock-tested adapters as live-certified.
