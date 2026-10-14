# CircleLogic OS v05 - start the working application

**This package runs a backend. It is not another locked HTML preview.** Use only a CircleLogic-approved computer. No account has been connected to Microsoft on your behalf.

## 1. Extract the download

Extract `CircleLogic-OS-v05-Application.zip` completely. Open the `circlelogic-os` folder. Do not run files from inside the ZIP, and do not open `frontend/index.html` as a file.

## 2. Start on Windows

Use an approved Python 3.11 or newer installation. Double-click **START-CIRCLELOGIC.cmd**. The first run creates `.venv` and installs the pinned dependencies. Internet or an approved Python package mirror is needed. After startup it opens your browser; otherwise type `http://localhost:8000`.

Keep the terminal window open while using the app. Closing it stops the backend. Nothing is published to the internet and no router/firewall port needs opening.

On macOS/Linux, open a terminal in the extracted folder and run `python3 launcher.py start`. The `.command` launchers are supplied as a convenience; the Python command is the fallback when OS policy prevents double-click execution. Do not bypass company security controls.

## 3. Create your own login for the connection test

While the backend is running, double-click **CREATE-PRIVATE-WORKSPACE.cmd**. Enter a workspace name, your display name, a new username, your work email and a private password of at least 12 characters. The password is prompted for privately; it is not a command-line argument. No email is sent.

Sign into the app using that new username. Scan the authenticator QR code, enter its current six-digit code and save the recovery codes privately. This is real two-factor authentication. There is no fixed `123456` bypass.

For an initial look with no real credentials, `testing123 / testing12345` still works in its own development workspace. Its published password must not be used to protect a real mailbox or customer data.

## 4. Confirm you are in the running application

Open **API Connections**. The top badge reads **Backend connected**. Select **Check backend setup**. It checks the API, database, credential vault and MFA and shows the exact Microsoft callback. This is only a local check; it does not yet contact Microsoft.

The Microsoft and REA credential fields/file uploads are enabled in this application. Agentbox, RP Data and Proping deliberately show their unfinished-connector notice instead of a non-working secret form.

## 5. Connect an approved Microsoft test mailbox

Follow `docs/LOCAL-TESTING-GUIDE.html` or `docs/MICROSOFT-FIRST-CONNECTION.md`. Have your Microsoft administrator arrange an approved test mailbox and app registration. Do not enter credentials in this chat, the archived preview or an unapproved device.

In **API Connections > Diary / Calendar > Add API**, enter the Application client ID, Directory tenant ID and client secret VALUE. You may instead fill and upload `templates/microsoft-credentials.blank.json`. Do not upload a complete Microsoft app manifest; the form expects the exact flat fields in the template.

Register the exact callback displayed in the form as a Microsoft **Web** redirect. The default is:

```
http://localhost:8000/api/oauth/microsoft/callback
```

Select **Save credentials > Authorise Microsoft**. Select the intended test mailbox and complete consent. On returning, select **Manage > Test and sync**. **Connection checks** explains the current step and displays safe errors.

## 6. Verify one appointment

Create a made-up event named `TEST - CircleLogic inspection` in the test mailbox's **default Outlook calendar**, tomorrow. Do not add real customers or send invitations. Sync and compare the title, local time and location. The dashboard displays Sydney time.

Change that event in Outlook and sync again; confirm it updates without duplication. Delete it and sync again; confirm it disappears. Calendar imports fill only the calendar panel. The CRM, market and buyer-score widgets remain empty until their own approved feeds are implemented and imported.

The connector reads the next 30 days. It does not create, edit, delete or email anything in Microsoft. Changes for this test are made by you in Outlook. Refresh is manual in this launcher; it does not start the optional scheduled worker.

## Useful commands

| Windows file | Purpose | Python equivalent |
| --- | --- | --- |
| START-CIRCLELOGIC.cmd | Install dependencies as needed and start locally | `python launcher.py start` |
| CREATE-PRIVATE-WORKSPACE.cmd | Create a private test login/workspace | `python launcher.py create` |
| CHECK-SETUP.cmd | Check local configuration without provider traffic | `python launcher.py check` |
| RUN-AUTOMATED-TESTS.cmd | Run synthetic backend tests | `python launcher.py test` |

## Troubleshooting

**Python is not found:** ask IT for an approved Python 3.11+ installation. **Package download fails:** check approved internet/package-mirror access; do not disable certificate verification or security software. **Address already in use:** stop the existing server, or copy `.env.example` to `.env`, change PUBLIC_ORIGIN to another localhost port and update the Microsoft redirect to match. Always open the exact configured address: localhost and 127.0.0.1 are not interchangeable for this app's origin checks.

**Uploads still look disabled:** you are probably in the old preview, or opening one of the three unfinished connectors. Use the localhost app and Microsoft Calendar or REA. **Consent denied:** ask the Microsoft administrator to review app/tenant permissions. **Client secret rejected:** use the secret Value, not its Secret ID. **No appointments:** check the selected account, default calendar, next-30-days window and time zone. A successful empty import is not an error.

**Lost authenticator:** use an unused recovery code. Do not delete the database to regain access when it contains information you need; involve the authorised operator. No public password-reset email service is included.

## Data and deployment

Your local data is under `data/` by default. The generated vault key is `data/.vault-key`. Protect both, together with any `.env` file; never upload them to chat or share them with the application ZIP. The database contains stored records that are not individually encrypted by the app. Do not reuse this testing database for customer production.

The Windows/macOS wrappers are supplied but were not executed on those operating systems here. A fresh pip install was attempted but blocked by the authoring environment's package-server DNS; tests used installed dependencies. See `docs/TEST-REPORT.md`. This does not replace a real provider-account test or production security review.
