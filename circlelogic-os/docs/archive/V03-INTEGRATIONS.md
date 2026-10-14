# Integration setup and verified scope

Reviewed against public primary-source documentation on 25 September 2026. These are implementation notes, not vendor certification. Public documentation may change; obtain each agency's approved access and exercise its sandbox before a client release.

**Status vocabulary:** implemented means adapter code exists and the supplied mock-contract tests pass. It does not mean an agency account was connected here. Gated means the adapter has not been implemented; the UI will not collect secrets or pretend an API key enables it.

## Connection matrix

| Provider | This build reads | Input fields / flow | Status |
| --- | --- | --- | --- |
| Rex | Contacts; published CRM listings | `email`, `password`, `account_id`; API login token | Implemented, mock-tested |
| VaultRE | Contacts; available residential sale listings | `api_key`, `access_token` | Implemented, mock-tested |
| Domain | Live public agency listing catalogue | `client_id`, `client_secret`, `agency_id`; client-credentials grant | Implemented, mock-tested |
| REA / realestate.com.au | Agency listing-performance reports | `client_id`, `client_secret`, `agency_id`; client-credentials grant and agency delegation | Implemented, mock-tested |
| Microsoft 365 | Next 30 days' calendar; last 30 days' inbox metadata | `client_id`, `client_secret`, `directory_id`; user OAuth consent | Implemented, mock-tested; private per user |
| Xero | Invoice summaries and amounts due | `client_id`, `client_secret`, `tenant_id`; user OAuth consent | Implemented, mock-tested |
| DocuSign | Last 90 days' envelope status | `client_id`, `client_secret`, `account_id`, `environment`; user OAuth consent | Implemented, mock-tested |
| PropertyMe | Intended rental/lease module | Complete endpoint contract and approved access still needed | Not implemented |
| Reapit Sales / Agentbox | Intended alternative CRM | Integrator application, approved contract and adapter development needed | Not implemented |
| MRI Property Tree | Intended alternative rental module | Signed-in partner documentation, approved access and adapter development needed | Not implemented |

## Common setup sequence

The provider API is a service contract, not a file to upload. A credential JSON file is only a convenient way to fill the configuration form. It does not supply missing endpoint mappings, licensing, scopes, account approval or vendor consent.

Use an owner/admin account for shared services. Any permitted member can configure their own private Microsoft connection. Reverify in **Security** if the last two-factor check is more than ten minutes old. Enter the complete set of fields on every credential replacement; existing secret values are never read back into the browser.

A JSON example for Domain is:

```json
{
  "client_id": "YOUR_PROVIDER_CLIENT_ID",
  "client_secret": "YOUR_PROVIDER_CLIENT_SECRET",
  "agency_id": "YOUR_DOMAIN_AGENCY_ID"
}
```

All values must be strings. Unknown fields are rejected. The form's JSON loader accepts at most 32 KB. A missing or wrong credential must not be worked around by changing the provider URL: the adapter uses a fixed, reviewed host.

For OAuth providers, register these exact redirect patterns, substituting the actual approved HTTPS origin:

```text
https://YOUR-APP-DOMAIN/api/oauth/microsoft/callback
https://YOUR-APP-DOMAIN/api/oauth/xero/callback
https://YOUR-APP-DOMAIN/api/oauth/docusign/callback
```

For localhost development, a provider must explicitly allow the displayed `http://localhost:8000/...` redirect. Do not assume every provider accepts HTTP or localhost. Use the approved HTTPS test deployment where required. Authorisation is initiated in the same signed-in browser; state is tied to that user/session/connection and expires after ten minutes. Reconfiguration invalidates pending states.

After provider consent, click **Sync now**. The callback stores the token but deliberately does not claim data was imported. Only a complete successful sync sets the connection to connected. The optional worker later refreshes connections already authorised/connected or needing retry; it does not obtain partner approval or user consent.

## Rex

Use a dedicated agency-authorised integration user with access limited to the required data. The `account_id` must be numeric. This adapter performs `Authentication/login`, then paginated `Contacts/search` and `PublishedListings/search` under the Rex v1 API. The selected account and its permitted record set must be checked in the live pilot.

The current normalisation uses the documented common contact/listing fields. Additional account-specific custom fields, related contact methods, draft listings, archived data, appraisals and deals require mapping extensions. A successful published-listing count is not a count of every pipeline record. There is no CRM write-back.

