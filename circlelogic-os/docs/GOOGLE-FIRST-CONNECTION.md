# Google Calendar - first live connection checklist

Use an approved test Google account and fabricated calendar events only.

1. Start CircleLogic OS and sign into a private workspace with 2FA.
2. Open **API Connections > Google Calendar > Setup guide**.
3. In Google Cloud / Google Auth Platform:
   - enable Google Calendar API;
   - configure OAuth consent/testing;
   - create an OAuth client ID of type **Web application**;
   - add the exact CircleLogic Google redirect URI shown in the guide.
4. Save the Google OAuth client ID in CircleLogic One-time connection setup.
5. Paste the matching OAuth client secret in the single key field and select **Save key**.
6. Select **Authorise Google Calendar** and choose the intended account.
7. Confirm the consent screen is asking for read-only calendar-event access.
8. Return to CircleLogic and select **Test and sync**.
9. Create `TEST - CircleLogic Google inspection` tomorrow in the primary calendar. Sync and compare title/time/location.
10. Edit the event; sync; confirm it updates without duplication.
11. Delete the event; sync; confirm it disappears.
12. Run another sync without changes to verify no duplicate records appear.
13. Disconnect Google Calendar and confirm its imported calendar data disappears.

Official references:
- OAuth web server flow: https://developers.google.com/identity/protocols/oauth2/web-server
- Calendar API authorisation/scopes: https://developers.google.com/workspace/calendar/api/auth
- Events list endpoint: https://developers.google.com/workspace/calendar/api/v3/reference/events/list

The connector is read-only and requests `https://www.googleapis.com/auth/calendar.events.readonly`.
