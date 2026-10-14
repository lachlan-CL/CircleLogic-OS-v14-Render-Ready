"""Paste-only intake: same auth, workspace isolation and vault as v05.

All identifiers and secrets below are synthetic test fixtures.
"""
import json
import time
from urllib.parse import parse_qs, urlparse
import httpx
import pytest
from fastapi.testclient import TestClient
from cryptography.fernet import Fernet
from app.config import Settings
from app.main import create_app
from app.connectors import Engine
from app.services import conn_context
from conftest import ORIGIN, request, register, add_member

MS = {'client_id':'11111111-2222-3333-4444-555555555555',
      'directory_id':'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'}
REA = {'client_id':'REA-SYNTHETIC-CLIENT','agency_id':'TEST-AGENCY'}
KEY = 'SYNTHETIC-NOT-A-REAL-KEY-v06'

def setup(c, provider='microsoft', values=None):
    return request(c,'PUT',f'/api/integrations/{provider}/setup',{'values':values or (MS if provider=='microsoft' else REA)})

def paste(c, key=KEY, provider='microsoft'):
    return request(c,'POST',f'/api/integrations/{provider}/key',{'key':key})

def active(app, c, provider='microsoft'):
    user=app.state.store.one('SELECT * FROM users WHERE id=?',(c.user['id'],))
    owner=user['id'] if provider=='microsoft' else ''
    row=app.state.store.one('SELECT * FROM connections WHERE tenant_id=? AND provider=? AND owner_id=?',
                            (user['tenant_id'],provider,owner))
    return row, app.state.vault.open(conn_context(user['tenant_id'],provider,owner),row['credentials']) if row and row['credentials'] else {}

def test_empty_setup_is_private_and_uncached(owner):
    r=owner.get('/api/integrations/microsoft/setup')
    assert r.status_code==200 and r.headers['cache-control']=='no-store'
    d=r.json()
    assert not d['ready'] and d['values']==dict.fromkeys(MS,'')
    assert all(x['key']!='client_secret' for x in d['fields'])
    assert d['callback']==ORIGIN+'/api/oauth/microsoft/callback'

def test_setup_is_encrypted_but_does_not_claim_connected(app,owner):
    assert setup(owner).status_code==200
    row=app.state.store.one('SELECT * FROM connection_setups')
    assert row and all(v not in row['payload'] for v in MS.values())
    assert not app.state.store.one('SELECT * FROM connections')
    assert not owner.get('/api/integrations/microsoft/diagnostics').json()['credentials_saved']
    audit=owner.get('/api/audit').text
    assert all(v not in audit for v in MS.values())

def test_key_without_ids_points_to_guide(app,owner):
    r=paste(owner)
    assert r.status_code==400 and 'Setup guide' in r.text and KEY not in r.text
    assert not app.state.store.one('SELECT * FROM connections')

@pytest.mark.parametrize('provider',['agentbox','rpdata','proping','vaultre'])
def test_unfinished_or_unsupported_sources_cannot_collect_keys(owner,provider):
    assert paste(owner,provider=provider).status_code==422
    assert owner.get(f'/api/integrations/{provider}/setup').status_code==422
    assert setup(owner,provider,MS).status_code==422

@pytest.mark.parametrize('key',['testing123','testing12345','123456',' Testing12345 ','{\"secret\":\"SENTINEL\"}','[\"SENTINEL\"]','SENTINEL\nSECOND','SENTINEL\tSECOND','\n\t '])
def test_bad_key_is_not_saved_or_echoed(app,owner,key):
    assert setup(owner).status_code==200
    r=paste(owner,key)
    assert r.status_code==400 and 'SENTINEL' not in r.text
    assert not app.state.store.one('SELECT * FROM connections')

@pytest.mark.parametrize('key',['', 'X'*16001, {'secret':'SENTINEL'}, ['SENTINEL'], None])
def test_wrong_key_type_or_size_redacted(owner,key):
    r=paste(owner,key)
    assert r.status_code==422 and 'SENTINEL' not in r.text

