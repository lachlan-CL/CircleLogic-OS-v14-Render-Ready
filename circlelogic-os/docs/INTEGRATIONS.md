# v05 runtime note

Microsoft now uses Manage > Test and sync and includes Connection checks. The access scope and unfinished-provider gates below are unchanged. Use MICROSOFT-FIRST-CONNECTION.md for the current local flow. No provider has been certified with a live account.

# Five requested connections - v04

Verified public routes reviewed 25 September 2026. This is the shipped implementation status, not a promise of approved vendor access.

## Connect Agentbox

**Provider approval required**

Agentbox is now Reapit Sales. Its official integrator application is the verified starting point, not a guessed Settings > API menu.

1. **Confirm the office and owner.** Ask your agency administrator to identify the Agentbox office to connect. Keep Agentbox as the source of truth; the Brain is a read-only companion.
2. **Apply as an integration partner.** CircleLogic should complete the official Reapit Sales integrator application. Third parties are required to go through this application process.
3. **Confirm the approved contract.** Ask Reapit for the supported authentication method, office authorisation, endpoint documentation, allowed fields and rate limits. Do not assume the credentials are a client ID and secret.
4. **Complete the connector first.** This release has no live Agentbox adapter. CircleLogic must implement and test the approved contract before the credential upload is enabled.
5. **Return to API Connections.** Select Agentbox > Add API to see the current status and these instructions. No Agentbox credentials are accepted while the adapter is pending.

No public self-service key-generation sequence was verified. Do not enter your normal Agentbox password into this platform.

