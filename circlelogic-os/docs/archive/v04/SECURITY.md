# Security posture and limits - v04

This is a development pilot with implemented controls, not an independently audited or production-certified system.

## Implemented and locally tested

- Argon2id password hashing; username/email sign-in; generic invalid-login response; persistent rate limiting.
- Server-enforced first-login TOTP enrolment, MFA challenges, replay rejection, one-use hashed recovery codes and session rotation.
- HttpOnly, SameSite=Lax cookies scoped to `/api`; Secure in HTTPS configuration. Full API access is denied before MFA.
- Same-origin JSON mutation checks, CSRF verification, payload size limits, security headers and no-store API responses.
- Backend roles, tenant filters and additional per-user scope for calendar data. Shared credential changes restricted to owners/admins; supported private calendars are self-managed by permitted users.
- Ten-minute recent-MFA checks before sensitive account or connection changes.
- Context-bound encrypted stored provider credentials and TOTP secrets. Saved credential values are not returned to the browser or placed in audit messages.
- Server-side provider calls to fixed supported hosts; pagination validation, atomic imports, revision/lease guards and stale-data preservation.
- Secret-free standalone preview with blocked network access and disabled real credential fields. Demo values never populate real workspaces.
- Production refuses to start with the known testing username. Public signup disabled by default.

## Important limitations

Do not use `testing123 / testing12345` for clients. The public password exists solely for local testing. TOTP does not make a publicly known password an acceptable production credential.

SQLite record payloads are stored as application data, not individually encrypted by the application. Protect disks, backups, hosts and the master vault key. The current design uses a single master key and logical tenancy; operators with database/key access have privileged access. Establish a key lifecycle, audited operator access and customer isolation requirements before deployment.

Credential forms can accept provider secrets only for implemented adapters. The local HTTP warning is intentional: approved customer use requires HTTPS infrastructure. Treat file uploads as sensitive even though they fill only an in-memory form; securely remove temporary credential files from the operator's device after use.

REA partner credentials may authorize more than one agency. Provision and verify the intended agency binding and entitlement for each customer; do not hand clients shared integrator-wide secrets. The adapter checks returned report agency IDs where supplied but is not a substitute for least-privilege provider authorization.

Microsoft old consent grants may still permit mail if the deployment is upgraded from v03. Revoke those grants and reauthorise a calendar-only app; no automatic provider revocation is claimed. No Google Calendar, mailbox parser or Proping email reader is included.

Disconnect deletes local credentials, imports and snapshots. It does not revoke the provider-side app grant. Revoke provider consent separately.

Legacy API routes remain even though the navigation is reduced. Review their exposure and operational need. Automated tests do not replace penetration testing, dependency/security review, hosting configuration, abuse controls, breach response, data retention/deletion policy, restore drills or user acceptance.

## Never include in a release archive

`.env`, `.env.production`, `data/`, SQLite databases/WAL files, `.vault-key`, authenticator secrets/QRs, recovery codes, real provider credentials, customer screenshots or unredacted logs. The distributed archive has no pre-enrolled testing account, database or vault key.
