from __future__ import annotations
import base64
import csv
import hmac
import io
import json
from pathlib import Path
import re
import time
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from .pilot import VERSION, readiness, diagnostics
from pydantic import BaseModel, ConfigDict, Field
import qrcode

from .config import Settings
from .db import Store, uid
from .security import (ROLES, PASSWORDS, Vault, check_rate, digest, new_totp_secret,
                       provisioning_uri, token, totp_counter, verify_password)
from .catalog import CATALOG, DEFAULT_SOURCES, BRAIN_PROVIDERS
from .connectors import ConnectorError, Engine, auth_url
from .services import conn_context, dataset, perform_sync, settings_for
from .brain import brain_dashboard, connection_status
from .provision import validate_username
from .connection_input import setup_fields, validate_setup, validate_key

class Model(BaseModel):
    model_config=ConfigDict(extra='forbid')
class Register(Model):
    username: str=Field(default='',max_length=64)
    agency: str=Field(default='',max_length=120)
    name: str=Field(min_length=2,max_length=120)
    email: str=Field(min_length=5,max_length=254)
    password: str=Field(min_length=12,max_length=256)
    invite_token: str=Field(default='',max_length=200)
    provision_token: str=Field(default='',max_length=200)
class Login(Model):
    username: str=Field(default='',max_length=254)
    email: str=Field(default='',max_length=254)
    password: str=Field(max_length=256)
class MFA(Model):
    code: str=Field(min_length=6,max_length=50)
class Credentials(Model):
    values: dict[str,str]
class PastedKey(Model):
    key: str=Field(min_length=1,max_length=16000)
class Invite(Model):
    name: str=Field(default='',max_length=120)
    email: str=Field(min_length=5,max_length=254)
    role: str
class InvitationUpdate(Model):
    name: str | None=Field(default=None,max_length=120)
    role: str | None=None
class MemberUpdate(Model):
    name: str | None=Field(default=None,min_length=2,max_length=120)
    role: str
    active: bool=True
class SettingsUpdate(Model):
    demo_enabled: bool
    sources: dict[str,str]
class TaskCreate(Model):
    title: str=Field(min_length=2,max_length=200)
    description: str=Field(default='',max_length=2000)
    priority: str='Medium'
    due_date: str=''
    assigned_to: str=''
class TaskUpdate(Model):
    status: str | None=None
    assigned_to: str | None=None
class PasswordUpdate(Model):
    old_password: str=Field(max_length=256)
    new_password: str=Field(min_length=12,max_length=256)

COOKIE='agency_session'

