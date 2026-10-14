# First Microsoft Calendar connection - v05

This guide covers the running local application and an approved Microsoft 365 test mailbox. It does not claim a live connection was made in the authoring environment. Provider documentation checked 25 September 2026. The steps below paraphrase the official sources; account-specific settings behind your sign-in were not inspected.

## Prepare the application

Extract the package, run START-CIRCLELOGIC, create a private workspace with CREATE-PRIVATE-WORKSPACE, and sign in with MFA. Open API Connections > Check backend setup. Resolve any failed local checks first. Do not use the published testing123 password for a real mailbox.

## Register the Microsoft application

Ask an administrator with the appropriate Microsoft access to work in the organisation that owns the approved test mailbox. In Microsoft Entra, open Entra ID > App registrations > New registration. Choose a clear name such as CircleLogic Calendar Pilot and the single-tenant account option for this organisation. Record the Application (client) ID and Directory (tenant) ID from Overview. This pilot is for a work/school Microsoft 365 mailbox, not a Google calendar. [Official registration instructions](https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app).

## Register the return address

Open the Calendar credential form in CircleLogic and copy the Web redirect URI it displays. In the Microsoft app's Authentication settings, add that exact address as a Web redirect. Do not choose the SPA platform for this server-side exchange. At the default local configuration it is `http://localhost:8000/api/oauth/microsoft/callback`. Microsoft documents HTTP localhost redirects for locally running web apps; customer hosting should use the approved HTTPS origin. [Official redirect instructions](https://learn.microsoft.com/en-us/entra/identity-platform/how-to-add-redirect-uri).

## Create the test credential

In Certificates & secrets > Client secrets > New client secret, select an approved short expiry and record the secret **Value** immediately. Do not copy the Secret ID. This build supports the client-secret testing route; Microsoft recommends stronger certificate or federated credentials for production, which are not implemented in this adapter. Do not email or paste the secret into chat. [Official credential instructions](https://learn.microsoft.com/en-us/entra/identity-platform/how-to-add-credentials).

## Limit the permissions

In API permissions, add Microsoft Graph **Delegated** `Calendars.ReadBasic`. The application's authorisation flow also requests `offline_access` so access can be refreshed. It does not request email permissions or calendar write access. Remove unused default permissions from this dedicated pilot registration where your administrator approves. Obtain administrator consent when the organisation's policy requires it. [Calendar API permissions](https://learn.microsoft.com/en-us/graph/api/calendar-list-calendarview?view=graph-rest-1.0) and [Microsoft authorisation-code flow](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow).

## Save, authorise, import

In CircleLogic's Calendar form, enter the three values, or fill the supplied flat JSON template and upload it. Uploading only fills the form. Select Save credentials. Then select Authorise Microsoft, choose the intended test mailbox and complete consent. The app returns to API Connections. Select Calendar > Manage > Test and sync. The count shown is the actual number of records in the completed import; cancelled events can be included in that raw count but are not listed as upcoming appointments.

## Prove the end result

Create one artificial event in that account's default Outlook calendar tomorrow. Do not invite real people. Compare its title, time and location in the CircleLogic dashboard; the dashboard uses Sydney time. Change the appointment in Outlook, then sync and check it updates once. Delete it in Outlook, then sync and check it disappears. Test an all-day event, a recurring series and an empty period as well. The API expands recurring occurrences/exceptions within the requested time range and can paginate; the adapter follows supported next-page links. [CalendarView reference](https://learn.microsoft.com/en-us/graph/api/calendar-list-calendarview?view=graph-rest-1.0).

## Diagnose and retire the test

Connection checks displays save/authorise/import progress without returning stored secrets. It can download a report containing statuses and record counts, not event titles or tokens. Common credential errors have fixed, redacted explanations based on Microsoft's documented error codes. An error shown in the Microsoft website itself still needs administrator review. [Error reference](https://learn.microsoft.com/en-us/entra/identity-platform/reference-error-codes).

Disconnect in CircleLogic to delete its current connection and imported snapshot. Separately revoke app consent and retire the test secret in Microsoft. Local deletion is logical database deletion, not a claim that all historical backups or filesystem remnants are erased. Protect/retire test backups under CircleLogic's retention process.
