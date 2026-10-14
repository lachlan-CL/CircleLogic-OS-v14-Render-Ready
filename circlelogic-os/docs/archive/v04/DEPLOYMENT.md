# Deployment - reviewed pilot work required

No public deployment, Docker build, domain provisioning, TLS certificate issuance or live-provider connection was performed in this delivery. Templates are supplied for a qualified CircleLogic operator to review and test.

## Local development

Run `python run.py` from the extracted root. It binds to `127.0.0.1:8000`, creates a dev-only testing workspace and creates a local vault key in `data/.vault-key` if one is not supplied. Never commit that directory. Stop with Ctrl+C. Restarting retains the same local users and MFA; it does not reset authenticator enrolment.

## Separate approved services

The frontend container is Caddy serving only the live frontend and reverse-proxying `/api` to the API container. The backend container contains Python/FastAPI. Both use the same public HTTPS origin, so cookies and CSRF stay same-origin. The optional worker runs separately and shares the single-node store. The design preview is excluded from the frontend image.

1. Choose approved hosting, domain, data residency, backup and secret-management arrangements.
2. Review and pin/scan base images and installed dependencies before release. Dockerfiles use Python 3.13 and Caddy 2 tags; reproducible digest pinning and image scanning remain operator tasks.
3. Generate a private, non-overwriting environment template on the host:

```bash
python scripts/init_production_env.py --origin https://brain.your-approved-domain.example
```

The generated `.env.production` is sensitive and must not be shared through chat, emailed or committed. Transfer the vault key and provisioning token to approved secret storage and preserve the key across restarts. Loss of the key prevents decrypting credentials and MFA secrets.

4. Use a fresh production data volume without `testing123`. Set `APP_ENV=production`, `ALLOW_SIGNUP=false`, HTTPS `PUBLIC_ORIGIN`, persistent `VAULT_KEY`, and `DOMAIN`. The Compose template expects a private `PROVISION_TOKEN` too; restrict its use to operators.
5. Review the supplied configuration, then test builds and startup:

```bash
docker compose --env-file .env.production -f deploy/compose.yaml config
docker compose --env-file .env.production -f deploy/compose.yaml up --build -d
```

These commands are instructions, not evidence that deployment has succeeded. Verify permissions on the persistent SQLite volume and host storage. Publicly expose only the frontend proxy.

6. Provision a customer owner on an approved operator environment using `scripts/provision_workspace.py` configured to the same intended data store and key. The minimal API container does not contain that script; run it from the approved source checkout against the mounted database with the required environment, or deliberately add a reviewed operator job. Do not copy the local testing database or expose self-service signup as a shortcut.
7. Configure Microsoft Web redirect URIs to match the exact address displayed by this deployment. Confirm provider approvals, allowed agency IDs, consent scopes and real test fixtures. Connect one approved source before expanding.
8. Perform browser-native HTTPS login/MFA, cookie, CSP, redirect/consent, disconnect/revocation and cross-account tests. Run a restore drill and the release checklist before admitting customer data.

## Polling

The local launcher does not start background sync. Once the deployment is approved, the optional worker can be started with the Compose `sync` profile. It polls authorised connections; it is not a live event stream. Monitor stale/error states, token expiry, rate limits and failures. This worker was not deployed during authoring.
