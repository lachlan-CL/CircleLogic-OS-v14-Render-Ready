# v05 changes from v04

Built by modifying the supplied v04 source, not replacing it with another mock-up.

New Windows/macOS/Python launchers; interactive private local account provisioning; validated loopback origin and port; optional browser opening after backend health; readable port/dependency errors; authenticated readiness and safe downloadable connection diagnostics; Microsoft progress and Test and sync; least-privilege account-selection flow; sanitized Microsoft credential errors; bounded refresh after early token rejection; malformed-token handling; UTC request/all-day retention; stale calendar labelling; Host-header checks; validation-error input redaction; cancellation-safe async diagnostic dialogs.

No schema expansion or live-data seeding was added. Microsoft and REA remain the two visible implemented adapters. Agentbox/RP Data/Proping still need approved access and implementation. The known testing login remains development-only. New private workspaces are created through an operator terminal, not an unauthenticated public signup page.

Regression and new tests are described in TEST-REPORT.md. Screenshots show actual application rendering driven by synthetic fixture responses, not vendor-account screenshots or live integrations.
