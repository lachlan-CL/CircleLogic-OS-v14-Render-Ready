# Security implementation and remaining assurance work

This document describes code that exists and its limitations. It is not a certification, penetration test report, privacy assessment or legal-compliance opinion. Use only Circle Logic-approved company infrastructure for real company or client information.

## Implemented controls

Passwords use Argon2id; the original passwords are not persisted. Accounts enrol a SHA-1 RFC 6238 authenticator secret before receiving a business session. Secrets are encrypted; OTP counters are consumed atomically so a code cannot be reused. Eight high-entropy recovery codes are shown once and stored as hashes; each can be consumed only once. The standard SHA-1 RFC test vectors are covered in the automated suite.

Session tokens are opaque random values stored only as hashes server-side. Session cookies are HttpOnly, SameSite=Lax, scoped to `/api`, and Secure when the public origin uses HTTPS. Pre-MFA sessions expire after ten minutes; business sessions after eight hours. Sensitive settings need a successful MFA check within ten minutes. Logout, member deactivation and other-session revocation remove server-side sessions.

Unsafe requests require an exact allowed Origin and JSON content type. Authenticated mutations additionally require the server-generated CSRF token. App endpoints have no permissive CORS policy. The frontend escapes inserted record text; CSV exports protect leading formula characters. Security response headers restrict frames, scripts and referrers. No third-party frontend scripts, analytics or remote fonts are required.

Tenant and role checks run on the backend, including exports, search, detail views and mutations. Roles are owner, admin, agent, property manager, finance and viewer. Agent contacts are agency-wide, not assigned-agent-only. This is module-level RBAC, not configurable field-level permissions or a complete brokerage policy engine. Microsoft data has additional per-user isolation.

Provider credentials, OAuth tokens, PKCE verifiers and authenticator secrets use context-bound Fernet authenticated encryption. A ciphertext for one connection cannot be opened in another tenant/provider context. API status and audit responses do not contain stored credentials. OAuth state is random, single-use, time-limited and bound to session, user, tenant, provider and connection revision. PKCE is used in the Microsoft and DocuSign flows; the implemented Xero flow uses its confidential client secret.

The adapters accept no caller-controlled API base URL. Provider pagination is restricted to expected HTTPS hosts and resource paths, with bounded requests, retries and page counts. Sync is read-only and commits only after all pages and all declared modules validate. Changing/disconnecting a connection invalidates in-flight work. A failed sync retains last-good records with a stale/error state.

## Important limits

- SQLite tenancy is application enforced, not database row-level security. The database operator with the vault key can access data. This is not zero-knowledge or operator-proof isolation.
- **Business record payloads are not application-encrypted in SQLite.** Provider secrets and MFA material are encrypted separately, but imported personal/business data needs approved encrypted storage, backups and operating-system access controls.
- Local development may use HTTP and locally stored `data/.vault-key`. Those settings are not acceptable for public client use. Production settings require HTTPS and an explicit persistent key; the key must be separated from backups/source control and handled by approved secret management.
- API/login attempt limits exist, but there is no perimeter DDoS protection, distributed quota service or web application firewall. Behind the sample reverse proxy, request-IP-based limits may aggregate traffic at the proxy. Review trusted proxy handling and perimeter throttling before multi-client use.
- Audit rows are useful application records, not immutable evidence. There is no external append-only audit sink, SIEM alerting, formal retention policy or cryptographic audit-chain guarantee.
- No self-service forgotten-password, lost-all-MFA recovery, recovery-code regeneration, passkeys, SSO, SCIM, email ownership verification or tenant deletion workflow is implemented. Invitations are email-bound and single-use but delivered privately by the administrator, not via an email service. Identity verification and lost-access handling need an approved operating procedure; do not introduce a universal bypass.
- Disconnect erases imported rows and credentials from the active logical database view, but not prior backups, WAL history or upstream consent. Revoke the application at the provider as well; define retention and backup deletion procedures.
- The credentials form and JSON loader necessarily handle supplied values in memory. Do not use them on a shared/untrusted device. Clear any downloaded credential JSON according to the approved handling policy.
- No live provider account was tested, no public deployment or browser-network cookie/TLS test was performed, and no independent vulnerability/dependency/security audit was completed.

## Review priorities before a client release

Have a qualified reviewer test cross-tenant/role/record access, session fixation and revocation, CSRF, stored XSS, exported formula handling, invitation takeover, MFA loss/replay, OAuth account confusion, refresh-token races, SSRF, quota exhaustion and host/proxy configuration. Verify storage encryption, key lifecycle, backups and restoration, breach handling and a documented retention/deletion plan. Re-run tests for every connector or permission change.

A new connector must use an explicit approved host, correctly scoped account, verified schema and bounded pagination. It must not become a generic URL fetcher. A future AI module must use the same tenant and role checks, treat external text as untrusted, and require explicit human approval for high-impact actions; no such module is enabled in this release.
