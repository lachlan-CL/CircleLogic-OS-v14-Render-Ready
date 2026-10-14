# v06 changes

- Replaced the long connection form with software name, setup-guide link, one masked paste field and Save key.
- Removed JSON-file upload, credential templates and callback fields from the entry window.
- Moved required non-secret Microsoft/REA identifiers and the server-derived callback to a one-time form inside the setup guide.
- Added scoped/encrypted staged setup storage and a direct-key backend endpoint, reusing the existing encrypted credential save path.
- Reused existing v05 provider IDs automatically during key rotation; no forced re-onboarding for configured connections.
- Preserved MFA, CSRF, role and tenant/user boundaries, OAuth, sync and unfinished-provider gates.
- Added 44 backend tests, an updated 48-check embedded UI harness and a 37-check loopback harness.
- Supplied a checked, code-only local updater for v05; database/settings/key files are never included in the update payload.

This release is not a Render deployment or a live-provider certification.
