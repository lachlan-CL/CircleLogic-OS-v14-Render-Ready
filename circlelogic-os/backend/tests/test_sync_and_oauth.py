import json
import time
from urllib.parse import urlparse,parse_qs
import pytest
from fastapi.testclient import TestClient
from app.connectors import ConnectorError
from app.services import perform_sync,conn_context
from app.security import digest
from conftest import ORIGIN,request,register,add_member

class FakeEngine:
    result={'contacts':[{'external_id':'contact-1','title':'Private CRM Contact','status':'Contact'}],
            'listings':[{'external_id':'listing-1','title':'Private CRM Listing','status':'Available'}]}
    failure=None
    callback=None
    def sync(self,provider,creds,save):
        if self.callback:self.callback(creds,save)
        if self.failure:raise ConnectorError(self.failure)
        return self.result
    def exchange(self,provider,creds,**kwargs):
        assert kwargs.get('verifier')
        creds.update(access_token='unit-test-access',refresh_token='unit-test-refresh',expires_at=time.time()+3600)
        return creds
    def close(self):pass

@pytest.fixture
def sync_app(tmp_path):
    from app.config import Settings
    from app.main import create_app
    from cryptography.fernet import Fernet
    class Engine(FakeEngine):pass
    app=create_app(Settings(tmp_path,ORIGIN,'test',Fernet.generate_key().decode(),True,''),engine_factory=Engine)
    app.state.test_engine=Engine
    return app

@pytest.fixture
def sync_owner(sync_app):return register(sync_app)

def configure_rex(c):
    r=request(c,'PUT','/api/integrations/rex',{'values':{'email':'api@agency.example','password':'private-key-test-only','account_id':'123'}})
    assert r.status_code==200,r.text

def test_empty_state_switches_only_after_sync_not_credential_save(sync_app,sync_owner):
    configure_rex(sync_owner)
    assert sync_owner.get('/api/records/contacts').json()['mode']=='unavailable'
    r=request(sync_owner,'POST','/api/integrations/rex/sync')
    assert r.status_code==200,r.text
    data=sync_owner.get('/api/records/contacts').json()
    assert data['mode']=='live' and data['total']==1
    assert data['rows'][0]['title']=='Private CRM Contact'
    assert sync_owner.get('/api/records/invoices').json()['mode']=='unavailable'
    assert sync_owner.get('/api/dashboard').json()['mode']=='workspace'
    assert sync_owner.get('/api/dashboard').json()['chart'] is None

def test_successful_zero_is_live_empty_never_sample(sync_app,sync_owner):
    configure_rex(sync_owner);sync_app.state.test_engine.result={'contacts':[],'listings':[]}
    assert request(sync_owner,'POST','/api/integrations/rex/sync').status_code==200
    d=sync_owner.get('/api/records/listings').json()
    assert d['mode']=='live' and d['rows']==[] and d['total']==0

@pytest.mark.parametrize('bad_result',[{'contacts':[]},{'contacts':[{'title':'Missing id'}],'listings':[]},{'contacts':[{'external_id':'1'},{'external_id':'1'}],'listings':[]}])
def test_invalid_partial_sync_preserves_previous_snapshot(sync_app,sync_owner,bad_result):
    configure_rex(sync_owner)
    assert request(sync_owner,'POST','/api/integrations/rex/sync').status_code==200
    sync_app.state.test_engine.result=bad_result
    assert request(sync_owner,'POST','/api/integrations/rex/sync').status_code==502
    d=sync_owner.get('/api/records/contacts').json()
    assert d['mode']=='stale' and d['rows'][0]['title']=='Private CRM Contact'

def test_failed_sync_does_not_replace_live_with_sample(sync_app,sync_owner):
    configure_rex(sync_owner);request(sync_owner,'POST','/api/integrations/rex/sync')
    sync_app.state.test_engine.failure='Provider access was refused.'
    assert request(sync_owner,'POST','/api/integrations/rex/sync').status_code==502
    d=sync_owner.get('/api/records/listings').json()
    assert d['mode']=='stale' and d['total']==1

def test_expired_freshness_is_stale(sync_app,sync_owner):
    configure_rex(sync_owner);request(sync_owner,'POST','/api/integrations/rex/sync')
    sync_app.state.store.execute('UPDATE snapshots SET synced_at=?',(time.time()-3601,))
    assert sync_owner.get('/api/records/listings').json()['mode']=='stale'