@pytest.mark.parametrize('ids',[
    {**MS,'client_id':'testing123'},
    {**MS,'client_id':'not-a-client-guid'},
    {**MS,'directory_id':'https://SENTINEL.invalid'},
    {**MS,'directory_id':'../SENTINEL'},
    {**MS,'directory_id':''},
    {**MS,'client_secret':'SENTINEL'},
    {**MS,'callback':'https://SENTINEL.invalid'},
    {'client_id':MS['client_id']},
])
def test_bad_ids_or_injected_secret_rejected(owner,ids):
    r=setup(owner,values=ids)
    assert r.status_code==400 and 'SENTINEL' not in r.text

def test_direct_paste_saved_only_on_backend(app,owner):
    assert setup(owner).status_code==200
    r=paste(owner,'  '+KEY+'  ')
    assert r.status_code==200 and r.json()['next']=='authorise' and KEY not in r.text
    row, values=active(app,owner)
    assert values=={**MS,'client_secret':KEY} and KEY not in row['credentials']
    assert row['status']=='configured'
    assert not app.state.store.one('SELECT * FROM connection_setups')
    for endpoint in ['setup','diagnostics']:
        out=owner.get('/api/integrations/microsoft/'+endpoint)
        assert KEY not in out.text
    assert KEY not in owner.get('/api/audit').text
    assert KEY not in owner.get('/api/brain/connections').text
    assert not owner.get('/api/integrations/microsoft/diagnostics').json()['authorisation_present']

def test_rea_single_secret_intake(app,owner):
    assert setup(owner,'rea').status_code==200
    r=paste(owner,provider='rea')
    assert r.status_code==200 and r.json()['next']=='sync'
    row, values=active(app,owner,'rea')
    assert values=={**REA,'client_secret':KEY} and row['status']=='configured'
    assert owner.get('/api/integrations/rea/setup').json()['callback'] is None

def test_v05_credentials_rotate_without_reentering_ids(app,owner):
    assert request(owner,'PUT','/api/integrations/microsoft',{'values':{**MS,'client_secret':'OLD-SYNTHETIC'}}).status_code==200
    assert owner.get('/api/integrations/microsoft/setup').json()['ready']
    assert paste(owner).status_code==200
    assert active(app,owner)[1]=={**MS,'client_secret':KEY}

def test_changing_setup_does_not_switch_active_connection_until_key_saved(app,owner):
    setup(owner);paste(owner)
    changed={**MS,'client_id':'99999999-2222-3333-4444-555555555555'}
    assert setup(owner,values=changed).status_code==200
    assert active(app,owner)[1]['client_id']==MS['client_id']
    assert paste(owner,'NEW-SYNTHETIC-KEY').status_code==200
    assert active(app,owner)[1]=={**changed,'client_secret':'NEW-SYNTHETIC-KEY'}

@pytest.mark.parametrize('save_first',[False,True])
def test_disconnect_erases_staged_ids_and_secrets(app,owner,save_first):
    setup(owner)
    if save_first:
        paste(owner);setup(owner)
    assert request(owner,'DELETE','/api/integrations/microsoft').status_code==200
    assert not app.state.store.one('SELECT * FROM connection_setups')
    assert not active(app,owner)[1]
    assert not owner.get('/api/integrations/microsoft/setup').json()['ready']

def test_legacy_full_save_clears_old_staged_setup(app,owner):
    setup(owner)
    other={**MS,'directory_id':'bbbbbbbb-bbbb-cccc-dddd-eeeeeeeeeeee','client_secret':KEY}
    assert request(owner,'PUT','/api/integrations/microsoft',{'values':other}).status_code==200
    assert not app.state.store.one('SELECT * FROM connection_setups')
    assert owner.get('/api/integrations/microsoft/setup').json()['values']['directory_id']=='bbbbbbbb-bbbb-cccc-dddd-eeeeeeeeeeee'

def test_workspace_and_user_isolation(app,owner):
    setup(owner);paste(owner)
    other=register(app,'other@different.example','Another agency')
    colleague=add_member(app,owner,'agent','colleague@same.example')
    for c in [other,colleague]:
        assert not c.get('/api/integrations/microsoft/setup').json()['ready']
        assert paste(c).status_code==400
    setup(owner,'rea');paste(owner,provider='rea')
    assert not other.get('/api/integrations/rea/setup').json()['ready']
    assert colleague.get('/api/integrations/rea/setup').status_code==403
    assert setup(colleague,'rea').status_code==403
    assert paste(colleague,provider='rea').status_code==403
    assert setup(colleague).status_code==200
    assert paste(colleague,'COLLEAGUE-KEY').status_code==200
    assert active(app,owner)[1]['client_secret']==KEY
    assert active(app,colleague)[1]['client_secret']=='COLLEAGUE-KEY'

