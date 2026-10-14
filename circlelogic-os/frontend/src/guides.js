/* Verified public routes, checked 2 October 2026. No invented vendor screens. */
window.BRAIN_GUIDES = {
 agentbox: {
  title: 'Connect Agentbox', tag: 'Provider approval required',
  intro: 'Agentbox is now Reapit Sales. Its official integrator application is the verified starting point, not a guessed Settings > API menu.',
  steps: [
   ['Confirm the office and owner', 'Ask your agency administrator to identify the Agentbox office to connect. Keep Agentbox as the source of truth; the Brain is a read-only companion.'],
   ['Apply as an integration partner', 'CircleLogic should complete the official Reapit Sales integrator application. Third parties are required to go through this application process.'],
   ['Confirm the approved contract', 'Ask Reapit for the supported authentication method, office authorisation, endpoint documentation, allowed fields and rate limits. Do not assume the credentials are a client ID and secret.'],
   ['Complete the connector first', 'This release has no live Agentbox adapter. CircleLogic must implement and test the approved contract before key entry is enabled.'],
   ['Return to API Connections', 'Select Agentbox > Add API to see the current status and these instructions. No Agentbox credentials are accepted while the adapter is pending.']
  ],
  note: 'No public self-service key-generation sequence was verified. Do not enter your normal Agentbox password into this platform.',
  links: [['Official integrator application','https://www.agentbox.com.au/integrator-application']]
 },
 rea: {
  title: 'Connect REA Ignite', tag: 'REA Partner Platform',
  intro: 'The implemented connection reads listing-performance reports through the REA Partner Platform. It is not a direct sign-in to Ignite and does not yet import buyer-intent scores.',
  steps: [
   ['Apply for Partner Platform access', 'CircleLogic, as the integrator, follows the REA onboarding guide: review the terms and submit the linked application. REA support supplies approved Partner Platform credentials.'],
   ['Arrange agency authorisation', 'The agency must authorise the integration. Follow REA\'s current customer-permissions instructions and request campaign:listing-performance:read. A partner account alone does not authorise every agency.'],
   ['Prepare the three fields', 'Have the partner Client ID, Client secret and the authorised REA Agency ID ready. Confirm them with your approved REA contact. Never use your Ignite account password.'],
   ['Set up once, then paste the key', 'Open API Connections > REA Ignite > Setup guide. Save the Partner client ID and REA agency ID in One-time connection setup. Return to the connection window, paste the Partner client secret into the single key box and select Save key. No JSON file is needed.'],
   ['Test and import', 'Select Sync now. Only a completed, validated response marks the source connected. An error preserves any previous snapshot and does not generate substitute data.']
  ],
  note: 'Listing performance and buyer intent are different data products. The sample buyer scores in the design preview are illustrative only; no buyer-score availability is claimed.',
  links: [['Official onboarding','https://partner.realestate.com.au/getting-started/overview/'],['Authentication','https://partner.realestate.com.au/getting-started/authentication/'],['Agency authorisation','https://partner.realestate.com.au/getting-started/authorization/']]
 },
 rpdata: {
  title: 'Connect RP Data', tag: 'Australian access must be confirmed',
  intro: 'Use Cotality\'s Australian RP Data team to establish the permitted integration route. A subscription or a US developer account is not proof that this dashboard may access Australian records.',
  steps: [
   ['Identify your Australian subscription', 'Ask the account administrator for the RP Data plan and the intended office/users. Do not share the login password.'],
   ['Ask about the appropriate integration route', 'Use the contact form on Cotality\'s Australian RP Data page. Ask whether CircleLogic can be an eligible RP Inside/PropTech integration or needs a separate API agreement.'],
   ['Confirm permissions and licensing', 'Request written confirmation of the allowed Australian datasets, display rights, retention, office/user entitlements, API authentication and limits. Treat ownership matching as unconfirmed until explicitly approved.'],
   ['Obtain the exact technical contract', 'Have Cotality identify the correct regional documentation and credential format. Do not substitute the US MCP client-credentials guide.'],
   ['Finish the adapter, then connect', 'The RP Data adapter is pending. API Connections > RP Data currently opens this access checklist; key entry and live import are deliberately disabled.']
  ],
  note: 'The public RP Data page describes RP Inside connections for eligible CRMs/PropTech platforms. It does not establish that CircleLogic is eligible or supply a verified self-service key-generation flow.',
  links: [['Australian RP Data and contact form','https://www.cotality.com/au/products/rp-data-real-estate']]
 },
 proping: {
  title: 'Connect Proping', tag: 'Integration route not yet verified',
  intro: 'This uses Proping (proping.com.au), the daily property-alert service. Confirm it is the service called "Propping" in your agency materials before implementing a connector.',
  steps: [
   ['Confirm the service', 'Ask the office administrator to confirm the vendor and the alert email account. The public Proping product describes daily email reports.'],
   ['Contact Proping', 'Use the official contact page to ask whether an API, licensed export or authorised email-ingestion route is available for your account.'],
   ['Get written approval and documentation', 'Ask for the permitted data, authentication format, limits and retention rules. A reply offering an API is needed before designing a credential form; do not assume an API key exists.'],
   ['Review email access separately', 'An email-based alternative would need separate permissions, privacy controls and parsing tests. The calendar integration in this build cannot read your inbox.'],
   ['Return after the connector is approved', 'Proping > Add API currently shows this checklist. No invented API endpoint, guessed credential field or automatic email ingestion is enabled.']
  ],
  note: 'Public self-service API documentation was not located. That is not proof that a private integration is unavailable; it needs confirmation from Proping.',
  links: [['Product and email-alert description','https://www.proping.com.au/'],['Official contact page','https://www.proping.com.au/contact']]
 },
 microsoft: {
  title: 'Connect your diary / calendar', tag: 'Microsoft 365 - read-only',
  intro: 'Microsoft 365 remains available alongside Google Calendar. Your Microsoft calendar is private to your CircleLogic login; other workspace users do not inherit access. Use CREATE-PRIVATE-WORKSPACE and an approved test mailbox, not the published testing123 login, for a real connection.',
  steps: [
   ['Have your administrator register an application', 'In the Microsoft Entra admin center, open Entra ID > App registrations > New registration. Choose a descriptive name and the account type approved by your administrator. For a single-organisation pilot, use that organisation\'s tenant.'],
   ['Configure the exact redirect address', 'In CircleLogic, open API Connections > Diary / Calendar > Setup guide and copy the Web redirect URI from One-time connection setup. Add that exact address as a Web redirect in the Microsoft app registration. Use HTTPS on an approved deployed host; localhost is development-only.'],
   ['Record the application and directory IDs', 'From the registration Overview, copy Application (client) ID and Directory (tenant) ID into One-time connection setup in this guide. Select Save setup and paste key. These IDs are saved for future key changes.'],
   ['Create the application credential', 'Open Certificates & secrets > Client secrets > New client secret. Set an approved expiry and copy the secret VALUE immediately, not its Secret ID. This pilot uses a client secret; certificate/federated-credential support would need an adapter change for a hardened deployment.'],
   ['Set least-privilege delegated access', 'Add the Microsoft Graph delegated Calendars.ReadBasic permission. The sign-in flow also requests offline_access for refresh tokens. Do not grant Mail.Read, Calendars.ReadWrite or application-wide mailbox access. Obtain administrator consent when your tenant requires it.'],
   ['Save, authorise and sync', 'Return to the compact connection window, paste only the client secret VALUE and select Save key. No JSON file is required. Select Authorise Microsoft, sign in to the correct account and consent. After returning, select Test and sync to import the next 30 days. Create one made-up test event in the default Outlook calendar, then verify it on the dashboard. Connection checks shows the current step and safe error messages.']
  ],
  note: 'The published testing123 login is not a Microsoft client ID or API key. Saving a secret does not grant access. The Microsoft consent redirect and a successful sync are separate steps. Disconnecting here erases local credentials/data; revoke the app in Microsoft as well when retiring access.',
  links: [['Register an application','https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app'],['Add credentials','https://learn.microsoft.com/en-us/entra/identity-platform/how-to-add-credentials'],['Calendar permissions and API','https://learn.microsoft.com/en-us/graph/api/calendar-list-calendarview?view=graph-rest-1.0']]
 },
 google: {
  title: 'Connect Google Calendar', tag: 'Google OAuth - read-only',
  intro: 'This connection reads events from the signed-in Google account\'s primary calendar for the next 30 days. It is private to your CircleLogic login and does not create, edit or delete calendar events.',
  steps: [
   ['Create or choose a Google Cloud project', 'Open Google Cloud Console with the account approved for testing. Create a project or choose an existing project that will own the CircleLogic test integration.'],
   ['Enable the Google Calendar API', 'In APIs & Services > Library, find Google Calendar API and enable it for the project.'],
   ['Configure OAuth consent', 'In Google Auth Platform / OAuth consent, configure the app information. Keep the app in testing while you validate the integration and add the Google account you will use as a test user when Google requires it.'],
   ['Create a Web application OAuth client', 'In Google Auth Platform > Clients (or APIs & Services > Credentials), create an OAuth client ID for a Web application. Open CircleLogic OS > Google Calendar > Setup guide and add the exact redirect URI shown here to Authorized redirect URIs.'],
   ['Save the client ID once', 'Copy the Google OAuth client ID ending in .apps.googleusercontent.com into One-time connection setup below and select Save setup and paste key.'],
   ['Paste the client secret', 'Copy the client secret from the same Google Web application credential, return to the compact connection window and paste it into the single key field. Select Save key.'],
   ['Authorise and sync', 'Select Authorise Google Calendar, sign in to the intended Google account, approve the read-only calendar-events permission, return to CircleLogic OS, then select Test and sync. Create one made-up event in the primary calendar and confirm its title, time and location appear on the dashboard.']
  ],
  note: 'This uses OAuth 2.0, not a standalone Google API key. CircleLogic requests only the calendar.events.readonly scope. Saving the client secret does not grant calendar access until the Google consent step succeeds.',
  links: [['Google web-server OAuth','https://developers.google.com/identity/protocols/oauth2/web-server'],['Calendar API scopes','https://developers.google.com/workspace/calendar/api/auth'],['Events list reference','https://developers.google.com/workspace/calendar/api/v3/reference/events/list']]
 }
};
