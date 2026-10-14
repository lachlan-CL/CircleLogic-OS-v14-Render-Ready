from dataclasses import dataclass
from pathlib import Path
import os
from urllib.parse import urlparse
from cryptography.fernet import Fernet

@dataclass(frozen=True)
class Settings:
    data_dir: Path
    public_origin: str
    environment: str
    vault_key: str
    allow_signup: bool
    provision_token: str
    session_hours: int = 8

    @property
    def secure(self) -> bool:
        return self.public_origin.startswith('https://')

    @property
    def database(self) -> Path:
        return self.data_dir / 'agency.sqlite3'

    @classmethod
    def load(cls):
        root = Path(os.getenv('DATA_DIR', './data')).resolve()
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        env = os.getenv('APP_ENV', 'development')
        origin = os.getenv('PUBLIC_ORIGIN', 'http://localhost:8000').rstrip('/')
        parsed = urlparse(origin)
        if (env not in ('development','test','production') or parsed.scheme not in ('http','https')
                or not parsed.hostname or parsed.username or parsed.password
                or parsed.path or parsed.query or parsed.fragment):
            raise RuntimeError('Use a valid APP_ENV and a PUBLIC_ORIGIN containing only scheme, hostname and optional port.')
        if parsed.scheme == 'http' and parsed.hostname not in ('localhost','127.0.0.1','::1'):
            raise RuntimeError('Unencrypted HTTP is permitted only on loopback. Use approved HTTPS hosting for remote access.')
        key = os.getenv('VAULT_KEY', '')
        if env == 'production':
            if not origin.startswith('https://') or not key:
                raise RuntimeError('Production requires HTTPS PUBLIC_ORIGIN and VAULT_KEY.')
            if os.getenv('ALLOW_SIGNUP', 'false').lower() == 'true':
                raise RuntimeError('Public workspace signup must be disabled in production.')
        if not key:
            p = root / '.vault-key'
            if not p.exists():
                # Local development only. Never package or commit this file.
                fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, 'wb') as f:
                    f.write(Fernet.generate_key())
            key = p.read_text().strip()
        Fernet(key.encode())  # Validate early.
        return cls(root, origin, env, key,
                   os.getenv('ALLOW_SIGNUP', 'false').lower() == 'true',
                   os.getenv('PROVISION_TOKEN', ''))
