# Migrate v06 to v07

Use `CircleLogic-OS-v07-Update.zip` rather than replacing your existing installation by hand.

The updater changes application code/docs only. It preserves `.env`, `.venv`, `data/`, your database and the vault key. It accepts either the original v06 launcher or the separately supplied v06 startup-fixed launcher and replaces it with the v07 version-aware launcher.

No existing Microsoft or REA credentials are altered. The new Google connection begins disconnected for every user until its own setup, secret and OAuth consent are completed.
