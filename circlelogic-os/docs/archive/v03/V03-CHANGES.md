# CircleLogic OS v03 - release changes

Date: 25 September 2026. Version: 0.3.0-pilot.

## Branding

The product is CircleLogic OS. Sidebar, sign-in, mobile identity, favicon, browser titles, local-data source labels, API title and new authenticator labels are updated. The CL mark is copied from the original vector paths in the user-provided onboarding pack. Only the logo artwork is included, not the pack, its fonts or any client material. This is a reference extraction, not a new approved master-brand asset.

## Functional team and tasks

The preview supports adding/replacing/editing profiles, removing unused profiles, persistence through browser localStorage when available, session-only fallback and a reset control. The full app supports named invitations, visible pending and expired states, token rotation, revocation, own-authenticator onboarding, display-name updates and existing role/deactivation controls. No real email has been sent and no invitation-delivery service has been added.

Task creation has a team-member selector. Owners and administrators can reassign local tasks. Local task labels follow display-name updates by stable user ID. Inactive, incomplete-MFA and Viewer accounts are not eligible for new task assignments. External provider records are not rewritten.

## Upgrade from v02

1. Stop API and worker processes. Take a verified backup of the database and deployment configuration; retain the existing vault encryption key in the approved secret store.
2. Replace application source/frontend assets without deleting the existing `data` directory or `.env` / `.env.production`. Preserve `DATA_DIR`, `VAULT_KEY`, `PUBLIC_ORIGIN` and the deployment's existing data volumes and Compose project name. Renaming a project directory must not accidentally select an empty volume.
3. Rebuild the frontend service as well as the backend. The frontend Dockerfile now explicitly includes `frontend/assets/circlelogic-logo.svg`.
4. Start the application. Startup adds `id`, `name` and `created_at` to invitation rows where absent; missing invitation IDs are filled without changing existing token hashes. The migration is transactional and idempotent.
5. Verify existing login and MFA, existing workspace data, invitation creation/reissue/acceptance, task assignment, and the new logo over the actual HTTPS host. An old unnamed pending invite needs a name entered when it is edited/reissued.

Existing users, password hashes, authenticator secrets, sessions, tenant IDs, tasks and connections are retained. The internal `agency_session` cookie and existing volume keys are intentionally retained for compatibility. New authenticator entries use CircleLogic OS; older authenticator app labels may retain their prior display name without preventing their codes from working.

Do not apply the update by making fresh unrelated user accounts, deleting the old database or replacing the vault key. Upgrades of a real deployment still require operator validation and an actual backup/restore test.

## Verification and remaining gates

76 backend tests pass, including the v02 regression suite and 17 added team/migration tests. Three embedded Chromium scripts pass. Actual loopback browser navigation was blocked by the authoring browser's administrator policy; the optional `browser_team_http.py` script is supplied for testing in an approved environment but did not run successfully here. See TEST-REPORT.md for the exact distinction between tested routes/UI and untested browser transport/persistence.

This is not a new production certification. Existing provider, security, shared-hosting, backups and deployment release gates remain. No changes have been made to the implemented/unimplemented integration boundaries.
