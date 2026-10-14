# Upgrade v05 to v06

Stop the server and make a private backup of the existing installation. Apply the supplied update to the existing `circlelogic-os` folder; do not create a new empty installation and discard the old database. Restart with START-CIRCLELOGIC.cmd and hard-refresh the browser. No new dependencies are needed.

The updater verifies original v05 hashes (or already-applied v06 hashes) before changing files. It refuses locally modified files instead of overwriting them. Changed source is backed up under `.circlelogic-update-backups`. It never touches `.env`, `.venv`, data/, the database, the vault key, or account records. Startup adds the connection_setups table with CREATE TABLE IF NOT EXISTS. Existing connections reuse their stored non-secret identifiers automatically.

The update is local source replacement only. A deployed installation needs its approved redeployment procedure; a local ZIP cannot change a hosted service. Do not upload databases, vault keys or secrets with the source ZIP.
