# CircleLogic OS v12 – UI refinement and unified connector catalogue

## What changed
- Refined the executive snapshot cards so the headline metrics render more cleanly and consistently.
- Added a warmer colour treatment across the summary cards and dashboard panels.
- Rebuilt the integrations page into a single unified connector catalogue instead of splitting “core” and “other” connectors.
- Removed “showcase” / “real setup guide” language from the visible UI.
- Added logo assets for each connector card so every listed API has a visual identity.
- Enabled connection flows for the broader connector catalogue by allowing credentials to be saved and managed for each API.
- Preserved live Google Calendar behaviour while making the wider catalogue connection-ready for future workflow use.

## Main files changed
- `frontend/src/app.js`
- `frontend/src/styles.css`
- `backend/app/catalog.py`
- `backend/app/main.py`
- `preview/runtime.js`
- `frontend/assets/logo-*.svg`
