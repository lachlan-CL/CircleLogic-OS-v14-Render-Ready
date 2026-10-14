# CircleLogic OS v13 – connector permission fix and provider logos

## Fixed
- API Connections now returns the `manageable` permission flag for every visible connector.
- The frontend only blocks a connection when `manageable === false`, so missing metadata can no longer incorrectly trigger the workspace-access warning.
- The access warning no longer mentions private calendars for unrelated integrations.
- Verified that an owner account can open and save a connection for broader catalogue entries such as PropertyMe.

## Logos
- Connector cards now request each provider's current site/app favicon using the provider's own domain.
- If a remote logo cannot load, the existing bundled local connector asset is used automatically as a fallback.
- The logo treatment is applied consistently across the unified API catalogue and any other place that uses the provider icon component.

## Preserved
- Google Calendar OAuth and calendar sync behaviour is unchanged.
- Existing stored connections, workspace data, `.env`, database files and credential vault files are not replaced by the update package.
