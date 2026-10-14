# Development and deployment handover

## Local use

Use Python 3.13, a virtual environment, `pip install -r backend/requirements.txt`, then `python run.py` from the project root. Visit `http://localhost:8000`. No npm build is required. The local server binds to loopback and is not a hosted client service.

`run.py` reads `.env` when present. Copy `.env.example` only for local development. Local signup is enabled by default. SQLite files and a development vault key appear in `data/`; this directory must not be committed, uploaded into chat or included in a release archive. Deleting the vault key makes stored connection and MFA secrets unreadable.

Use a clean separate development database. Do not run tests against a client database. The automated suite creates temporary databases and synthetic accounts.

## Separate frontend and backend deployment template

The `deploy/` directory supplies a Docker Compose/Caddy **template**. Docker was not available in the authoring environment, so this configuration has not been built, publicly deployed or TLS-tested. Validate it in a controlled staging environment before use. Pin reviewed image digests and scan dependencies rather than treating mutable base tags as a production supply-chain lock.

The API image contains the Python backend. The frontend image serves HTML/CSS/JS and proxies `/api/*` to the API over the private container network. Only the frontend publishes host ports. Both browser traffic and OAuth callbacks use one HTTPS origin. The API's database is a persistent local named volume; this is a **single-host pilot topology**, not a horizontally scalable service.

Generate a private configuration on the approved host:

```sh
python scripts/init_production_env.py --origin https://agencyos.YOUR-DOMAIN
```

This creates `.env.production` without overwriting an existing file, generates a Fernet key and a high-entropy operator provisioning token, and disables public workspace signup. Keep these values private and migrate them into the operator's approved secret-management process. Register each provider's callback with the exact same public origin.

The intended staging commands are:

```sh
docker compose --env-file .env.production -f deploy/compose.yaml config
docker compose --env-file .env.production -f deploy/compose.yaml up --build -d
```

Prerequisites include an approved host, persistent encrypted disk, DNS pointing to that host, inbound ports 80/443 and provider-approved outbound HTTPS. Configure perimeter rate limiting, monitoring and backup controls. Check actual access/logging rules; OAuth query strings and secrets must not be stored in access logs. The API command disables its access log.

Create the initial agency from the setup UI using the private operator provisioning code. Do not issue this code to ordinary clients. Invite client owners/members into the intended tenant through Team & access. New colleagues should follow their invitation, not create a separate workspace. Choose the least necessary role and require individual authenticator enrolment.

## Polling worker

Manual **Sync now** is sufficient for a controlled first test. A separate worker can poll previously authorised/configured connections. For local testing, from the backend directory with the same `DATA_DIR` and `VAULT_KEY` as the API:

```sh
python -m app.worker --once
# or continuously, default 900 seconds between complete polling cycles:
python -m app.worker --interval 900
```

`run.py` reads `.env`; `python -m app.worker` does not. Set/export the required environment values explicitly. Relative data paths must resolve to the same actual directory as the API; absolute paths are safer. The worker never performs first-time user consent.

The deployment template's worker is opt-in:

```sh
docker compose --env-file .env.production -f deploy/compose.yaml --profile sync up -d
```

Review each provider's aggregate quota before enabling it. This implementation polls sequentially, uses full snapshots, caps each connector at 100 pages and a 180-second request budget, and marks data stale after an hour. It has no webhook intake, distributed job queue or incremental cursor strategy. Larger agencies and more tenants need measured capacity, provider-specific budgets, incremental sync and a managed database/queue design.

## Backup and restore

Back up the live SQLite database using SQLite's online backup mechanism or a verified stopped-service procedure that accounts for WAL files. Copying just the main database file while writers are active is not the supplied backup strategy. No scheduled backup service is included.

Keep a separately protected copy of the exact vault key. Restore database and matching key together into an isolated test environment, verify account/MFA decryption and source snapshots, then rotate affected credentials when policy requires. Encrypt backups, limit operators, specify retention and rehearse restoration. A disconnected record can still exist in an old backup until retention/deletion procedures remove it.

There is no built-in seamless key-rotation migration, downgrade migration, tenant portability tool or database schema migration framework beyond the initial schema version. Design and test these before a broader service rollout. Do not simply replace `VAULT_KEY` on an existing database.

## Staging verification

Confirm valid HTTPS, Secure/HttpOnly/SameSite cookies in a real browser, exact Origin/CSRF enforcement, no cross-origin embedding, expected role restrictions, tenant isolation, OAuth redirects and refresh rotation, empty/large datasets, account mismatch, disconnect races, private Microsoft isolation, source totals and recovery from provider/host outage. Run an independent security review and user acceptance testing. The included mocks and embedded browser checks do not replace these tests.
