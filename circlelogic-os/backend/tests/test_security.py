import base64
import json
import time
from urllib.parse import urlparse,parse_qs
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from app.security import otp,totp_counter,Vault,check_rate,digest
from app.catalog import CATALOG
from conftest import ORIGIN,PASSWORD,request,register,add_member

@pytest.mark.parametrize('timestamp,expected',[(59,'94287082'),(1111111109,'07081804'),(1111111111,'14050471'),(1234567890,'89005924'),(2000000000,'69279037'),(20000000000,'65353130')])
def test_totp_rfc6238_sha1_vectors(timestamp,expected):
    secret=base64.b32encode(b'12345678901234567890').decode()
    assert otp(secret,timestamp//30,8)==expected

def test_totp_replay_window_and_invalid_input():
    secret=base64.b32encode(b'12345678901234567890').decode();now=1200
    code=otp(secret,40)
    assert totp_counter(secret,code,-1,now)==40
    assert totp_counter(secret,code,40,now) is None
    assert totp_counter(secret,otp(secret,38),-1,now) is None
    assert totp_counter(secret,'not-code',-1,now) is None

def test_secrets_are_encrypted_and_context_bound():
    v=Vault(Fernet.generate_key().decode());sealed=v.seal('agency-a',{'secret':'never plaintext'})
    assert 'never plaintext' not in sealed
    assert v.open('agency-a',sealed)['secret']=='never plaintext'
    with pytest.raises(ValueError):v.open('agency-b',sealed)

def test_pre_mfa_session_cannot_access_business_data(app):
    c=TestClient(app,base_url=ORIGIN)
    r=request(c,'POST','/api/auth/register',{'agency':'A','name':'Alice','email':'a@b.example','password':PASSWORD})
    assert r.status_code==201
    assert c.get('/api/dashboard').status_code==401
    assert c.get('/api/records/contacts').status_code==401
    assert c.get('/api/integrations').status_code==401
    assert c.get('/api/auth/enrolment').status_code==200

def test_unauthenticated_and_origin_csrf_boundaries(app,owner):
    anonymous=TestClient(app,base_url=ORIGIN)
    assert anonymous.get('/api/dashboard').status_code==401
    r=owner.post('/api/tasks',json={'title':'CSRF attack'},headers={'Origin':'https://evil.example'})
    assert r.status_code==403
    assert request(owner,'POST','/api/tasks',{'title':'No csrf'},csrf=False).status_code==403
    r=request(owner,'POST','/api/tasks',{'title':'Valid task'})
    assert r.status_code==200,r.text
    h=owner.get('/api/dashboard').headers
    assert h['cache-control']=='no-store' and h['x-frame-options']=='DENY'
    assert "script-src 'self'" in h['content-security-policy']

def test_session_cookie_and_password_not_plaintext(app,owner):
    u=app.state.store.one('SELECT * FROM users WHERE email=?',(owner.email,))
    assert u['password_hash'].startswith('$argon2id$') and PASSWORD not in u['password_hash']
    assert owner.secret not in u['totp_secret']
    raw=owner.cookies.get('agency_session')
    assert not app.state.store.one('SELECT * FROM sessions WHERE token_hash=?',(raw,))
    assert app.state.store.one('SELECT * FROM sessions WHERE token_hash=?',(digest(raw),))
    r=request(owner,'POST','/api/auth/login',{'email':owner.email,'password':PASSWORD})
    cookie=r.headers['set-cookie'].lower()
    assert 'httponly' in cookie and 'samesite=lax' in cookie and 'path=/api' in cookie

def test_recovery_code_is_one_use_and_full_session_rotates(app,owner):
    old=owner.cookies.get('agency_session');code=owner.recovery[0]
    request(owner,'POST','/api/auth/logout')
    assert request(owner,'POST','/api/auth/login',{'email':owner.email,'password':PASSWORD}).status_code==200
    pre=owner.cookies.get('agency_session')
    assert request(owner,'POST','/api/auth/mfa',{'code':code}).status_code==200
    full=owner.cookies.get('agency_session')
    assert len({old,pre,full})==3
    request(owner,'POST','/api/auth/logout')
    request(owner,'POST','/api/auth/login',{'email':owner.email,'password':PASSWORD})
    assert request(owner,'POST','/api/auth/mfa',{'code':code}).status_code==400
    assert owner.get('/api/dashboard').status_code==401

def test_recent_mfa_required_for_credentials(app,owner):
    app.state.store.execute('UPDATE sessions SET mfa_at=?',(time.time()-601,))
    values={'email':'api@rex.example','password':'test-private-rex','account_id':'100'}
    assert request(owner,'PUT','/api/integrations/rex',{'values':values}).status_code==403
    assert request(owner,'POST','/api/auth/step-up',{'code':owner.recovery[0]}).status_code==200
    assert request(owner,'PUT','/api/integrations/rex',{'values':values}).status_code==200

def test_cross_tenant_record_search_export_and_assignment_denied(app,owner):
    second=register(app,'second@other.example','Other Agency')
    r=request(owner,'POST','/api/tasks',{'title':'PRIVATE-AGENCY-ALPHA'});task=r.json()['id']
    assert second.get('/api/record/tasks/'+task).status_code==404
    assert request(second,'PATCH','/api/tasks/'+task,{'status':'Done'}).status_code==404
    assert second.get('/api/search?q=PRIVATE-AGENCY-ALPHA').json()['results']==[]
    assert 'PRIVATE-AGENCY-ALPHA' not in second.get('/api/export/tasks').text
    assert request(owner,'POST','/api/tasks',{'title':'Invalid assignment','assigned_to':second.user['id']}).status_code==400
    assert request(second,'PATCH','/api/team/'+owner.user['id'],{'role':'viewer','active':False}).status_code==404
    # Untrusted tenant selector fields cannot be submitted.
    assert request(second,'POST','/api/tasks',{'title':'Injected tenant','tenant_id':'fake'}).status_code==422

@pytest.mark.parametrize('role,allowed,denied',[('agent','contacts','invoices'),('property_manager','rentals','contacts'),('finance','invoices','contacts'),('viewer','listings','contacts')])
def test_roles_enforced_on_api_not_only_ui(app,owner,role,allowed,denied):
    member=add_member(app,owner,role)
    assert member.get('/api/records/'+allowed).status_code==200
    assert member.get('/api/records/'+denied).status_code==403
    assert member.get('/api/export/'+denied).status_code==403
    assert member.get('/api/team').status_code==403
    assert denied not in member.get('/api/dashboard').json()['modules']
    if role!='viewer':
        catalog=member.get('/api/integrations').json()['integrations']
        assert [c['id'] for c in catalog]==['microsoft','google']
        assert request(member,'PUT','/api/integrations/rex',{'values':{}}).status_code==403

def test_member_deactivation_revokes_existing_sessions(app,owner):
    member=add_member(app,owner)
    assert request(owner,'PATCH','/api/team/'+member.user['id'],{'role':'agent','active':False}).status_code==200
    assert member.get('/api/dashboard').status_code==401

def test_email_bound_one_use_invitation(app,owner):
    r=request(owner,'POST','/api/team/invite',{'email':'invite@agency.example','role':'finance'})
    token=r.json()['url'].split('token=')[1]
    c=TestClient(app,base_url=ORIGIN)
    bad=request(c,'POST','/api/auth/register',{'name':'Wrong','email':'wrong@agency.example','password':PASSWORD,'invite_token':token})
    assert bad.status_code==400
    member=register(app,'invite@agency.example',invite=token)
    assert member.user['role']=='finance' and member.user['agency']==owner.user['agency']
    assert c.get('/api/auth/invitation?token='+token).status_code==404

def test_rate_limit_is_persistent(app):
    from fastapi import HTTPException
    for _ in range(3):check_rate(app.state.store,'test-bucket',3,300)
    with pytest.raises(HTTPException) as e:check_rate(app.state.store,'test-bucket',3,300)
    assert e.value.status_code==429

def test_credentials_redacted_from_api_audit_and_at_rest(app,owner):
    secret='PRIVATE-KEY-DO-NOT-RETURN'
    r=request(owner,'PUT','/api/integrations/vaultre',{'values':{'api_key':secret,'access_token':'ACCESS-TOKEN-DO-NOT-RETURN'}})
    assert r.status_code==200
    for endpoint in ['/api/integrations','/api/audit','/api/auth/session','/api/search?q=PRIVATE']:
        assert secret not in owner.get(endpoint).text
    c=app.state.store.one('SELECT * FROM connections WHERE provider=?',('vaultre',))
    assert secret not in c['credentials']

@pytest.mark.parametrize('provider',['propertyme','propertytree','agentbox'])
def test_unimplemented_connectors_cannot_collect_credentials(owner,provider):
    assert request(owner,'PUT','/api/integrations/'+provider,{'values':{}}).status_code==422

def test_csv_formula_escape_and_no_external_task_mutation(owner):
    assert request(owner,'POST','/api/tasks',{'title':'=HYPERLINK("evil")'}).status_code==200
    csv=owner.get('/api/export/tasks').text
    assert "'=HYPERLINK" in csv and 'local' in csv
    assert request(owner,'PATCH','/api/tasks/demo-tasks-1',{'status':'Done'}).status_code==404

def test_disable_samples_explicitly(owner):
    r=request(owner,'PUT','/api/settings',{'demo_enabled':False,'sources':{}})
    assert r.status_code==200
    data=owner.get('/api/records/listings').json()
    assert data['mode']=='unavailable' and data['rows']==[]
    assert owner.get('/api/dashboard').json()['chart'] is None
