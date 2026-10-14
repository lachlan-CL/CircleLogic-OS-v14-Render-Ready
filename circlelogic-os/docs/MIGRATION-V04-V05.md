# v04 to v05 local upgrade

Prefer a new extracted folder and new private test workspace. No customer information or secrets are bundled. The v05 data schema uses the existing v04 tables; no new tenant/record migration is required by this update.

To retain an approved existing local test database, stop the old server and have the authorised operator back up its database and vault key together. Copy only through approved local storage, never through chat. Point v05 DATA_DIR and VAULT_KEY at the correct local material, following the existing key-storage method. Do not mix a database with a different key. Do not overwrite a populated directory without a verified backup. Restart and verify authentication and encrypted connection state before syncing.

Revoke overly broad historic Microsoft consent and reconnect the dedicated calendar-only app. Credential replacement and reauthorisation do not automatically remove provider-side historic grants. Delete temporary exports and protect backups under CircleLogic policy. Do not carry the testing database into production.