Primary references: [Authentication](https://api-docs.rexsoftware.com/article/authentication), [Rex API documentation](https://api-docs.rexsoftware.com/).

## VaultRE

A registered integrator receives its API key; the agency grants an access token with selected scopes. This implementation sends both the `X-Api-Key` header and the agency bearer token. Obtain permissions for contacts and the required residential-sale collection. Confirm the account's permitted fields and pagination shape against its approved API contract; the current adapter expects `items` collections and pages until an empty page or explicit total-page boundary.

The public guide documents the v1.3 API base, caching guidance and quotas. This pilot retries limited rate-limit responses but has no cross-tenant distributed quota scheduler. A shared integrator key serving multiple agencies needs a reviewed aggregate budget before enabling broad polling. No property photos are hotlinked or downloaded by this build.

Primary references: [Technical guide and authentication](https://docs.api.vaultre.com.au/guide.html), [Swagger reference](https://docs.api.vaultre.com.au/swagger/index.html).

## Domain

Register an approved developer application and use client credentials with `api_listings_read`. The adapter obtains a token from `https://auth.domain.com.au/v1/connect/token`, then pages through `/v1/agencies/{agency_id}/listings` with the live listing filter. Where an advertiser ID is supplied, it is checked against the configured agency.

This is a **public agency listing catalogue**, not private lead/enquiry data, vendor reporting or listing publication. Private Domain capabilities may need a different user-authorised grant and scopes and are not implemented here. Results appear under **Portal listings** so they do not overwrite the authoritative CRM.

Primary references: [Client credentials grant](https://developer.domain.com.au/docs/latest/authentication/oauth/client-credentials-grant/), [Domain API reference](https://developer.domain.com.au/docs/latest/apis/pkg_agents_listings/references/agencies_getlistings/).

## REA / realestate.com.au

First obtain Partner Platform access for the product, including the listing-performance capability and the relevant agency's delegation. The adapter requests a client-credentials token and reads `/campaign/v1/listing-performance?agency_id=...`, following its HAL pagination. The public capability documentation identifies the campaign listing-performance read scope.

Records retain their supplied report metrics; the application does not invent a formula to reinterpret missing metrics as enquiries, leads or advertising ROI. No REA publishing, XML ingestion, portal enquiry intake or ad spend ordering is implemented.

Primary references: [Partner onboarding](https://partner.realestate.com.au/getting-started/overview/), [Partner Platform documentation](https://partner.realestate.com.au/).

## Microsoft 365

Register a confidential web application in the approved Microsoft Entra directory. Configure the redirect URI and delegated permissions used here: `User.Read`, `Calendars.ReadBasic`, `Mail.ReadBasic`, plus `offline_access`. The implementation uses authorisation code with PKCE and a backend-held client secret. Tenant policy may require administrator consent.

The app requests basic calendar entries from `/me/calendar/calendarView` for the next 30 days and inbox metadata for the last 30 days. It selects subjects, sender metadata, times and basic event location; no mail bodies, attachments, mailbox search, sending, shared calendars or shared mailboxes are fetched. Imported data stays private to the connecting login, including against other application admins through the API.

The current configuration stores app credentials separately for each connecting user. Centralised operator-managed Microsoft application registration is a future onboarding improvement, not an implemented shared-secret admin portal.

Primary references: [Authorisation code and PKCE](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow), [Calendar view](https://learn.microsoft.com/en-us/graph/api/calendar-list-calendarview?view=graph-rest-1.0), [Mail folder messages](https://learn.microsoft.com/en-us/graph/api/mailfolder-list-messages?view=graph-rest-1.0).

## Xero

Register a confidential web app, configure the callback, and authorise the intended organisation. Obtain its tenant ID from the authorised connection metadata; this pilot expects the operator to supply it rather than offering an organisation-picker UI. Before downloading invoices, the adapter checks `/connections` includes the configured organisation, then uses the `Xero-tenant-id` header.

This version requests `offline_access accounting.transactions.read`. Xero is migrating to granular scopes; the documentation reviewed during this build states broad accounting scopes continue to be supported until September 2027. Review the current invoice-read scope requirements before launch and update the adapter's scope constant and tests as necessary; do not assume this compatibility setting is permanent. The confidential standard code flow uses the client secret; refresh tokens are saved before subsequent invoice fetches.

Only invoice summaries are imported. An invoice amount due is not commission earned. Payroll, bank transactions, trust accounting, journals, payments and reconciliations are not implemented. Non-AUD totals are not converted into the AUD metric.

Primary references: [Standard auth flow](https://developer.xero.com/documentation/guides/oauth2/auth-flow/), [Scopes](https://developer.xero.com/documentation/guides/oauth2/scopes/), [Invoices](https://developer.xero.com/documentation/api/accounting/invoices/).

## DocuSign

Begin with an approved developer/demo application and a registered callback. `environment` must be exactly `demo` or `production`. Supply the integration key, client secret and API account ID. The implemented code flow requests `signature extended`, uses PKCE and stores tokens on the backend. Production use requires the provider's go-live process.

The adapter calls OAuth userinfo, verifies the configured account, and accepts only an HTTPS DocuSign API host returned for that account. It reads envelope metadata changed since the last 90 days, including status and subject. This scope is not equivalent to all historical agreements. No envelope creation, signing, sending or document content retrieval is implemented.

Primary references: [OAuth reference](https://developers.docusign.com/platform/auth/reference/), [Envelope listStatusChanges](https://developers.docusign.com/docs/esign-rest-api/reference/envelopes/envelopes/liststatuschanges/).

## Gated property-management and alternative CRM adapters

**PropertyMe:** the public Swagger interface and API resource index were located, but a complete endpoint/schema contract was not accessible during this build. That does not establish that PropertyMe has no API. Obtain approved access and the full lease/property/arrears contract, implement normalisation, validate permissions/pagination and add live sandbox tests. Reference: [Public API entry point](https://app.propertyme.com/api/swagger-ui/).

**Reapit Sales / Agentbox:** the official page requires a reviewed integrator application. The private API contract was not supplied. Complete approval, obtain the approved endpoints and implement the adapter rather than guessing them. Reference: [Integrator application](https://www.agentbox.com.au/integrator-application).

**MRI Property Tree:** the API portal redirected to sign-in. Obtain authorised documentation and access, then implement and test the adapter. Reference: [Developer portal](https://developer.propertytree.io/apis).

Until these are completed, rental data is explicitly synthetic or unavailable. Saving a key is not a substitute for the missing implementation.

## Acceptance test for each live connection

Record the approved provider/account/tenant, scopes, licence permissions and expected record population. Sync a controlled sample. Compare source IDs, pagination totals, selected field values, null handling, time zones and financial currencies with the provider UI. Test real expired/revoked tokens, account mismatch, rate limits, zero results, partial failures and disconnect during sync. Sign off data accuracy and access boundaries before switching off sample data for a client.