def create_app(settings=None, engine_factory=Engine):
    settings=settings or Settings.load()
    store=Store(settings.database)
    if settings.environment == 'production' and store.one("SELECT id FROM users WHERE username='testing123'"):
        raise RuntimeError('The known testing account must not exist in a production database. Provision a fresh customer database.')
    vault=Vault(settings.vault_key)
    app=FastAPI(title='CircleLogic OS API',version=VERSION,docs_url='/api/docs' if settings.environment!='production' else None,
                redoc_url=None,openapi_url='/api/openapi.json' if settings.environment!='production' else None)
    app.state.store=store;app.state.vault=vault;app.state.settings=settings

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request,exc):
        # Pydantic's default 'input' fields can echo supplied passwords/secrets.
        # Do not return raw request bodies, values, arbitrary keys or context.
        return JSONResponse({'detail':'Invalid request format. Check the required fields and their types.'},status_code=422)

    @app.middleware('http')
    async def boundaries(request,call_next):
        # A loopback listener alone is not a complete DNS-rebinding defence.
        # Compare the exact configured authority, not an attacker-supplied Host.
        expected_host = urlparse(settings.public_origin).netloc.lower()
        if request.headers.get('host', '').lower() != expected_host:
            return JSONResponse({'detail':'Use the configured application address: '+settings.public_origin},status_code=400,
                                headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
        origin=request.headers.get('origin')
        if request.method in ('POST','PATCH','PUT','DELETE'):
            if origin!=settings.public_origin:
                return JSONResponse({'detail':'Request origin is not allowed.'},status_code=403)
            if 'application/json' not in request.headers.get('content-type',''):
                return JSONResponse({'detail':'JSON requests are required.'},status_code=415)
            try:
                content_length=int(request.headers.get('content-length','0') or 0)
            except ValueError:
                return JSONResponse({'detail':'Invalid content length.'},status_code=400)
            if content_length>65536:
                return JSONResponse({'detail':'Request is too large.'},status_code=413)
            body=await request.body()
            if len(body)>65536:
                return JSONResponse({'detail':'Request is too large.'},status_code=413)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['Permissions-Policy']='camera=(), microphone=(), geolocation=()'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://www.google.com; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control']='no-store'
        if settings.secure:
            response.headers['Strict-Transport-Security']='max-age=31536000; includeSubDomains'
        return response

    def raw_session(request):
        raw=request.cookies.get(COOKIE,'')
        if not raw:
            return None
        return store.one('''SELECT u.*,s.token_hash,s.stage,s.csrf,s.expires_at,s.mfa_at
                            FROM sessions s JOIN users u ON u.id=s.user_id
                            WHERE s.token_hash=? AND s.expires_at>? AND u.active=1''',(digest(raw),time.time()))

    def require(request, permission=None, full=True, recent=False):
        s=raw_session(request)
        if not s or (full and (s['stage']!='full' or not s['mfa_enabled'])):
            raise HTTPException(401,'Sign in and complete two-factor authentication.')
        if request.method in ('POST','PATCH','PUT','DELETE'):
            if not hmac.compare_digest(s['csrf'],request.headers.get('x-csrf-token','')):
                raise HTTPException(403,'CSRF verification failed. Reload this page.')
        if permission and permission not in ROLES[s['role']]:
            raise HTTPException(403,'Your role cannot access this module.')
        if recent and s['mfa_at']<time.time()-600:
            raise HTTPException(403,'Reverify two-factor authentication in Security before changing sensitive settings.')
        return s

    def public_user(s):
        tenant=store.one('SELECT name FROM tenants WHERE id=?',(s['tenant_id'],))
        return {'id':s['id'],'name':s['name'],'email':s['email'],'role':s['role'],
                'agency':tenant['name'],'workspace_id':s['tenant_id'],'username':s.get('username') or s['email'],'permissions':sorted(ROLES[s['role']]),'mfa_enabled':bool(s['mfa_enabled'])}

    def issue_session(response,user_id,stage,old=None):
        raw=token();csrf=token();now=time.time();ttl=settings.session_hours*3600 if stage=='full' else 600
        with store.transaction() as db:
            if old:
                db.execute('DELETE FROM sessions WHERE token_hash=?',(old,))
            db.execute('DELETE FROM sessions WHERE expires_at<?',(now,))
            db.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?,?)',
                       (digest(raw),user_id,stage,csrf,now+ttl,now if stage=='full' else 0,now))
        response.set_cookie(COOKIE,raw,max_age=ttl,httponly=True,secure=settings.secure,samesite='lax',path='/api')
        return csrf

    def valid_email(email):
        email=email.strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):
            raise HTTPException(400,'Enter a valid email address.')
        return email

    def consume_mfa(user,code,allow_recovery=True):
        with store.transaction() as db:
            row=db.execute('SELECT * FROM users WHERE id=? AND tenant_id=? AND active=1',(user['id'],user['tenant_id'])).fetchone()
            if not row or not row['totp_secret']:
                raise HTTPException(400,'Authenticator setup is missing.')
            secret=vault.open('mfa:'+row['id'],row['totp_secret'])
            counter=totp_counter(secret,code,row['last_totp_counter'])
            if counter is not None:
                db.execute('UPDATE users SET last_totp_counter=? WHERE id=?',(counter,row['id']))
                return
            if allow_recovery and row['mfa_enabled']:
                codehash=digest(row['id']+':'+code.upper().replace('-','').replace(' ',''))
                n=db.execute('DELETE FROM recovery_codes WHERE user_id=? AND code_hash=?',(row['id'],codehash)).rowcount
                if n:
                    return
            raise HTTPException(400,'Invalid or already-used code. Wait for a new authenticator code and try again.')

    def connection_for(s,provider):
        if provider not in CATALOG:
            raise HTTPException(404,'Unknown integration.')
        if not CATALOG[provider].get('private') and s['role'] not in ('owner','admin'):
            raise HTTPException(403,'Only an agency owner or admin can manage shared integrations.')
        owner=s['id'] if CATALOG[provider].get('private') else ''
        return store.one('SELECT * FROM connections WHERE tenant_id=? AND provider=? AND owner_id=?',(s['tenant_id'],provider,owner)),owner

    @app.get('/api/health')
    def health():
        return {'ok':True,'version':VERSION}

    @app.get('/api/auth/session')
    def session(request:Request):
        s=raw_session(request)
        if not s:
            return {'authenticated':False,'stage':'anonymous','signup_enabled':settings.allow_signup,'environment':settings.environment}
        result={'authenticated':s['stage']=='full','stage':s['stage'],'csrf':s['csrf']}
        result['environment']=settings.environment
        if s['stage']=='full':
            result.update(user=public_user(s),mfa_recent=s['mfa_at']>time.time()-600)
        return result

    @app.post('/api/auth/register')
    def register(body:Register,request:Request):
        check_rate(store,'register:'+str(request.client.host),12)
        email=valid_email(body.email)
        username=validate_username(body.username) if body.username else None
        if username=='testing123':
            raise HTTPException(400,'This username is reserved for the local development account.')
        if len(body.name.strip())<2:
            raise HTTPException(400,'Enter a name of at least two characters.')
        invitation=None
        if body.invite_token:
            invitation=store.one('SELECT * FROM invitations WHERE token_hash=? AND expires_at>?',(digest(body.invite_token),time.time()))
            if not invitation or invitation['email']!=email:
                raise HTTPException(400,'The invitation is invalid, expired or belongs to another email.')
        if not invitation and not settings.allow_signup:
            if not settings.provision_token or not hmac.compare_digest(settings.provision_token,body.provision_token):
                raise HTTPException(403,'Workspace creation is restricted. Request an invitation from your administrator.')
        if not invitation and not body.agency.strip():
            raise HTTPException(400,'Enter an agency name.')
        user_id=uid(); tenant=invitation['tenant_id'] if invitation else uid();now=time.time()
        password_hash=PASSWORDS.hash(body.password)
        with store.transaction() as db:
            if db.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone():
                raise HTTPException(409,'This email already has an account. Sign in instead.')
            if username and db.execute('SELECT id FROM users WHERE username=?',(username,)).fetchone():
                raise HTTPException(409,'This username already has an account.')
            if invitation:
                used=db.execute('DELETE FROM invitations WHERE token_hash=? AND expires_at>?',(invitation['token_hash'],now)).rowcount
                if not used:
                    raise HTTPException(400,'This invitation was already used.')
            else:
                db.execute('INSERT INTO tenants VALUES(?,?,?,?)',(tenant,body.agency.strip(),json.dumps({'demo_enabled':False}),now))
            db.execute('INSERT INTO users(id,tenant_id,email,name,password_hash,role,created_at,username) VALUES(?,?,?,?,?,?,?,?)',
                       (user_id,tenant,email,body.name.strip(),password_hash,invitation['role'] if invitation else 'owner',now,username))
        response=JSONResponse({'stage':'enrol'},status_code=201)
        csrf=issue_session(response,user_id,'enrol')
        response.body=json.dumps({'stage':'enrol','csrf':csrf}).encode()
        response.headers['content-length']=str(len(response.body))
        store.audit(tenant,user_id,'user.registered')
        return response

    @app.post('/api/auth/login')
    def login(body:Login,request:Request):
        email=(body.username or body.email).strip().lower()
        if not email:
            raise HTTPException(400,'Enter your username or email.')
        check_rate(store,'login-ip:'+str(request.client.host),40)
        check_rate(store,'login-account:'+digest(email),10)
        user=store.one('SELECT * FROM users WHERE email=? OR username=?',(email,email))
        valid=verify_password(user['password_hash'] if user else None,body.password)
        if not user or not valid or not user['active']:
            raise HTTPException(401,'Username or password is incorrect.')
        if PASSWORDS.check_needs_rehash(user['password_hash']):
            store.execute('UPDATE users SET password_hash=? WHERE id=?',(PASSWORDS.hash(body.password),user['id']))
        stage='mfa' if user['mfa_enabled'] else 'enrol'
        response=JSONResponse({'stage':stage})
        existing=raw_session(request)
        csrf=issue_session(response,user['id'],stage,existing['token_hash'] if existing else None)
        response.body=json.dumps({'stage':stage,'csrf':csrf}).encode();response.headers['content-length']=str(len(response.body))
        return response

    @app.get('/api/auth/enrolment')
    def enrolment(request:Request):
        s=require(request,full=False)
        if s['stage']!='enrol' or s['mfa_enabled']:
            raise HTTPException(403,'Authenticator setup is not available for this session.')
        with store.transaction() as db:
            row=db.execute('SELECT totp_secret FROM users WHERE id=?',(s['id'],)).fetchone()
            if row['totp_secret']:
                secret=vault.open('mfa:'+s['id'],row['totp_secret'])
            else:
                secret=new_totp_secret()
                db.execute('UPDATE users SET totp_secret=? WHERE id=?',(vault.seal('mfa:'+s['id'],secret),s['id']))
        uri=provisioning_uri(secret,s.get('username') or s['email'])
        buf=io.BytesIO();qrcode.make(uri).save(buf,format='PNG')
        return {'secret':secret,'qr':'data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()}

    @app.post('/api/auth/mfa')
    def mfa(body:MFA,request:Request):
        s=require(request,full=False)
        if s['stage'] not in ('mfa','enrol'):
            raise HTTPException(400,'This session has already completed authentication.')
        check_rate(store,'mfa:'+s['id'],8,300)
        consume_mfa(s,body.code,allow_recovery=s['stage']=='mfa')
        recovery=[]
        if s['stage']=='enrol':
            recovery=[token().replace('-','').replace('_','')[:16].upper() for _ in range(8)]
            with store.transaction() as db:
                db.execute('UPDATE users SET mfa_enabled=1 WHERE id=?',(s['id'],))
                db.execute('DELETE FROM recovery_codes WHERE user_id=?',(s['id'],))
                db.executemany('INSERT INTO recovery_codes VALUES(?,?)',[(s['id'],digest(s['id']+':'+c)) for c in recovery])
            store.audit(s['tenant_id'],s['id'],'mfa.enrolled')
        response=JSONResponse({'ok':True})
        csrf=issue_session(response,s['id'],'full',s['token_hash'])
        response.body=json.dumps({'ok':True,'csrf':csrf,'recovery_codes':recovery}).encode();response.headers['content-length']=str(len(response.body))
        store.audit(s['tenant_id'],s['id'],'session.authenticated')
        return response

    @app.post('/api/auth/step-up')
    def stepup(body:MFA,request:Request):
        s=require(request);check_rate(store,'mfa:'+s['id'],8,300)
        consume_mfa(s,body.code)
        store.execute('UPDATE sessions SET mfa_at=? WHERE token_hash=?',(time.time(),s['token_hash']))
        return {'ok':True}

    @app.post('/api/auth/logout')
    def logout(request:Request):
        s=require(request,full=False)
        store.execute('DELETE FROM sessions WHERE token_hash=?',(s['token_hash'],))
        response=JSONResponse({'ok':True});response.delete_cookie(COOKIE,path='/api')
        return response

    @app.post('/api/auth/revoke-other-sessions')
    def revoke(request:Request):
        s=require(request,recent=True)
        store.execute('DELETE FROM sessions WHERE user_id=? AND token_hash<>?',(s['id'],s['token_hash']))
        store.audit(s['tenant_id'],s['id'],'sessions.revoked')
        return {'ok':True}

    @app.post('/api/auth/password')
    def password(body:PasswordUpdate,request:Request):
        s=require(request,recent=True);check_rate(store,'password:'+s['id'],5)
        if not verify_password(s['password_hash'],body.old_password):
            raise HTTPException(400,'Current password is incorrect.')
        with store.transaction() as db:
            db.execute('UPDATE users SET password_hash=? WHERE id=?',(PASSWORDS.hash(body.new_password),s['id']))
            db.execute('DELETE FROM sessions WHERE user_id=? AND token_hash<>?',(s['id'],s['token_hash']))
        store.audit(s['tenant_id'],s['id'],'password.changed')
        return {'ok':True}

    @app.get('/api/brain/dashboard')
    def get_brain_dashboard(request:Request):
        s=require(request,'dashboard')
        return brain_dashboard(store,s)

    @app.get('/api/brain/connections')
    def get_brain_connections(request:Request):
        s=require(request,'dashboard')
        return {'connections':[connection_status(store,s,p,settings.public_origin) for p in BRAIN_PROVIDERS]}

    @app.get('/api/pilot/readiness')
    def get_readiness(request:Request):
        s=require(request,'dashboard')
        return readiness(store,vault,settings,s)

    @app.get('/api/integrations/{provider}/diagnostics')
    def get_diagnostics(provider:str,request:Request):
        s=require(request,'integrations');c,owner=connection_for(s,provider)
        return diagnostics(store,vault,settings,s,provider,c,owner)

    @app.get('/api/settings')
    def get_settings(request:Request):
        s=require(request)
        return settings_for(store,s['tenant_id'])

    @app.put('/api/settings')
    def update_settings(body:SettingsUpdate,request:Request):
        s=require(request,'settings',recent=True)
        if body.demo_enabled:
            raise HTTPException(400,'Synthetic data is only available in the standalone design preview, not in a customer workspace.')
        for kind,provider in body.sources.items():
            if kind not in DEFAULT_SOURCES or provider not in CATALOG or kind not in CATALOG[provider]['kinds']:
                raise HTTPException(400,'Unsupported authoritative source mapping.')
        current=settings_for(store,s['tenant_id'])
        current.update(demo_enabled=False,sources={**current['sources'],**body.sources})
        store.execute('UPDATE tenants SET settings=? WHERE id=?',(json.dumps(current),s['tenant_id']))
        store.audit(s['tenant_id'],s['id'],'settings.updated')
        return current

    @app.get('/api/integrations')
    def integrations(request:Request):
        s=require(request,'integrations');result=[]
        for provider,meta in CATALOG.items():
            if s['role'] not in ('owner','admin') and not meta.get('private'):
                continue
            owner=s['id'] if meta.get('private') else ''
            c=store.one('SELECT * FROM connections WHERE tenant_id=? AND provider=? AND owner_id=?',(s['tenant_id'],provider,owner))
            manageable=('integrations' in ROLES[s['role']] and (meta.get('private') or s['role'] in ('owner','admin')))
            result.append({'id':provider,**meta,'status':c['status'] if c else ('not_connected' if meta['implemented'] else 'not_implemented'),
                'last_success':c['last_success'] if c else None,'error':c['error'] if c else None,
                'has_credentials':bool(c and c['credentials']),'syncing':bool(c and c['lease_until']>time.time()),
                'manageable':bool(manageable),
                'callback':settings.public_origin+'/api/oauth/'+provider+'/callback' if meta['auth']=='oauth' else None,
                'verification':'Connection configuration available.' if meta['implemented'] else 'Connector development required.'})
        return {'integrations':result}

    def save_credential_values(s, provider, values, owner):
        meta=CATALOG[provider]
        if not meta['implemented']:
            raise HTTPException(422,'This connector is not implemented. Credentials cannot enable it yet.')
        required={f['key'] for f in meta['fields']}
        if set(values)!=required or any(not str(v).strip() or len(str(v))>16000 for v in values.values()):
            raise HTTPException(400,'Supply exactly the required fields. Blank credentials and extra fields are rejected.')
        if provider=='microsoft':
            # The tenant is part of a fixed Microsoft URL; no URLs or path fragments.
            from .connectors import ident
            try:
                ident(values['directory_id'].strip())
            except ConnectorError:
                raise HTTPException(400,'Enter the Microsoft directory (tenant) ID, not a URL.') from None
        if provider=='google':
            validate_setup('google',{'client_id':values['client_id']})
        if provider=='docusign' and values['environment'] not in ('demo','production'):
            raise HTTPException(400,'DocuSign environment must be demo or production.')
        ctx=conn_context(s['tenant_id'],provider,owner)
        secret_fields={f['key'] for f in meta['fields'] if f.get('secret')}
        cleaned={k:(str(v) if k in secret_fields else str(v).strip()) for k,v in values.items()}
        cipher=vault.seal(ctx,cleaned)
        connection_only=bool(meta.get('connection_only'))
        new_status='connected' if connection_only else 'configured'
        success_at=time.time() if connection_only else None
        with store.transaction() as db:
            row=db.execute('SELECT * FROM connections WHERE tenant_id=? AND provider=? AND owner_id=?',(s['tenant_id'],provider,owner)).fetchone()
            if row:
                db.execute('UPDATE connections SET credentials=?,status=?,last_success=?,error=NULL,revision=revision+1,lease_until=0,lease_token=NULL WHERE id=? AND tenant_id=?',
                           (cipher,new_status,success_at,row['id'],s['tenant_id']))
                db.execute('DELETE FROM oauth_states WHERE connection_id=?',(row['id'],))
            else:
                db.execute('INSERT INTO connections(id,tenant_id,provider,owner_id,credentials,status,last_success) VALUES(?,?,?,?,?,?,?)',
                           (uid(),s['tenant_id'],provider,owner,cipher,new_status,success_at))
            db.execute('DELETE FROM connection_setups WHERE tenant_id=? AND provider=? AND owner_id=?',
                       (s['tenant_id'],provider,owner))
        store.audit(s['tenant_id'],s['id'],'integration.configured',provider)
        return {'ok':True,'next':'authorise' if meta['auth']=='oauth' else ('saved' if connection_only else 'sync')}

    @app.put('/api/integrations/{provider}')
    def save_integration(provider:str,body:Credentials,request:Request):
        s=require(request,'integrations',recent=True);_,owner=connection_for(s,provider)
        return save_credential_values(s,provider,body.values,owner)

    def read_connection_setup(s, provider, owner, existing):
        fields=setup_fields(provider)
        row=store.one('SELECT payload FROM connection_setups WHERE tenant_id=? AND provider=? AND owner_id=?',
                      (s['tenant_id'],provider,owner))
        if row:
            values=vault.open('setup:'+conn_context(s['tenant_id'],provider,owner),row['payload'])
        elif existing and existing['credentials']:
            active=vault.open(conn_context(s['tenant_id'],provider,owner),existing['credentials'])
            values={f['key']:active.get(f['key'],'') for f in fields}
        else:
            values={f['key']:'' for f in fields}
        # Return only explicit, non-secret identifiers. Never return an access
        # token, refresh token, saved secret or unrelated workspace settings.
        return {f['key']:values.get(f['key'],'') for f in fields}

    @app.get('/api/integrations/{provider}/setup')
    def get_connection_setup(provider:str,request:Request):
        s=require(request,'integrations');existing,owner=connection_for(s,provider)
        fields=setup_fields(provider)
        values=read_connection_setup(s,provider,owner,existing)
        return {'provider':provider,'fields':fields,'values':values,
                'ready':all(values.values()),
                'callback':settings.public_origin+'/api/oauth/'+provider+'/callback' if CATALOG[provider]['auth']=='oauth' else None}

    @app.put('/api/integrations/{provider}/setup')
    def put_connection_setup(provider:str,body:Credentials,request:Request):
        s=require(request,'integrations',recent=True);_,owner=connection_for(s,provider)
        values=validate_setup(provider,body.values)
        cipher=vault.seal('setup:'+conn_context(s['tenant_id'],provider,owner),values)
        store.execute('INSERT INTO connection_setups(tenant_id,provider,owner_id,payload,updated_at) VALUES(?,?,?,?,?) '
                      'ON CONFLICT(tenant_id,provider,owner_id) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at',
                      (s['tenant_id'],provider,owner,cipher,time.time()))
        store.audit(s['tenant_id'],s['id'],'integration.setup_saved',provider)
        return {'ok':True,'next':'paste_key'}

    @app.post('/api/integrations/{provider}/key')
    def paste_connection_key(provider:str,body:PastedKey,request:Request):
        s=require(request,'integrations',recent=True);existing,owner=connection_for(s,provider)
        setup_fields(provider)  # Refuse unfinished or unsupported connectors.
        key=validate_key(body.key)
        values=read_connection_setup(s,provider,owner,existing)
        if not all(values.values()):
            raise HTTPException(400,'Open Setup guide and save the provider IDs once. Then return here and paste only the client secret Value.')
        # IDs are already checked by setup or retained from a working v05
        # connection. No shared/environment credential fallbacks are used.
        values['client_secret']=key
        return save_credential_values(s,provider,values,owner)

    @app.post('/api/integrations/{provider}/sync')
    def sync(provider:str,request:Request):
        s=require(request,'integrations');c,_=connection_for(s,provider)
        check_rate(store,'sync:'+s['tenant_id']+':'+provider+':'+s['id'],12,300)
        if not c or not c['credentials']:
            raise HTTPException(400,'Save credentials and authorise this provider first.')
        try:
            return perform_sync(store,vault,c,s['id'],engine_factory)
        except ConnectorError as exc:
            raise HTTPException(502,str(exc)) from None

    @app.delete('/api/integrations/{provider}')
    def disconnect(provider:str,request:Request):
        s=require(request,'integrations',recent=True);c,owner=connection_for(s,provider)
        store.execute('DELETE FROM connection_setups WHERE tenant_id=? AND provider=? AND owner_id=?',
                      (s['tenant_id'],provider,owner))
        if c:
            with store.transaction() as db:
                db.execute('UPDATE connections SET credentials=NULL,status=?,revision=revision+1,error=NULL,lease_until=0,lease_token=NULL WHERE id=? AND tenant_id=?',('disconnected',c['id'],s['tenant_id']))
                db.execute('DELETE FROM records WHERE tenant_id=? AND connection_id=?',(s['tenant_id'],c['id']))
                db.execute('DELETE FROM snapshots WHERE connection_id=?',(c['id'],))
                db.execute('DELETE FROM oauth_states WHERE connection_id=?',(c['id'],))
            store.audit(s['tenant_id'],s['id'],'integration.disconnected',provider)
        return {'ok':True,'note':'Stored credentials and imported records were erased. Also revoke this app in the provider account; upstream consent is not revoked automatically.'}

    @app.post('/api/integrations/{provider}/authorise')
    def authorise(provider:str,request:Request):
        s=require(request,'integrations',recent=True);c,owner=connection_for(s,provider)
        if not c or not c['credentials'] or CATALOG[provider]['auth']!='oauth':
            raise HTTPException(400,'Save the OAuth application configuration first.')
        creds=vault.open(conn_context(s['tenant_id'],provider,owner),c['credentials'])
        state=token();verifier=token()+token();callback=settings.public_origin+'/api/oauth/'+provider+'/callback'
        try:
            target=auth_url(provider,creds,callback,state,verifier)
        except ConnectorError as exc:
            raise HTTPException(400,str(exc)) from None
        with store.transaction() as db:
            db.execute('DELETE FROM oauth_states WHERE expires_at<? OR (connection_id=? AND user_id=?)',(time.time(),c['id'],s['id']))
            db.execute('INSERT INTO oauth_states VALUES(?,?,?,?,?,?,?,?,?)',
                (digest(state),s['token_hash'],c['id'],s['tenant_id'],s['id'],provider,vault.seal('oauth:'+digest(state),verifier),c['revision'],time.time()+600))
        return {'url':target}

    @app.get('/api/oauth/{provider}/callback')
    def callback(provider:str,request:Request,state:str='',code:str='',error:str=''):
        s=require(request,'integrations')
        with store.transaction() as db:
            row=db.execute('SELECT * FROM oauth_states WHERE state_hash=? AND session_hash=? AND tenant_id=? AND user_id=? AND provider=? AND expires_at>?',
                (digest(state),s['token_hash'],s['tenant_id'],s['id'],provider,time.time())).fetchone()
            if not row:
                raise HTTPException(400,'Invalid, expired or already-used OAuth state.')
            row=dict(row)
            db.execute('DELETE FROM oauth_states WHERE state_hash=?',(digest(state),))
        c,owner=connection_for(s,provider)
        if not c or c['id']!=row['connection_id'] or c['revision']!=row['revision'] or not c['credentials']:
            raise HTTPException(400,'Connection changed during authorisation. Start again.')
        if error or not code:
            # Never echo the provider's free-form error description into the UI or logs.
            provider_name=CATALOG[provider]['name']
            store.execute('UPDATE connections SET error=? WHERE id=? AND tenant_id=? AND revision=?',
                (provider_name+' authorisation was cancelled or refused. Retry and review the provider consent settings.',c['id'],s['tenant_id'],row['revision']))
            return RedirectResponse('/#integrations?oauth=denied&provider='+provider,303)
        ctx=conn_context(s['tenant_id'],provider,owner)
        creds=vault.open(ctx,c['credentials']);engine=engine_factory()
        try:
            engine.exchange(provider,creds,code=code,callback=settings.public_origin+'/api/oauth/'+provider+'/callback',
                            verifier=vault.open('oauth:'+digest(state),row['verifier']))
            n=store.execute('UPDATE connections SET credentials=?,status=?,error=NULL WHERE id=? AND tenant_id=? AND revision=?',
                (vault.seal(ctx,creds),'authorised',c['id'],s['tenant_id'],row['revision']))
            if not n:
                raise ConnectorError('Connection changed before authorisation was saved.')
            store.audit(s['tenant_id'],s['id'],'integration.authorised',provider)
        except ConnectorError as exc:
            store.execute('UPDATE connections SET error=? WHERE id=? AND tenant_id=? AND revision=?',
                (str(exc),c['id'],s['tenant_id'],row['revision']))
            store.audit(s['tenant_id'],s['id'],'integration.authorisation_failed',provider)
            return RedirectResponse('/#integrations?oauth=failed&provider='+provider,303)
        finally:
            engine.close()
        # Authorisation is not the same as sync success. The user starts a sync explicitly.
        return RedirectResponse('/#integrations?oauth=success&provider='+provider,303)

    @app.get('/api/records/{kind}')
    def records(kind:str,request:Request,q:str='',status:str='',page:int=1,per_page:int=25):
        s=require(request,kind)
        if kind not in DEFAULT_SOURCES:
            raise HTTPException(404,'Unknown record type.')
        data=dataset(store,s,kind);rows=data.pop('rows')
        if q:
            rows=[r for r in rows if q.lower() in json.dumps(r).lower()]
        if status:
            rows=[r for r in rows if str(r.get('status','')).lower()==status.lower()]
        page=max(1,page);per_page=max(1,min(per_page,100));start=(page-1)*per_page
        return {**data,'rows':rows[start:start+per_page],'total':len(rows),'page':page,'per_page':per_page}

    @app.get('/api/record/{kind}/{record_id}')
    def record_detail(kind:str,record_id:str,request:Request):
        s=require(request,kind)
        if kind not in DEFAULT_SOURCES:
            raise HTTPException(404,'Unknown record type.')
        data=dataset(store,s,kind)
        row=next((r for r in data['rows'] if r['id']==record_id),None)
        if not row:
            raise HTTPException(404,'Record not found in your workspace or permitted source.')
        return {'record':row,'mode':data['mode'],'provider':data['provider'],'note':data['note']}

    @app.get('/api/search')
    def search(request:Request,q:str=''):
        s=require(request)
        if len(q.strip())<2:
            return {'results':[]}
        results=[]
        for kind in DEFAULT_SOURCES:
            if kind not in ROLES[s['role']]:
                continue
            d=dataset(store,s,kind)
            for r in d['rows']:
                if q.lower() in json.dumps(r).lower():
                    results.append({'kind':kind,'id':r['id'],'title':r.get('title',''), 'mode':d['mode']})
                    if len(results)>=30:
                        return {'results':results}
        return {'results':results}

    @app.get('/api/export/{kind}')
    def export(kind:str,request:Request):
        s=require(request,kind)
        if kind not in DEFAULT_SOURCES:
            raise HTTPException(404,'Unknown record type.')
        d=dataset(store,s,kind)
        fields=['title','status','owner','source_mode','source_provider']
        extras=sorted({k for r in d['rows'] for k,v in r.items() if isinstance(v,(str,int,float)) and k not in fields and k not in ('id','external_id','assigned_to')})
        fields+=extras;buf=io.StringIO();writer=csv.DictWriter(buf,fieldnames=fields);writer.writeheader()
        def safe(value):
            value='' if value is None else str(value)
            return "'"+value if value and value.lstrip().startswith(('=','+','-','@','\t','\r','\n')) else value
        for r in d['rows']:
            full={**r,'source_mode':d['mode'],'source_provider':d['provider']}
            writer.writerow({k:safe(full.get(k,'')) for k in fields})
        store.audit(s['tenant_id'],s['id'],'data.exported',kind)
        return Response(buf.getvalue(),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename="agency-{kind}-{d["mode"]}.csv"'})

    @app.get('/api/dashboard')
    def dashboard(request:Request):
        s=require(request,'dashboard');modules={};metrics=[];suggestions=[]
        for kind in DEFAULT_SOURCES:
            if kind in ROLES[s['role']]:
                d=dataset(store,s,kind);rows=d.pop('rows')
                modules[kind]={**d,'total':len(rows),'rows':rows[:5]}
                if kind in ('listings','contacts','rentals','invoices'):
                    title={'listings':'Listings synced','contacts':'CRM contacts','rentals':'Rent roll','invoices':'Unpaid invoices (AUD)'}[kind]
                    amount=len(rows);fmt='number'
                    if kind=='invoices':
                        fmt='currency';amount=sum(float(r.get('due') or 0) for r in rows if r.get('currency')=='AUD' and r.get('type')=='ACCREC' and r.get('status') not in ('VOIDED','DELETED'))
                    metrics.append({'kind':kind,'title':title,'value':amount,'format':fmt,'mode':d['mode'],'source':d['provider']})
                if d['mode']=='stale':
                    suggestions.append({'title':'Refresh '+kind.replace('_',' '),'detail':'This module is showing an older successful snapshot. Check its integration before making decisions.','kind':'integrations','severity':'warning'})
        for kind,title in [('tasks','Open workspace tasks'),('documents','Tracked documents')]:
            if len(metrics)<4 and kind in modules:
                metrics.append({'kind':kind,'title':title,'value':modules[kind]['total'],'format':'number','mode':modules[kind]['mode'],'source':modules[kind]['provider']})
        metrics.sort(key=lambda m:['invoices','listings','contacts','rentals','tasks','documents'].index(m['kind']))
        modes={m['mode'] for m in modules.values()}
        tasks=modules.get('tasks',{}).get('rows',[])
        for r in tasks[:2]:
            if r.get('status')!='Done':
                suggestions.append({'title':r['title'],'detail':'Review this task before acting. No message will be sent automatically.','kind':'tasks','severity':'normal'})
        return {'metrics':metrics[:4],'modules':modules,'suggestions':suggestions[:4],
                'mode':'workspace', 'chart':None}

    @app.post('/api/tasks')
    def create_task(body:TaskCreate,request:Request):
        s=require(request,'tasks');assigned=body.assigned_to or s['id']
        if assigned!=s['id'] and s['role'] not in ('owner','admin'):
            raise HTTPException(403,'Only admins can assign work to another team member.')
        assignee=store.one('SELECT id,name,role FROM users WHERE id=? AND tenant_id=? AND active=1 AND mfa_enabled=1',(assigned,s['tenant_id']))
        if not assignee or 'tasks' not in ROLES[assignee['role']]:
            raise HTTPException(400,'Choose an active, two-factor-enrolled member with task access.')
        if body.priority not in ('High','Medium','Low'):
            raise HTTPException(400,'Invalid priority.')
        if body.due_date:
            from datetime import date
            try:
                date.fromisoformat(body.due_date)
            except ValueError:
                raise HTTPException(400,'Due date must be YYYY-MM-DD.') from None
        task_id=uid();r={**body.model_dump(),'external_id':task_id,'status':'Open','assigned_to':assigned,'owner':assignee['name']}
        store.execute('INSERT INTO records VALUES(?,?,?,?,?,?,?,?,?)',(task_id,s['tenant_id'],None,'manual','','tasks',task_id,json.dumps(r),time.time()))
        store.audit(s['tenant_id'],s['id'],'task.created',task_id)
        return {'id':task_id,'record':r}

    @app.patch('/api/tasks/{task_id}')
    def update_task(task_id:str,body:TaskUpdate,request:Request):
        s=require(request,'tasks')
        if body.status is None and body.assigned_to is None:
            raise HTTPException(400,'Supply a task status or assignee.')
        with store.transaction() as db:
            r=db.execute('SELECT * FROM records WHERE id=? AND tenant_id=? AND kind=? AND provider=?',
                         (task_id,s['tenant_id'],'tasks','manual')).fetchone()
            if not r:
                raise HTTPException(404,'Editable workspace task not found. Sample tasks are read-only.')
            data=json.loads(r['payload'])
            if data['assigned_to']!=s['id'] and s['role'] not in ('owner','admin'):
                raise HTTPException(403,"You cannot update another member's task.")
            if body.status is not None:
                if body.status not in ('Open','In progress','Done'):
                    raise HTTPException(400,'Invalid task status.')
                data['status']=body.status
            if body.assigned_to is not None:
                if s['role'] not in ('owner','admin'):
                    raise HTTPException(403,'Only an owner or admin can reassign tasks.')
                assignee=db.execute('SELECT id,name,role FROM users WHERE id=? AND tenant_id=? AND active=1 AND mfa_enabled=1',
                                    (body.assigned_to,s['tenant_id'])).fetchone()
                if not assignee or 'tasks' not in ROLES[assignee['role']]:
                    raise HTTPException(400,'Choose an active, two-factor-enrolled member with task access.')
                data.update(assigned_to=assignee['id'],owner=assignee['name'])
            db.execute('UPDATE records SET payload=?,updated_at=? WHERE id=? AND tenant_id=?',
                       (json.dumps(data),time.time(),task_id,s['tenant_id']))
        store.audit(s['tenant_id'],s['id'],'task.updated',task_id)
        return {'ok':True}

    @app.get('/api/team')
    def team(request:Request):
        s=require(request,'team')
        members=store.all('SELECT id,name,email,role,mfa_enabled,active,created_at FROM users WHERE tenant_id=? ORDER BY name',
                          (s['tenant_id'],))
        counts={}
        for row in store.all("SELECT payload FROM records WHERE tenant_id=? AND kind='tasks' AND provider='manual'",(s['tenant_id'],)):
            task=json.loads(row['payload'])
            if task.get('status')!='Done':
                member_id=task.get('assigned_to')
                counts[member_id]=counts.get(member_id,0)+1
        for member in members:
            member['open_tasks']=counts.get(member['id'],0)
            member['can_assign']=bool(member['active'] and member['mfa_enabled'] and 'tasks' in ROLES[member['role']])
        invitations=store.all('SELECT id,name,email,role,expires_at,created_at FROM invitations WHERE tenant_id=? ORDER BY created_at DESC',
                              (s['tenant_id'],))
        return {'members':members,'invitations':invitations,'storage':'server'}

    def permitted_role(s,role,current_role=None):
        if role not in ROLES:
            raise HTTPException(400,'Unknown role.')
        if s['role']!='owner' and (role in ('owner','admin') or current_role in ('owner','admin')):
            raise HTTPException(403,'Only an owner can manage administrator or owner access.')

    def invitation_result(raw,invitation):
        return {'id':invitation['id'],'name':invitation['name'],'role':invitation['role'],
                'url':settings.public_origin+'/#join?token='+raw,'email':invitation['email'],'expires_in_hours':24,
                'note':'Not emailed automatically. Share this single-use link through an approved private channel. The recipient creates their own password and completes two-factor setup.'}

    @app.post('/api/team/invite')
    def invite(body:Invite,request:Request):
        s=require(request,'team',recent=True);email=valid_email(body.email)
        check_rate(store,'invite:'+s['tenant_id']+':'+s['id'],40,3600)
        permitted_role(s,body.role)
        name=body.name.strip()
        if body.name and len(name)<2:
            raise HTTPException(400,'Enter a name of at least two characters.')
        raw=token();now=time.time();invitation_id=uid()
        with store.transaction() as db:
            if db.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone():
                raise HTTPException(409,'That email already has an account. This pilot supports one agency per login.')
            existing=db.execute('SELECT role FROM invitations WHERE tenant_id=? AND email=?',(s['tenant_id'],email)).fetchone()
            if existing:
                permitted_role(s,body.role,existing['role'])
                raise HTTPException(409,'An invitation already exists for this email. Reissue or revoke it in Team & access.')
            db.execute('''INSERT INTO invitations(token_hash,tenant_id,email,role,expires_at,created_by,id,name,created_at)
                        VALUES(?,?,?,?,?,?,?,?,?)''',
                       (digest(raw),s['tenant_id'],email,body.role,now+86400,s['id'],invitation_id,name,now))
        store.audit(s['tenant_id'],s['id'],'member.invited',invitation_id)
        return invitation_result(raw,{'id':invitation_id,'name':name,'role':body.role,'email':email})

    @app.post('/api/team/invitations/{invitation_id}/reissue')
    def reissue_invitation(invitation_id:str,body:InvitationUpdate,request:Request):
        s=require(request,'team',recent=True)
        check_rate(store,'invite:'+s['tenant_id']+':'+s['id'],40,3600)
        raw=token()
        with store.transaction() as db:
            row=db.execute('SELECT * FROM invitations WHERE id=? AND tenant_id=?',(invitation_id,s['tenant_id'])).fetchone()
            if not row:
                raise HTTPException(404,'Invitation not found or already accepted.')
            role=body.role if body.role is not None else row['role']
            name=body.name.strip() if body.name is not None else row['name']
            permitted_role(s,role,row['role'])
            if body.name is not None and len(name)<2:
                raise HTTPException(400,'Enter a name of at least two characters.')
            db.execute('UPDATE invitations SET token_hash=?,expires_at=?,name=?,role=? WHERE id=? AND tenant_id=?',
                       (digest(raw),time.time()+86400,name,role,invitation_id,s['tenant_id']))
        store.audit(s['tenant_id'],s['id'],'invitation.reissued',invitation_id)
        return invitation_result(raw,{'id':invitation_id,'name':name,'role':role,'email':row['email']})

    @app.delete('/api/team/invitations/{invitation_id}')
    def revoke_invitation(invitation_id:str,request:Request):
        s=require(request,'team',recent=True)
        with store.transaction() as db:
            row=db.execute('SELECT role FROM invitations WHERE id=? AND tenant_id=?',(invitation_id,s['tenant_id'])).fetchone()
            if not row:
                raise HTTPException(404,'Invitation not found or already accepted.')
            permitted_role(s,row['role'],row['role'])
            db.execute('DELETE FROM invitations WHERE id=? AND tenant_id=?',(invitation_id,s['tenant_id']))
        store.audit(s['tenant_id'],s['id'],'invitation.revoked',invitation_id)
        return {'ok':True}

    @app.get('/api/auth/invitation')
    def get_invitation(request:Request,token:str=''):
        check_rate(store,'invitation-read:'+str(request.client.host),60,300)
        invitation=store.one('''SELECT i.email,i.name,i.role,t.name AS agency FROM invitations i
                              JOIN tenants t ON t.id=i.tenant_id WHERE i.token_hash=? AND i.expires_at>?''',(digest(token),time.time()))
        if not invitation:
            raise HTTPException(404,'Invitation is invalid or expired.')
        return invitation

    @app.patch('/api/team/{user_id}')
    def update_member(user_id:str,body:MemberUpdate,request:Request):
        s=require(request,'team',recent=True)
        name=body.name.strip() if body.name is not None else None
        if name is not None and len(name)<2:
            raise HTTPException(400,'Enter a name of at least two characters.')
        with store.transaction() as db:
            target=db.execute('SELECT * FROM users WHERE id=? AND tenant_id=?',(user_id,s['tenant_id'])).fetchone()
            if not target:
                raise HTTPException(404,'Member not found.')
            if user_id==s['id'] and (body.role!=s['role'] or not body.active):
                raise HTTPException(400,'You cannot change your own role or disable your own account here.')
            # Admins may edit their own display name, never elevate their role.
            if user_id!=s['id']:
                permitted_role(s,body.role,target['role'])
            if target['role']=='owner' and (body.role!='owner' or not body.active):
                remaining=db.execute("SELECT COUNT(*) FROM users WHERE tenant_id=? AND role='owner' AND active=1 AND mfa_enabled=1 AND id!=?",
                                     (s['tenant_id'],user_id)).fetchone()[0]
                if not remaining:
                    raise HTTPException(400,'Keep at least one active, two-factor-enrolled owner.')
            access_changed=body.role!=target['role'] or int(body.active)!=target['active']
            db.execute('UPDATE users SET name=?,role=?,active=? WHERE id=? AND tenant_id=?',
                       (name if name is not None else target['name'],body.role,int(body.active),user_id,s['tenant_id']))
            if name is not None and name!=target['name']:
                for row in db.execute("SELECT id,payload FROM records WHERE tenant_id=? AND kind='tasks' AND provider='manual'",(s['tenant_id'],)).fetchall():
                    task=json.loads(row['payload'])
                    if task.get('assigned_to')==user_id:
                        task['owner']=name
                        db.execute('UPDATE records SET payload=?,updated_at=? WHERE id=? AND tenant_id=?',
                                   (json.dumps(task),time.time(),row['id'],s['tenant_id']))
            if access_changed:
                db.execute('DELETE FROM sessions WHERE user_id=?',(user_id,))
            if not body.active:
                db.execute('DELETE FROM connection_setups WHERE tenant_id=? AND owner_id=?',(s['tenant_id'],user_id))
                db.execute('UPDATE connections SET credentials=NULL,status=?,revision=revision+1,lease_token=NULL,lease_until=0 WHERE tenant_id=? AND owner_id=?',
                           ('disconnected',s['tenant_id'],user_id))
                db.execute('DELETE FROM records WHERE tenant_id=? AND owner_id=?',(s['tenant_id'],user_id))
                db.execute('DELETE FROM oauth_states WHERE user_id=? AND tenant_id=?',(user_id,s['tenant_id']))
        store.audit(s['tenant_id'],s['id'],'member.access_changed' if access_changed else 'member.profile_updated',user_id)
        return {'ok':True,'sessions_revoked':access_changed}

    @app.get('/api/audit')
    def audit(request:Request):
        s=require(request,'audit')
        return {'events':store.all('SELECT a.id,a.action,a.detail,a.created_at,u.name AS actor FROM audit a LEFT JOIN users u ON u.id=a.user_id AND u.tenant_id=a.tenant_id WHERE a.tenant_id=? ORDER BY a.created_at DESC LIMIT 200',(s['tenant_id'],))}

    frontend=Path(__file__).resolve().parents[2]/'frontend'
    if frontend.exists():
        app.mount('/',StaticFiles(directory=frontend,html=True),name='frontend')
    return app
