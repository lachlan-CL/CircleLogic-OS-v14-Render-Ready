"""Single-node pilot store. Every business query is explicitly tenant scoped."""
from contextlib import contextmanager
import sqlite3
import time
import uuid

SCHEMA = '''
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS schema_version(version INTEGER PRIMARY KEY);
INSERT OR IGNORE INTO schema_version VALUES(1);
CREATE TABLE IF NOT EXISTS tenants(
 id TEXT PRIMARY KEY, name TEXT NOT NULL, settings TEXT NOT NULL DEFAULT '{}', created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS users(
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id), email TEXT NOT NULL UNIQUE,
 name TEXT NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL,
 totp_secret TEXT, mfa_enabled INTEGER NOT NULL DEFAULT 0, last_totp_counter INTEGER NOT NULL DEFAULT -1,
 active INTEGER NOT NULL DEFAULT 1, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS recovery_codes(
 user_id TEXT NOT NULL REFERENCES users(id), code_hash TEXT NOT NULL, PRIMARY KEY(user_id, code_hash)
);
CREATE TABLE IF NOT EXISTS sessions(
 token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), stage TEXT NOT NULL,
 csrf TEXT NOT NULL, expires_at REAL NOT NULL, mfa_at REAL NOT NULL DEFAULT 0, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS rate_limits(
 bucket TEXT PRIMARY KEY, count INTEGER NOT NULL, expires_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS invitations(
 token_hash TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id), email TEXT NOT NULL,
 role TEXT NOT NULL, expires_at REAL NOT NULL, created_by TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS connections(
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id), provider TEXT NOT NULL,
 owner_id TEXT NOT NULL DEFAULT '', credentials TEXT, status TEXT NOT NULL DEFAULT 'configured',
 last_success REAL, error TEXT, revision INTEGER NOT NULL DEFAULT 1,
 lease_until REAL NOT NULL DEFAULT 0, lease_token TEXT,
 UNIQUE(tenant_id, provider, owner_id)
);
-- v06: staged non-secret provider IDs. Kept apart from active credentials;
-- editing setup never silently switches an existing connection to another app.
CREATE TABLE IF NOT EXISTS connection_setups(
 tenant_id TEXT NOT NULL REFERENCES tenants(id), provider TEXT NOT NULL,
 owner_id TEXT NOT NULL DEFAULT '', payload TEXT NOT NULL, updated_at REAL NOT NULL,
 PRIMARY KEY(tenant_id, provider, owner_id)
);
CREATE TABLE IF NOT EXISTS snapshots(
 connection_id TEXT NOT NULL REFERENCES connections(id) ON DELETE CASCADE,
 kind TEXT NOT NULL, synced_at REAL NOT NULL, PRIMARY KEY(connection_id, kind)
);
CREATE TABLE IF NOT EXISTS records(
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id), connection_id TEXT REFERENCES connections(id) ON DELETE CASCADE,
 provider TEXT NOT NULL, owner_id TEXT NOT NULL DEFAULT '', kind TEXT NOT NULL, external_id TEXT NOT NULL,
 payload TEXT NOT NULL, updated_at REAL NOT NULL,
 UNIQUE(tenant_id, provider, owner_id, kind, external_id)
);
CREATE INDEX IF NOT EXISTS records_scope ON records(tenant_id, kind, provider, owner_id);
CREATE TABLE IF NOT EXISTS oauth_states(
 state_hash TEXT PRIMARY KEY, session_hash TEXT NOT NULL, connection_id TEXT NOT NULL REFERENCES connections(id) ON DELETE CASCADE,
 tenant_id TEXT NOT NULL, user_id TEXT NOT NULL, provider TEXT NOT NULL, verifier TEXT NOT NULL,
 revision INTEGER NOT NULL, expires_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS audit(
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id), user_id TEXT NOT NULL,
 action TEXT NOT NULL, detail TEXT NOT NULL, created_at REAL NOT NULL
);
'''

class Store:
    def __init__(self, path):
        self.path = str(path)
        with self.connect() as db:
            db.executescript(SCHEMA)
            # Additive v03 migration: preserve v02 users, MFA, sessions, records
            # and pending invitation tokens. IDs are public handles, not tokens.
            db.execute('BEGIN IMMEDIATE')
            try:
                columns={r['name'] for r in db.execute('PRAGMA table_info(invitations)')}
                for column, definition in [('id', 'TEXT'), ('name', "TEXT NOT NULL DEFAULT ''"),
                                           ('created_at', 'REAL NOT NULL DEFAULT 0')]:
                    if column not in columns:
                        db.execute(f'ALTER TABLE invitations ADD COLUMN {column} {definition}')
                for row in db.execute('SELECT token_hash FROM invitations WHERE id IS NULL').fetchall():
                    db.execute('UPDATE invitations SET id=? WHERE token_hash=?',(uid(),row['token_hash']))
                db.execute('CREATE UNIQUE INDEX IF NOT EXISTS invitations_id ON invitations(id)')
                db.execute('INSERT OR IGNORE INTO schema_version VALUES(3)')
                # v04 adds optional unique usernames. Existing email logins remain valid.
                user_columns={r['name'] for r in db.execute('PRAGMA table_info(users)')}
                if 'username' not in user_columns:
                    db.execute('ALTER TABLE users ADD COLUMN username TEXT')
                db.execute('CREATE UNIQUE INDEX IF NOT EXISTS users_username ON users(username) WHERE username IS NOT NULL')
                # Do not silently seed customer dashboards after upgrading.
                if not db.execute('SELECT version FROM schema_version WHERE version=4').fetchone():
                    import json
                    for tenant in db.execute('SELECT id,settings FROM tenants').fetchall():
                        values=json.loads(tenant['settings'])
                        values['demo_enabled']=False
                        db.execute('UPDATE tenants SET settings=? WHERE id=?',(json.dumps(values),tenant['id']))
                    db.execute('INSERT INTO schema_version VALUES(4)')
                db.execute('INSERT OR IGNORE INTO schema_version VALUES(6)')
                db.commit()
            except BaseException:
                db.rollback()
                raise

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA busy_timeout=15000')
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def transaction(self):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    def one(self, sql, args=()):
        with self.connect() as db:
            r = db.execute(sql, args).fetchone()
            return dict(r) if r else None

    def all(self, sql, args=()):
        with self.connect() as db:
            return [dict(r) for r in db.execute(sql, args).fetchall()]

    def execute(self, sql, args=()):
        with self.transaction() as db:
            return db.execute(sql, args).rowcount

    def audit(self, tenant, user, action, detail=''):
        # Only identifiers and fixed messages. Never log raw provider responses or secrets.
        self.execute('INSERT INTO audit VALUES(?,?,?,?,?,?)',
                     (uid(), tenant, user, action, detail[:500], time.time()))

def uid():
    return str(uuid.uuid4())
