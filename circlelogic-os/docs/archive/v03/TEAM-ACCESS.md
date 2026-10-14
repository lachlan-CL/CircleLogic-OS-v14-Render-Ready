# Team & access - v03

## Two different modes

| Capability | Interactive preview | Full application |
| --- | --- | --- |
| Replace sample people | Yes; editable browser-only profiles | No sample login accounts are created |
| Add a person | Saves a preview profile, not an account | Creates a named, email-bound invitation |
| Name, email and role | Editable preview fields | Name and permitted role editable; login email fixed |
| Persistent storage | Browser localStorage when available, otherwise session-only | Server SQLite database |
| Shared access | None | Individual password and mandatory two-factor setup |
| Invite delivery | No invitations | Copy a private link; no automatic email delivery |
| Tasks | Draft tasks and profile assignments | Workspace tasks assigned to active MFA-enrolled users with task access |
| External systems | Synthetic records only | Existing read-only adapters; membership edits do not write to providers |

Preview profile edits are intentionally not exported into production accounts or converted silently into real permissions. Add people through the full app's invitation flow when ready.

## Owner / administrator workflow

1. Open Team & access and choose Add person. Enter full name, work email and a role.
2. Create the invitation. The person appears under Invitations immediately; no account exists yet.
3. Copy and privately share the one-time 24-hour link. It is not emailed automatically. The full secret link is only shown on creation/reissue; the database stores its hash, not the raw token.
4. On acceptance, the new user appears with 2FA setup pending. Business-data access and assignment are still blocked.
5. After they finish their own authenticator enrolment, the account is Active and eligible for task assignment where the role permits tasks.
6. Manage person changes display name, role or account state. Role/state changes revoke existing sessions; name-only edits do not. Deactivation also erases the user's private Microsoft credentials and snapshots.

Duplicate account or invitation emails are rejected case-insensitively. Existing accepted accounts cannot be reassigned by overwriting their login email. Invite a different person separately. One agency per email/login remains a pilot limitation.

Pending and expired invitations remain visible until accepted, reissued or revoked. Edit / reissue changes the name or role and generates a new 24-hour token; the old token stops working immediately. Revoke prevents subsequent acceptance. Owners and administrators can manage permitted invitations only inside their own tenant.

## Permissions

Owners may grant any supported role. Administrators cannot manage owners/other administrators or create, downgrade, revoke or reissue their privileged invitations. An administrator may edit their own display name without changing their own role. No user can disable their own account or change their own role here. At least one active MFA-enrolled owner must remain.

Supported roles remain Owner, Admin, Agent, Property manager, Finance and Viewer. Roles are fixed bundles in `backend/app/security.py`, not arbitrary per-person ACLs. Ordinary roles do not gain access to the Team administration screen. Privileged writes require a recent MFA check; renew it under Security when requested.

## Task assignment

The New task form lists active, two-factor-enrolled members with task access. Invite-only people, incomplete MFA accounts, disabled accounts and Viewers cannot be assigned new work. Ordinary task-enabled users may create tasks for themselves; Owners/Admins may assign to others. Open a workspace task and choose Reassign task to transfer its assignment. Name changes keep the same user ID and update names on local tasks only.

Disabling a member does not silently transfer their work. Their existing tasks stay visible to the workspace administrator and can be reassigned. Team cards count non-completed workspace tasks, not tasks imported from external products. Sample tasks in the full app remain read-only.

In the preview, replacing a sample profile preserves its ID and draft-task assignments. Draft tasks can be reassigned. Removing a profile with any assigned draft tasks is blocked until the assignments are changed. Preview permissions are descriptive, not real access control.

## API routes

All write routes require the current session, expected request origin, JSON and CSRF verification. Team writes also require recent MFA.

| Route | Purpose |
| --- | --- |
| GET /api/team | Members, assignment eligibility, open-task counts and invitations |
| POST /api/team/invite | Create named private invitation |
| POST /api/team/invitations/{id}/reissue | Rotate token; optionally edit name/role |
| DELETE /api/team/invitations/{id} | Revoke a tenant-scoped invitation |
| GET /api/auth/invitation?token=... | Validate link and return join form defaults; rate-limited |
| POST /api/auth/register | Register a new user using their own password and invite token |
| PATCH /api/team/{user_id} | Update display name, role and active state, not email |
| POST /api/tasks | Create task, optionally assigned to an eligible member |
| PATCH /api/tasks/{task_id} | Update status or reassign a local task |

The preview's `/team/members`, `/preview/reset` and removal routes are an in-browser adapter only. They are not backend account-provisioning APIs.

## Hosting and delivery boundary

A local development URL cannot grant another device access to the local machine. Use the reviewed approved HTTPS deployment and correct public origin for shared access. No email delivery provider has been configured or added. Share invite links only with their intended recipients. No real people were invited as part of generating or testing this release.