def test_role_viewer_and_anonymous_are_rejected(app,owner):
    viewer=add_member(app,owner,'viewer','viewer@same.example')
    anonymous=TestClient(app,base_url=ORIGIN)
    for c,status in [(viewer,403),(anonymous,401)]:
        assert c.get('/api/integrations/microsoft/setup').status_code==status
        assert setup(c).status_code==status
        assert paste(c).status_code==status

def test_full_mfa_required(app):
    c=TestClient(app,base_url=ORIGIN)
    assert request(c,'POST','/api/auth/register',{'agency':'Example','name':'Person','email':'pre-mfa@example.invalid','password':'SYNTHETIC-PASSWORD-2026'}).status_code==201
    assert c.get('/api/integrations/microsoft/setup').status_code==401
    assert setup(c).status_code==401
    assert paste(c).status_code==401

def test_csrf_origin_and_reverification_still_required(app,owner):
    path='/api/integrations/microsoft/setup'
    assert request(owner,'PUT',path,{'values':MS},csrf=False).status_code==403
    assert owner.put(path,json={'values':MS},headers={'Origin':'https://bad.invalid'}).status_code==403
    setup(owner)
    assert request(owner,'POST','/api/integrations/microsoft/key',{'key':KEY},csrf=False).status_code==403
    app.state.store.execute('UPDATE sessions SET mfa_at=? WHERE user_id=?',(time.time()-1000,owner.user['id']))
    assert setup(owner).status_code==403
    assert paste(owner).status_code==403

def test_request_cannot_select_other_owner_or_workspace(owner):
    r=request(owner,'POST','/api/integrations/microsoft/key',{'key':KEY,'owner_id':'somebody-else'})
    assert r.status_code==422 and KEY not in r.text
    r=request(owner,'PUT','/api/integrations/microsoft/setup',{'values':MS,'tenant_id':'someone-else'})
    assert r.status_code==422

def test_deactivated_users_setup_removed(app,owner):
    colleague=add_member(app,owner,'agent','inactive@same.example')
    setup(colleague)
    assert request(owner,'PATCH','/api/team/'+colleague.user['id'],{'role':'agent','active':False}).status_code==200
    assert not app.state.store.one('SELECT * FROM connection_setups WHERE owner_id=?',(colleague.user['id'],))

def test_restart_preserves_login_mfa_ids_and_key(app,owner):
    setup(owner);paste(owner)
    settings=app.state.settings
    again=create_app(settings)
    assert again.state.store.one('SELECT mfa_enabled FROM users WHERE id=?',(owner.user['id'],))['mfa_enabled']==1
    assert active(again,owner)[1]=={**MS,'client_secret':KEY}

def test_pasted_key_drives_real_adapter_with_mock_microsoft(tmp_path):
    calls=[]
    def transport(req):
        calls.append(req)
        if req.url.host=='login.microsoftonline.com':
            assert 'client_secret='+KEY in req.content.decode()
            return httpx.Response(200,json={'access_token':'SYNTHETIC-TOKEN','refresh_token':'SYNTHETIC-REFRESH','expires_in':3600})
        assert req.url.host=='graph.microsoft.com' and req.method=='GET'
        return httpx.Response(200,json={'value':[]})
    settings=Settings(tmp_path,ORIGIN,'test',Fernet.generate_key().decode(),True,'')
    app=create_app(settings,engine_factory=lambda:Engine(transport=httpx.MockTransport(transport)))
    c=register(app)
    assert setup(c).status_code==200 and paste(c).status_code==200 and not calls
    r=request(c,'POST','/api/integrations/microsoft/authorise')
    assert r.status_code==200
    params=parse_qs(urlparse(r.json()['url']).query)
    assert params['client_id']==[MS['client_id']]
    assert c.get('/api/oauth/microsoft/callback?state='+params['state'][0]+'&code=SYNTHETIC',follow_redirects=False).status_code==303
    sync=request(c,'POST','/api/integrations/microsoft/sync')
    assert sync.status_code==200 and sync.json()['counts']['calendar']==0
    assert len(calls)>=2
