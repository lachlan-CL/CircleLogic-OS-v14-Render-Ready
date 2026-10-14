# Architecture and product boundaries

## Frontend versus backend

The **frontend** is the interface a client sees: navigation, metrics, tables, forms, search and configuration screens. It cannot be trusted to enforce access because a user can modify browser code.

The **backend** is the server-side application: it validates sessions and roles, identifies the tenant, stores encrypted credentials, talks to providers and returns only the permitted data. No provider secrets are sent back to the browser after they are saved. The browser necessarily holds newly entered credentials temporarily while submitting the configuration form; they are not saved to browser local storage.

```text
Browser frontend (no provider secrets embedded)
          |
          | same-origin /api, cookie session, CSRF header
          v
HTTPS frontend/reverse proxy
          |
          v
FastAPI backend  <-------- Optional polling worker
   |         |
   |         +---- Fixed-host provider APIs / OAuth
   |
   +---- SQLite: tenants, users, sessions, encrypted secrets,
                connections, snapshots, canonical records, audit
```

The local launcher serves both source directories from one origin for ease of testing. The deployment template separates the static frontend and API into different containers while keeping one public origin, avoiding permissive CORS. It is not two independently deployed public domains.

## Identity and isolation

An agency is a tenant row. A login belongs to one tenant and one role. Every protected business operation derives the tenant from the authenticated server session, not a request body, URL parameter or browser-selected agency ID. Microsoft connections and records have an additional user-owner scope; shared sources use an empty owner scope.

This provides logical tenancy through application-level predicates. SQLite does not provide database-enforced row-level security here. A defect in a future query or a compromised operator with the database and vault key remains a threat. For more demanding deployments, migrate to a reviewed managed database with defence-in-depth policies, or use dedicated deployment/database instances per client.

## Canonical data and source authority

Each adapter produces a dict of complete module arrays: `contacts`, `listings`, `portal_listings`, `campaigns`, `invoices`, `documents`, `calendar` and/or `messages`. Each record must include a stable provider `external_id`. Unknown schema, duplicate or missing IDs, failed pages and incomplete module sets reject the entire import. No partial dataset is advertised as complete.

One selected source controls each module. The UI selects one sales CRM for contacts/listings and a future property-management source. The Domain catalogue is kept separate from the CRM and REA supplies a separate campaign-report module. No cross-provider contact deduplication, conflict resolution or bidirectional record editing is implemented.

A sync lease stops overlapping imports. A connection revision prevents an in-flight sync or OAuth callback from resurrecting credentials/data after reconfiguration or disconnection. Rotated OAuth refresh tokens are saved before subsequent record requests. Imported rows and module snapshots are replaced atomically after validation.

## State model

| State | Meaning |
| --- | --- |
| Sample data | No successful live snapshot for this module; examples are explicitly enabled. |
| Live snapshot | A complete successful import less than one hour old; not a real-time stream. |
| Stale snapshot | Last successful import is old, failed to refresh, or credentials were reconfigured. |
| Disconnected | Previously imported local data/credentials were deleted; no sample fallback hides that fact. |
| Workspace data | Tasks created directly in this tenant, not copied to another provider. |
| Not connected | No usable data and samples are disabled. |
| Mixed sources | At least one visible module is synthetic and another is not. Do not interpret the whole page as live. |

A zero-row success is still a live snapshot. Sample records never enter the live records table. Local tasks replace the example task list; the examples are not silently turned into real work.

## Metrics and financial meaning

The screenshot-inspired gross commission and growth rates are illustrative sample values. Once real Xero invoices are selected, the financial card changes to **Unpaid invoices (AUD)**: AUD receivable invoice amounts due, excluding voided/deleted records. Non-AUD invoices remain visible but are not converted or silently added to that total. It is neither recognised revenue nor gross commission nor a trust balance.

The real CRM count is **CRM contacts**, not automatically new leads this month. Imported listing counts reflect the connector's documented collection, not a guarantee of all stages in an agency's pipeline. Calendar, mailbox and DocuSign collections have explicit time windows. Historical commission charts remain unavailable outside a completely synthetic dashboard until a separately verified mapping exists.

## Scope deliberately not implied

No LLM, external tool-running AI agent, email sending, SMS, listing publication, financial transaction, signing workflow creation, bank/trust reconciliation, live settlement mapping, webhook receiver or property-management adapter exists in this release. The app aggregates read-only approved sources and manages its own local task list. Provider applications, licences, consents, approved scopes, partner agreements and live validation remain prerequisites.
