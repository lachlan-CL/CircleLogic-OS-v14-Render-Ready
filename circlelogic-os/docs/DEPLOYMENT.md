# v05 deployment boundary

This delivery is a local/private backend pilot, not a hosted service. Use START-HERE.md for the tested local route. The separate-service Docker/Caddy templates in deploy/ are inherited development templates and were not built or deployed here.

Before a shared pilot, an authorised CircleLogic operator must choose approved HTTPS hosting, configure a stable PUBLIC_ORIGIN, provision private workspaces on a fresh database, protect persistent storage/master keys and register the matching Microsoft Web callback. The Host header forwarded to the API must match PUBLIC_ORIGIN. Do not expose the local testing login, local database or development API docs publicly.

Complete live Microsoft/REA acceptance, native browser OAuth/cookie/CSP tests, certificates/secret lifecycle, backup/restore, role/tenant penetration tests, retention controls and platform/dependency review. The Microsoft adapter currently supports a client secret, not certificate/federated authentication. Customer data is not approved for this local pilot merely because it has MFA.

Historical v04 deployment notes are in archive/v04/DEPLOYMENT.md. They are not evidence of a completed deployment. No external host or public address has been created by this update.
