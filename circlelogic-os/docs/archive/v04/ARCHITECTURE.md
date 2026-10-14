# Architecture - v04

## Separation of responsibilities

`frontend/` is static HTML, CSS and JavaScript. It handles the two-page workspace, dialogs, display formatting and local credential file parsing. It never chooses a tenant ID, stores API keys in browser storage or connects directly to vendor APIs.

`backend/app/` verifies passwords and TOTP, resolves users to tenant IDs, checks roles, stores encrypted secrets and performs provider requests. Browser calls are same-origin under `/api`. The local runner serves both parts for convenience; deployment templates use separate frontend and backend containers behind one HTTPS origin.

## Authentication lifecycle

Password verification creates a short, limited session. A new account is in `enrol`; its authenticator secret and QR are available only in this session. Verification enables MFA, generates hashed one-use recovery codes and rotates to a full session. A returning account is in `mfa` until a valid TOTP or recovery code is supplied. Mutations require same-origin JSON and CSRF. Sensitive changes also require MFA verified within the previous ten minutes.

Usernames are optional on existing accounts, unique when present and normalized by supported creation paths. Email logins remain valid. Public registration is off by default. The published testing account is dev/test-only and is never created for a production launch.

## Tenancy and private data

Each user belongs to one `tenant_id`, resolved from the authenticated server session. Shared connections are tenant-scoped; Microsoft connections are also scoped by connecting `owner_id`. Database reads filter by those values and enforce role permissions. Even a workspace owner does not receive another member's private calendar snapshot.

This is logical tenant isolation in SQLite, not separate physical databases, containers or encryption masters per customer. The encryption context binds sealed values to tenant/provider/owner, but the deployment still uses one master vault key. Cross-customer operator access and stronger physical isolation require a production design decision.

## Snapshot semantics

`unavailable` has null totals; `live` represents a successful imported snapshot, not a streaming connection. A valid empty response has zero records. Incomplete/invalid results do not replace the previous snapshot. Expired snapshots or failed refreshes show stale data. Records and snapshots are replaced atomically after every required module and page validates. Per-connection leases and revisions prevent a concurrent disconnect or credential change from accepting obsolete results.

`brain.py` explicitly reads the requested providers rather than using the old default Rex source mapping. Missing Agentbox, RP Data, Proping or buyer-score feeds remain missing. No demo module is imported by the backend.

## Five-provider UI contract

`/api/brain/connections` returns exactly Agentbox, REA, RP Data, Proping and Microsoft. Gated adapters have no credential fields and reject attempted credential saves. REA reads Campaign listing-performance reports; Microsoft reads a private calendar. The legacy catalog retains other adapters for backward compatibility, but they are not exposed as navigation choices in this release.

## Operational boundaries

The optional single-node worker can poll already authorised connections. It is not started by the local launcher. No autonomous agent, LLM, lead scoring or provider write-back runs here. Imported record payloads are not encrypted individually in SQLite: encrypt host disks, backups and storage appropriately before customer use. See SECURITY.md and RELEASE-CHECKLIST.md.