[Official integrator application](https://www.agentbox.com.au/integrator-application)

## Connect REA Ignite

**REA Partner Platform**

The implemented connection reads listing-performance reports through the REA Partner Platform. It is not a direct sign-in to Ignite and does not yet import buyer-intent scores.

1. **Apply for Partner Platform access.** CircleLogic, as the integrator, follows the REA onboarding guide: review the terms and submit the linked application. REA support supplies approved Partner Platform credentials.
2. **Arrange agency authorisation.** The agency must authorise the integration. Follow REA's current customer-permissions instructions and request campaign:listing-performance:read. A partner account alone does not authorise every agency.
3. **Prepare the three fields.** Have the partner Client ID, Client secret and the authorised REA Agency ID ready. Confirm them with your approved REA contact. Never use your Ignite account password.
4. **Save in CircleLogic OS.** Open API Connections > REA Ignite > Add API. Enter the three fields, or upload the exact JSON template shown in the secure connection dialog. Select Save credentials.
5. **Test and import.** Select Sync now. Only a completed, validated response marks the source connected. An error preserves any previous snapshot and does not generate substitute data.

Listing performance and buyer intent are different data products. The sample buyer scores in the design preview are illustrative only; no buyer-score availability is claimed.

[Official onboarding](https://partner.realestate.com.au/getting-started/overview/) | [Authentication](https://partner.realestate.com.au/getting-started/authentication/) | [Agency authorisation](https://partner.realestate.com.au/getting-started/authorization/)

## Connect RP Data

**Australian access must be confirmed**

Use Cotality's Australian RP Data team to establish the permitted integration route. A subscription or a US developer account is not proof that this dashboard may access Australian records.

1. **Identify your Australian subscription.** Ask the account administrator for the RP Data plan and the intended office/users. Do not share the login password.
2. **Ask about the appropriate integration route.** Use the contact form on Cotality's Australian RP Data page. Ask whether CircleLogic can be an eligible RP Inside/PropTech integration or needs a separate API agreement.
3. **Confirm permissions and licensing.** Request written confirmation of the allowed Australian datasets, display rights, retention, office/user entitlements, API authentication and limits. Treat ownership matching as unconfirmed until explicitly approved.
4. **Obtain the exact technical contract.** Have Cotality identify the correct regional documentation and credential format. Do not substitute the US MCP client-credentials guide.
5. **Finish the adapter, then connect.** The RP Data adapter is pending. API Connections > RP Data currently opens this access checklist; credential upload and live import are deliberately disabled.

The public RP Data page describes RP Inside connections for eligible CRMs/PropTech platforms. It does not establish that CircleLogic is eligible or supply a verified self-service key-generation flow.

[Australian RP Data and contact form](https://www.cotality.com/au/products/rp-data-real-estate)

## Connect Proping

**Integration route not yet verified**

This uses Proping (proping.com.au), the daily property-alert service. Confirm it is the service called "Propping" in your agency materials before implementing a connector.

1. **Confirm the service.** Ask the office administrator to confirm the vendor and the alert email account. The public Proping product describes daily email reports.
2. **Contact Proping.** Use the official contact page to ask whether an API, licensed export or authorised email-ingestion route is available for your account.
3. **Get written approval and documentation.** Ask for the permitted data, authentication format, limits and retention rules. A reply offering an API is needed before designing a credential form; do not assume an API key exists.
4. **Review email access separately.** An email-based alternative would need separate permissions, privacy controls and parsing tests. The calendar integration in this build cannot read your inbox.
5. **Return after the connector is approved.** Proping > Add API currently shows this checklist. No invented API endpoint, guessed credential field or automatic email ingestion is enabled.

Public self-service API documentation was not located. That is not proof that a private integration is unavailable; it needs confirmation from Proping.

[Product and email-alert description](https://www.proping.com.au/) | [Official contact page](https://www.proping.com.au/contact)

## Connect your diary / calendar

**Microsoft 365 - read-only**

This release supports Microsoft 365, not Google Calendar. Your Microsoft calendar is private to your CircleLogic login; other workspace users do not inherit access.

1. **Have your administrator register an application.** In the Microsoft Entra admin center, open Entra ID > App registrations > New registration. Choose a descriptive name and the account type approved by your administrator. For a single-organisation pilot, use that organisation's tenant.
2. **Configure the exact redirect address.** In CircleLogic, open API Connections > Diary / Calendar > Add API and copy the Redirect URI. Add that exact address as a Web redirect in the Microsoft app registration. Use HTTPS on an approved deployed host; localhost is development-only.
3. **Record the application and directory IDs.** From the registration Overview, copy Application (client) ID and Directory (tenant) ID into the matching CircleLogic fields.
4. **Create the application credential.** Open Certificates & secrets > Client secrets > New client secret. Set an approved expiry and copy the secret VALUE immediately, not its Secret ID. This pilot uses a client secret; certificate/federated-credential support would need an adapter change for a hardened deployment.
5. **Set least-privilege delegated access.** Add the Microsoft Graph delegated Calendars.ReadBasic permission. The sign-in flow also requests offline_access for refresh tokens. Do not grant Mail.Read, Calendars.ReadWrite or application-wide mailbox access. Obtain administrator consent when your tenant requires it.
6. **Save, authorise and sync.** In CircleLogic, enter Directory ID, Client ID and secret value, or use the supplied JSON template. Save, select Authorise Microsoft, sign in to the correct account and consent. After returning, select Sync now to import the next 30 days.

Saving a secret does not grant access. The Microsoft consent redirect and a successful sync are separate steps. Disconnecting here erases local credentials/data; revoke the app in Microsoft as well when retiring access.

[Register an application](https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app) | [Add credentials](https://learn.microsoft.com/en-us/entra/identity-platform/how-to-add-credentials) | [Calendar permissions and API](https://learn.microsoft.com/en-us/graph/api/calendar-list-calendarview?view=graph-rest-1.0)

## Report semantics

REA metrics select only realestate_au / all / listingEvents / period=all. pageView maps to page_views, emailEnquiry to email_enquiries, and listingSaved to saves. Missing values remain null; daily and total values are never added together. These are report-period event counts, not unique people or intent scores. Official contract: https://partner.realestate.com.au/campaign/listing-performance/usage/

Calendar imports cover the next 30 days. The UI uses Australia/Sydney display time and a 7/30-day filter. No mailbox reads or calendar writes are performed.

## Next build gate

For each pending adapter, obtain the exact approved authentication and endpoint contract, agency/user entitlement, sample success/empty/error payloads, pagination, rate limits, data mapping and retention rules. Add atomic sync and cross-tenant tests before changing implemented=false or accepting credentials. This release has no endpoint for uploading an invented normalized file as though it came from a provider.
