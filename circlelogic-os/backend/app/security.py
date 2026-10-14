"""Argon2 passwords, opaque sessions, context-bound Fernet secrets, RFC 6238 OTP."""
import base64
import hashlib
import hmac
import json
import secrets
import struct
import time
from urllib.parse import quote
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from cryptography.fernet import Fernet
from fastapi import HTTPException

PASSWORDS = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
DUMMY_HASH = PASSWORDS.hash(secrets.token_urlsafe(30))

ROLES = {
 'owner': {'dashboard','contacts','listings','rentals','transactions','campaigns','portal_listings','invoices','documents','tasks','calendar','messages','reports','integrations','team','settings','audit'},
 'admin': {'dashboard','contacts','listings','rentals','transactions','campaigns','portal_listings','invoices','documents','tasks','calendar','messages','reports','integrations','team','settings','audit'},
 'agent': {'dashboard','contacts','listings','transactions','campaigns','portal_listings','documents','tasks','calendar','messages','integrations'},
 'property_manager': {'dashboard','rentals','documents','tasks','calendar','messages','integrations'},
 'finance': {'dashboard','invoices','transactions','documents','tasks','calendar','messages','reports','integrations'},
 'viewer': {'dashboard','listings','portal_listings'},
}

def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()

def token():
    return secrets.token_urlsafe(32)

def verify_password(encoded, password):
    try:
        return PASSWORDS.verify(encoded or DUMMY_HASH, password)
    except (VerificationError, InvalidHashError):
        return False

class Vault:
    def __init__(self, key):
        self.fernet = Fernet(key.encode())
    def seal(self, context, data):
        return self.fernet.encrypt(json.dumps({'context':context, 'data':data}).encode()).decode()
    def open(self, context, encrypted):
        obj = json.loads(self.fernet.decrypt(encrypted.encode()))
        if not hmac.compare_digest(obj['context'], context):
            raise ValueError('Secret context mismatch')
        return obj['data']

def new_totp_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip('=')

def otp(secret: str, counter: int, digits: int=6) -> str:
    key = base64.b32decode(secret + '=' * ((8-len(secret)%8)%8))
    mac = hmac.new(key, struct.pack('>Q', counter), hashlib.sha1).digest()
    offset = mac[-1] & 0x0f
    number = struct.unpack('>I', mac[offset:offset+4])[0] & 0x7fffffff
    return str(number % (10**digits)).zfill(digits)

def totp_counter(secret, code, last_counter=-1, now=None):
    now = time.time() if now is None else now
    if not isinstance(code, str) or not code.isdigit() or len(code) != 6:
        return None
    counter = int(now // 30)
    for c in (counter, counter-1, counter+1):
        if c >= 0 and c > last_counter and hmac.compare_digest(otp(secret,c), code):
            return c
    return None

def provisioning_uri(secret, email):
    return f'otpauth://totp/{quote("CircleLogic OS:"+email,safe="")}?secret={secret}&issuer=CircleLogic%20OS&algorithm=SHA1&digits=6&period=30'

def check_rate(store, key, limit, window=900):
    now = time.time()
    with store.transaction() as db:
        row = db.execute('SELECT * FROM rate_limits WHERE bucket=?',(key,)).fetchone()
        if row and row['expires_at'] > now:
            if row['count'] >= limit:
                raise HTTPException(429, 'Too many attempts. Please wait before trying again.', headers={'Retry-After':str(int(row['expires_at']-now)+1)})
            db.execute('UPDATE rate_limits SET count=count+1 WHERE bucket=?',(key,))
        else:
            db.execute('INSERT OR REPLACE INTO rate_limits VALUES(?,?,?)',(key,1,now+window))
        db.execute('DELETE FROM rate_limits WHERE expires_at<?',(now-3600,))
