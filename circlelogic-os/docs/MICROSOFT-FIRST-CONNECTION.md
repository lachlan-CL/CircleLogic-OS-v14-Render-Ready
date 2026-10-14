# Microsoft Calendar - first connection in v06

Use a private CircleLogic login with real MFA and an approved test mailbox. The known testing123 account is not a Microsoft app registration and its password is not a client secret.

Open API Connections > Diary / Calendar > Add API > Setup guide. Follow the in-app Microsoft instructions with your administrator. In the app registration Overview, copy the Application (client) ID and Directory (tenant) ID into One-time connection setup. Register the exact Web redirect URI displayed in that guide. The local default is `http://localhost:8000/api/oauth/microsoft/callback`; hosted installations must use their configured approved HTTPS origin.

Set the delegated Calendars.ReadBasic permission with offline_access for refresh as documented by the existing connector; do not add write or mail permissions. Complete administrator consent where your organisation requires it. The pilot uses a client secret credential. Certificate/federated-client authentication is not implemented here.

Select Save setup and paste key. Copy only the client secret VALUE from the Microsoft app registration into the compact key field. Select Save key, then Authorise Microsoft, finish provider consent, return and Test and sync. No JSON file, secret ID, access token, normal mailbox password or CircleLogic username is accepted as a substitute for the required provider credentials.

Create a made-up appointment in the test mailbox's default Outlook calendar. Compare it with the dashboard after sync, then change and delete it in Outlook and repeat sync. The connection reads the next 30 days and does not send invitations, write to calendars or read email. UI success does not replace a live acceptance test.

Official references (authentication requirements reviewed 2 October 2026):

- https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow
- https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app
- https://learn.microsoft.com/en-us/entra/identity-platform/how-to-add-credentials

The screenshot in LOCAL-TESTING-GUIDE.html is of this application, not an invented Microsoft portal screen.
