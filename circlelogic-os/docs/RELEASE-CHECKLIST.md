# Live pilot acceptance - NOT YET COMPLETED

Use approved test accounts and record the date, operator, build version, expected and actual result. Do not record secrets, QR codes or real customer details in evidence.

| Check | Expected result | Live result |
| --- | --- | --- |
| Fresh install on intended computer | Dependencies install; launcher serves app | Not run |
| Private login and MFA | Correct workspace; no access before MFA | Not run on target computer |
| Microsoft registration and browser consent | Correct mailbox; exact callback; no unintended scopes | Not run |
| Known appointment | Correct title, time, location | Not run |
| Update, delete, repeated sync | Updated once; deleted disappears; no duplicates | Not run |
| All-day/recurring/time-zone events | Correct intended display | Not run with Microsoft |
| Expired access/revoked consent | Refresh or clear reauthorisation; no false live status | Not run with Microsoft |
| Empty calendar | Successful empty result; no inserted samples | Not run with Microsoft |
| Different login/workspace | No access to another user's calendar or credentials | Synthetic tests passed; live review pending |
| REA agency/report-period match | Correct authorised agency and metric definitions | Not run |
| Host/security/backup review | Review and restore drill complete | Not run |
| Three gated connectors | Approved contract, implemented adapter and live acceptance | Not implemented |

A successful local request is not independent security approval. A green connection status is not proof that the selected account and business metric are correct. Do not publish until the required checks are signed off.
