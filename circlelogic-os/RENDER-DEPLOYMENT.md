# CircleLogic OS v14 - Render hosting instructions

This is a prepared hosting package, **not a live deployment**. The code has a FastAPI backend and SQLite database; it is **not** a static site. Use a Render **Web Service**, environment **Docker**, and **Dockerfile Path** `./Dockerfile.render` (when this folder is the repository root).

## Before uploading
- Use only a company-approved GitHub and Render account. Keep the repository PRIVATE.
- Do not upload customer data, local `data/`, `.env`, OAuth secrets or database files. This package contains no local database or `.env` file.
- The original `deploy/` directory has older development templates; use `Dockerfile.render` instead.

## Render service configuration
1. Create a private GitHub repository, upload this folder's contents (not the enclosing ZIP), and connect it to Render > New > Web Service.
2. Runtime: **Docker**. Dockerfile path: `./Dockerfile.render`. Health check path: `/api/health`.
3. Set environment variables:
   - `APP_ENV` = `production`
   - `ALLOW_SIGNUP` = `false`
   - `BOOTSTRAP_TESTING_ACCOUNT` = `false`
   - `DATA_DIR` = `/app/data`
   - `PUBLIC_ORIGIN` = `https://YOUR-EXACT-RENDER-HOSTNAME.onrender.com` (replace with actual Render URL, no trailing slash)
   - `VAULT_KEY` = persistent **Fernet** key; set as a Render secret, never commit it. Generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
4. **Persistent Disk:** Attach a Render disk with mount path `/app/data` and choose a paid plan supporting persistent disks. SQLite data stored only on an ephemeral filesystem disappears after redeploy/restart. Backups are separately required.
5. Once Render assigns the real hostname, confirm that `PUBLIC_ORIGIN` exactly matches the `https://` URL and redeploy. The API checks Host and Origin against this value.
6. Use Render's secure shell/approved operator access to create an initial private account after first start (the package intentionally does not create public default credentials):
   `cd /app && python scripts/provision_workspace.py --agency "Circle Logic Demo" --username YOUR_USERNAME --email YOUR_EMAIL --name "Demo Admin"`
   The command asks for a password privately. The first login enrols an authenticator for 2FA. If a secure shell is unavailable on the chosen plan, provision via an authorised offline migration before deployment; do not enable public signup or reintroduce the known testing account.
7. Open `/api/health`, then the root URL and test login, 2FA, session persistence across a redeploy, and dashboard flows.

## Important cautions
- The zip is **not independently security-audited**. Production settings disable public signup, but making the site reachable over the Internet is still a security decision. Start with fabricated demo data and restrict access appropriately.
- **Free Render web services** are not a suitable persistent database host here. For a truly free public demo, the application would need a different, intentionally stateless demo implementation or an externally managed data store.
- OAuth integrations require changing provider callback registrations to the exact deployed HTTPS callback URLs and retesting. Do not assume connectors are live just because the UI has a Connect button.
- Backups, recovery checks, log hygiene, MFA, rate limiting, secrets rotation, and a security review are needed before real client data.
- `PUBLIC_ORIGIN` must be the complete origin without a path or trailing slash; avoid custom-domain redirects that change the Host/Origin unexpectedly.

## Local Docker smoke test
From this repository root, with Docker installed:
`docker build -f Dockerfile.render -t circlelogic-render .`
The resulting image must be run with a production HTTPS origin and persistent volume on the real host, or development settings for local-only testing. The image has not been built in this preparation environment.
