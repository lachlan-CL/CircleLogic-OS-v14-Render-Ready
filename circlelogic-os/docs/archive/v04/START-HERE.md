# CircleLogic OS v04 - start here

**Real Estate Brain / development pilot / 25 September 2026**

This is the updated working application, not just the design image. The workspace has exactly two pages: **Dashboard** and **API Connections**. Login, two-factor authentication, security settings and connection guides are separate gates or dialogs, not extra workspace pages.

## 1. See the design without installing anything

Open `CircleLogic-OS-v04-Interactive-Preview.html` in a browser. It is included at the root of this package and also supplied separately.

- Username: `testing123`
- Password: `testing12345`
- Preview-only simulated two-factor code: `123456`

The preview first opens an **empty dashboard**. Select **Example data** in the top strip to see the populated design; select **Empty dashboard** to return. All example figures and records are fictional. The preview is not an authentication system, stores no keys, makes no provider requests and cannot access the actual database. Refreshing it resets the simulation.

## 2. Run the real application locally

Use Python 3.11 or newer (tested here on Python 3.13). Extract the ZIP and open a terminal in `circlelogic-os`:

```bash
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
python run.py
```

Open **http://localhost:8000** on that computer. The launcher binds to loopback, not the public network. Use the same testing username and password above. On the first sign-in, scan the QR code with an authenticator, enter its current six-digit code, and save the recovery codes. **123456 is not a bypass in the real app.** Subsequent sign-ins require your authenticator or an unused recovery code.

The testing account is created only for development. Its password is intentionally published, so it must never protect customer information. The server refuses to start in production against a database containing this account. No API credentials or customer data are bundled.

## 3. Add an approved connection

Go to **API Connections**, find the source and select **Add API**. For implemented sources, enter the credential fields or choose a matching JSON file. Uploading a file only fills the form; it does not save automatically.

Select **Save credentials**. For Microsoft, also select **Authorise Microsoft** and complete the provider consent flow. Finally, select **Sync now**. Only a successful import marks the connection connected. Empty successful imports show zero records; missing data remains unavailable; failed refreshes keep the last successful snapshot labelled stale.

**Do not enter real client secrets into the standalone preview, this chat or an unapproved local computer.** Deploy to approved HTTPS infrastructure before connecting customer accounts.

## What is ready, and what is not

| Source | This release |
| --- | --- |
| Agentbox | Visible source and official access guide. Adapter and credential intake are gated pending approved API documentation and implementation. |
| REA Ignite | Read-only REA Partner Platform listing-performance adapter, with reported views, email enquiries and saves when returned. Buyer-intent scores are not implemented. |
| RP Data | Australian access/licensing guide. Adapter and credential intake are gated; US developer credentials are not treated as Australian RP Data access. |
| Proping | Vendor/access confirmation guide. No verified API or email-ingestion adapter; credential intake is gated. |
| Diary / Calendar | Microsoft 365 delegated, read-only calendar OAuth and the next 30 days of events. Private to the connecting login. No inbox access or Google Calendar adapter. |

Adapters were tested with synthetic provider responses, not real vendor accounts. Neither a visual card nor a saved key proves an integration is available.

## Customer instances

An operator provisions each customer with `scripts/provision_workspace.py`. Accounts resolve to their own server-side workspace; data, credentials and permissions are scoped to that workspace. This is logical tenancy in a shared database, **not a separate virtual server per login**. The test account is a different workspace from customer accounts. Do not reuse the testing database for production.

## More help

The in-app **Unsure how to get API keys?** panel has all five guides. `docs/SETUP-GUIDE.html` adds actual screenshots of this application. Vendor access instructions link to official sources; no invented vendor screenshots are used. `docs/TEST-REPORT.md` states exactly what was tested and what remains before customer release.
