# v05 architecture

The browser loads frontend/index.html and sends same-origin JSON requests to the FastAPI backend. The local run.py serves the separate frontend directory at the same origin; source separation does not imply two public servers are required for testing. The inherited deploy templates separate the frontend proxy and API services, but that deployment has not been run here.

The backend identifies the workspace from a server-side authenticated session, not a browser-supplied tenant selector. SQLite contains users, tenants, sessions, encrypted provider credentials, imported records, snapshots and audit events. Every business-data lookup must be scoped by tenant, plus connecting user for Microsoft calendar. This is logical tenancy, not physical infrastructure isolation.

Microsoft path: save three credential fields -> store an encrypted envelope -> build an authorisation-code/PKCE URL -> validate the callback's one-use session/user/workspace state -> server exchanges code for tokens -> user triggers Test and sync -> refresh access if needed -> retrieve read-only CalendarView -> validate and atomically replace the snapshot -> browser reads its authorised calendar panel. A failed import preserves the last successful snapshot as stale. Refresh-token rotation is saved before retrieving calendar pages.

New endpoints:

- GET /api/pilot/readiness: full-MFA local backend/database/vault checks and exact callback; no provider request.
- GET /api/integrations/{provider}/diagnostics: role/user-scoped credential-state booleans, counts, next action and safe error; no credential values or event content.
- Existing PUT /api/integrations/{provider}, POST authorise, callback and POST sync remain the actual connection path. No simulation mode is exposed by the normal server.

The browser's file upload parses a small flat JSON object locally, then sends the reviewed form as JSON on Save. No raw file is kept by the server. The standalone preview is archived and is never served by run.py.

The first pilot uses manual sync. No email sending, calendar write-back, AI scoring or background worker is started. The UI deliberately retains exactly Dashboard and API Connections; setup/security/help live in dialogs.