def test_disconnect_erases_secrets_and_data_and_never_falls_back_to_sample(sync_app,sync_owner):
    configure_rex(sync_owner);request(sync_owner,'POST','/api/integrations/rex/sync')
    assert request(sync_owner,'DELETE','/api/integrations/rex').status_code==200
    d=sync_owner.get('/api/records/listings').json()
    assert d['mode']=='unavailable' and d['total']==0
    c=sync_app.state.store.one('SELECT * FROM connections WHERE provider=?',('rex',))
    assert c['credentials'] is None
    assert not sync_app.state.store.all('SELECT * FROM records WHERE connection_id=?',(c['id'],))

def test_disconnect_during_sync_discards_result(sync_app,sync_owner):
    configure_rex(sync_owner)
    store=sync_app.state.store
    def callback(self,creds,save):
        store.execute("UPDATE connections SET credentials=NULL,revision=revision+1,status='disconnected',lease_token=NULL WHERE provider='rex'")
    sync_app.state.test_engine.callback=callback
    assert request(sync_owner,'POST','/api/integrations/rex/sync').status_code==502
    assert not store.all('SELECT * FROM records')

def test_duplicate_concurrent_sync_rejected(sync_app,sync_owner):
    configure_rex(sync_owner)
    sync_app.state.store.execute('UPDATE connections SET lease_until=?',(time.time()+300,))
    assert request(sync_owner,'POST','/api/integrations/rex/sync').status_code==502

def test_primary_crm_does_not_merge_sources(sync_app,sync_owner):
    configure_rex(sync_owner);request(sync_owner,'POST','/api/integrations/rex/sync')
    request(sync_owner,'PUT','/api/settings',{'demo_enabled':False,'sources':{'contacts':'vaultre','listings':'vaultre'}})
    d=sync_owner.get('/api/records/contacts').json()
    assert d['mode']=='unavailable' and d['total']==0

def configure_oauth(c,provider='microsoft'):
    values={'client_id':'test-client','client_secret':'test-secret','directory_id':'test-directory'} if provider=='microsoft' else {'client_id':'x-client','client_secret':'x-secret','tenant_id':'x-org'}
    r=request(c,'PUT','/api/integrations/'+provider,{'values':values})
    assert r.status_code==200,r.text
    r=request(c,'POST','/api/integrations/'+provider+'/authorise')
    assert r.status_code==200,r.text
    return parse_qs(urlparse(r.json()['url']).query)

def test_oauth_pkce_session_binding_single_use_and_no_premature_live(sync_app,sync_owner):
    params=configure_oauth(sync_owner)
    assert params['code_challenge_method']==['S256']
    assert params['redirect_uri']==[ORIGIN+'/api/oauth/microsoft/callback']
    state=params['state'][0]
    stranger=register(sync_app,'stranger@other.example','Other')
    callback='/api/oauth/microsoft/callback?state='+state+'&code=test-code'
    assert stranger.get(callback).status_code==400
    r=sync_owner.get(callback,follow_redirects=False)
    assert r.status_code==303 and 'success' in r.headers['location']
    assert sync_owner.get(callback).status_code==400
    c=sync_app.state.store.one('SELECT * FROM connections WHERE provider=?',('microsoft',))
    assert c['status']=='authorised' and c['last_success'] is None
    assert sync_owner.get('/api/records/messages').json()['mode']=='unavailable'

def test_oauth_reconfiguration_invalidates_state(sync_app,sync_owner):
    state=configure_oauth(sync_owner)['state'][0]
    configure_oauth(sync_owner)
    r=sync_owner.get('/api/oauth/microsoft/callback?state='+state+'&code=test-code')
    assert r.status_code==400

def test_oauth_denial_consumes_state_without_credentials(sync_app,sync_owner):
    state=configure_oauth(sync_owner)['state'][0]
    url='/api/oauth/microsoft/callback?state='+state+'&error=access_denied'
    r=sync_owner.get(url,follow_redirects=False)
    assert r.status_code==303 and 'denied' in r.headers['location']
    assert sync_owner.get(url).status_code==400

def test_private_microsoft_calendar_not_visible_to_same_agency_owner(sync_app,sync_owner):
    member=add_member(sync_app,sync_owner)
    state=configure_oauth(member)['state'][0]
    member.get('/api/oauth/microsoft/callback?state='+state+'&code=test-code',follow_redirects=False)
    sync_app.state.test_engine.result={'calendar':[{'external_id':'event-1','title':'PRIVATE-MEMBER-EVENT','status':'Scheduled'}]}
    assert request(member,'POST','/api/integrations/microsoft/sync').status_code==200
    assert member.get('/api/records/calendar').json()['mode']=='live'
    assert 'PRIVATE-MEMBER-EVENT' not in sync_owner.get('/api/records/calendar').text
    assert sync_owner.get('/api/search?q=PRIVATE-MEMBER-EVENT').json()['results']==[]
    assert 'PRIVATE-MEMBER-EVENT' not in sync_owner.get('/api/export/messages').text
