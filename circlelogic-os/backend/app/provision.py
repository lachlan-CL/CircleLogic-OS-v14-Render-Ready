"""Operator-only account provisioning. The published testing password is local-only."""
from __future__ import annotations
import json
import re
import time
from fastapi import HTTPException
from .db import Store, uid
from .security import PASSWORDS


def validate_username(value: str) -> str:
    value=value.strip().lower()
    if not re.fullmatch(r'[a-z0-9][a-z0-9._-]{2,63}',value):
        raise HTTPException(400,'Use 3-64 letters, numbers, dots, underscores or hyphens for the username.')
    return value


def create_workspace(store: Store, *, agency: str, name: str, username: str, email: str,
                     password: str, testing: bool=False) -> dict:
    username=validate_username(username)
    if not testing and (len(password)<12 or username=='testing123'):
        raise ValueError('Customer accounts need a unique username and a password of at least 12 characters. testing123 is reserved for local development.')
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):
        raise ValueError('A valid email address is required.')
    if not agency.strip() or not name.strip():
        raise ValueError('Workspace and account names are required.')
    now=time.time(); tenant=uid(); user=uid()
    hashed=PASSWORDS.hash(password)
    with store.transaction() as db:
        if db.execute('SELECT id FROM users WHERE username=? OR email=?',(username,email.lower())).fetchone():
            raise ValueError('Username or email already exists.')
        db.execute('INSERT INTO tenants VALUES(?,?,?,?)',
                   (tenant,agency.strip(),json.dumps({'demo_enabled':False,'testing':testing}),now))
        db.execute('INSERT INTO users(id,tenant_id,email,name,password_hash,role,created_at,username) VALUES(?,?,?,?,?,?,?,?)',
                   (user,tenant,email.lower(),name.strip(),hashed,'owner',now,username))
    store.audit(tenant,user,'workspace.provisioned','local-testing' if testing else 'operator')
    return {'user_id':user,'workspace_id':tenant,'username':username}


def bootstrap_testing_account(settings, store: Store | None=None) -> bool:
    if settings.environment not in ('development','test'):
        raise RuntimeError('The testing account can only be created in development or automated tests.')
    store=store or Store(settings.database)
    if store.one("SELECT id FROM users WHERE username='testing123'"):
        return False
    create_workspace(store,agency='CircleLogic Testing',name='Testing account',username='testing123',
                     email='testing123@circlelogic.local.invalid',password='testing12345',testing=True)
    return True
