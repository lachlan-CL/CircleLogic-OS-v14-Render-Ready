# CircleLogic OS v07 - Google Calendar test connection

v07 adds **Google Calendar** as a testable read-only calendar option. Microsoft Calendar remains available. The Google connection window stays deliberately simple: software name, **Setup guide**, one masked field for the Google OAuth client secret, and **Save key**.

## Updating your current v06 installation

Use the separately supplied **CircleLogic-OS-v07-Update.zip**. Stop the CircleLogic server first. Extract the update and run **APPLY-UPDATE.cmd**, then choose your existing `circlelogic-os` folder. The updater preserves `.env`, `data/`, the database, vault key and `.venv`, and makes a backup of replaced code.

This v07 updater also includes the corrected startup launcher, so it is safe whether you already applied the earlier v06 startup fix or not. After updating, start **START-CIRCLELOGIC.cmd** and press **Ctrl+F5** in the browser. The footer should say **v07**.

## New installation

Extract **CircleLogic-OS-v07-Application.zip**. On an approved computer with Python 3.11+, start `START-CIRCLELOGIC.cmd` on Windows or `python3 launcher.py start` on macOS/Linux. Use a private workspace and real authenticator setup before connecting an account.

## Connect Google Calendar

1. Open **API Connections > Google Calendar > Setup guide**.
2. In Google Cloud / Google Auth Platform, create or choose a project and enable the **Google Calendar API**.
3. Configure the OAuth consent screen. For a private development test, keep the app in testing and add the Google account you intend to use as a test user when required.
4. Create an OAuth **Web application** client. Copy the exact CircleLogic **Google Calendar redirect URI** shown in the Setup guide into the Web application's authorised redirect URIs.
5. Copy the Google OAuth **client ID** (normally ending `.apps.googleusercontent.com`) into CircleLogic's One-time connection setup and save it.
6. Copy the matching **client secret** from Google, return to the simple connection window, paste it into the one masked field and select **Save key**.
7. Select **Authorise Google Calendar**. Sign into the intended Google account and approve the read-only calendar permission.
8. Return to CircleLogic and select **Test and sync**.
9. Create a made-up event in the Google account's primary calendar, sync again and check its title, time and location on the dashboard. Update and then delete the event in Google, syncing after each change to verify the integration.

CircleLogic requests `calendar.events.readonly`, reads the signed-in user's **primary calendar** for the next 30 days, and does not create, edit or delete Google events.

### Important terminology

Google Calendar does **not** use a simple standalone API key to read a private user's calendar. The value pasted into CircleLogic is the **OAuth client secret** belonging to the Web application whose client ID was saved in the Setup guide. Calendar access begins only after the user completes Google's consent flow.

## Microsoft and REA

Microsoft Calendar and REA remain available. Their existing one-time provider identifiers stay in their Setup guides and their client secrets are pasted into the same single-field connection UI.

## Other systems

Agentbox, Australian RP Data and Proping remain gated. They do not collect credentials until a supported connector is implemented.

## Security / pilot limits

Do not use the public `testing123` account for a real Google calendar. Use a private CircleLogic workspace and a made-up test event. The backend encrypts stored provider credentials and does not return saved secrets to the browser. Disconnecting removes that provider's stored setup, credentials and imported snapshot for the current owner.

This package was tested with synthetic Google provider responses. A real Google consent round-trip still needs to be performed on your approved installation before treating the connector as verified.
