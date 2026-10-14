# Release gates - owner sign-off required

## Gate 1: qualify and discover

Confirm the paying agency/sponsor, team roles, source systems and subscriptions, number of records, desired business outcomes, and approved hosting/data handling. Select **one** authoritative sales CRM. Obtain approved provider applications, access, scopes and partner contracts. Do not use real client data with personal/unapproved AI tools.

## Gate 2: map and prioritise

For each module, document the source fields, record population, ownership, exclusions, timestamps/time zones, currency, update cadence and metric definitions. Prioritise one verified CRM plus one supporting service rather than pretending every catalogue entry is live. Decide whether the first client needs property management; this build cannot supply a live rent roll until that adapter is completed.

## Gate 3: design and complete

Approve role/record/field access, tenant model, per-user Microsoft privacy, recovery and offboarding, retention, consent revocation, secret management and backup/restore. Complete any required gated connector, settlement/commission mapping or other unsupported workflow before it enters the contracted scope. Keep outbound actions disabled unless deliberately designed and approved.

## Gate 4: test

Run the delivered suite. Add source-derived fixtures and approved live sandbox tests for each selected provider. Reconcile source IDs, complete pagination totals, zero rows, nulls, currencies and time windows. Verify unauthorised roles/tenants, OTP replay, lost access, expired/revoked tokens, wrong accounts, quota exhaustion, partial failures, concurrent refresh, source switching and disconnect during an active sync. Conduct browser-network/TLS testing, vulnerability/dependency scans and an independent security review.

## Gate 5: deploy and adopt

Use approved hosting with valid HTTPS, persistent encrypted storage, monitoring, backup and tested restore. Restrict signup/provisioning. Complete provider production approvals and register exact callbacks. Invite users with least privilege and individual MFA. Disable sample data for client operations once their live scope is accepted; unsupported modules should then show unavailable, not invented business data. Train users to recognise snapshot age and stale/error labels.

## Gate 6: support and expand

Name an operator for credential expiry, quota events, sync failures, access changes and incident response. Define support hours and recovery expectations. Measure dashboard accuracy, time saved and adoption. Extend only after the foundation is stable, with new connector contracts, tests, human-approval boundaries and documentation.

## Explicit not-done items in this delivery

No public hosting/deployment, provider credential collection from the user, live provider certification, PropertyMe/Reapit Sales/Property Tree adapter, AI agent execution, outbound provider writes, automated invitation emails, live commissions/settlements, trust reconciliation, independent security assessment, dependency vulnerability scan, backup scheduler or production restore drill was completed. Docker files are templates, not executed infrastructure.
