"""v05 pilot tests: synthetic provider traffic only, real adapters/backend."""
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.connectors import Engine, ConnectorError, auth_url
from app.provision import bootstrap_testing_account
from app.services import conn_context
from conftest import ORIGIN, request, register, add_member

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from run import local_address

SECRET='SYNTHETIC-SECRET-NEVER-LOG-THIS'
VALUES={'client_id':'TEST-CLIENT','directory_id':'TEST-DIRECTORY','client_secret':SECRET}

def event(id='event-1',title='TEST - CircleLogic inspection',start=None,end=None,**kwargs):
    now=datetime.now(timezone.utc)
    return {'id':id,'subject':title,'start':{'dateTime':start or (now+timedelta(days=1)).isoformat(),'timeZone':'UTC'},
            'end':{'dateTime':end or (now+timedelta(days=1,hours=1)).isoformat(),'timeZone':'UTC'},
            'isCancelled':False,'isAllDay':False,'location':{'displayName':'TEST location'},**kwargs}

class GraphFixture:
    def __init__(self):
        self.calls=[];self.events=[];self.token_error=None;self.graph_errors=[];self.page2=None;self.expires=3600
    def __call__(self,r):
        self.calls.append(r)
        if r.url.host=='login.microsoftonline.com':
            assert r.method=='POST'
            data=parse_qs(r.content.decode())
            assert data['client_secret']==[SECRET]
            if self.token_error:
                return httpx.Response(400,json=self.token_error)
            return httpx.Response(200,json={'access_token':'SYNTHETIC-ACCESS-'+str(len(self.calls)),
                'refresh_token':'SYNTHETIC-REFRESH','expires_in':self.expires})
        assert r.url.host=='graph.microsoft.com'
        assert r.method=='GET'
        assert r.url.path=='/v1.0/me/calendar/calendarView'
        assert 'Bearer SYNTHETIC' in r.headers['Authorization']
        if self.graph_errors:
            code=self.graph_errors.pop(0)
            if code!=200:return httpx.Response(code,json={'error':{'message':'PRIVATE-RESPONSE-NOT-FOR-LOGS'}})
        if self.page2 is not None and '$skiptoken' in r.url.params:
            return httpx.Response(200,json={'value':self.page2})
        body={'value':self.events}
        if self.page2 is not None:body['@odata.nextLink']='https://graph.microsoft.com/v1.0/me/calendar/calendarView?$skiptoken=next'
        return httpx.Response(200,json=body)

@pytest.fixture
def pilot(tmp_path):
    s=Settings(tmp_path,ORIGIN,'test',Fernet.generate_key().decode(),True,'')
    feed=GraphFixture()
    app=create_app(s,engine_factory=lambda:Engine(transport=httpx.MockTransport(feed)))
    app.state.feed=feed
    return app

@pytest.fixture
def pilot_owner(pilot):return register(pilot)

def save(c):
    r=request(c,'PUT','/api/integrations/microsoft',{'values':VALUES})
    assert r.status_code==200,r.text

def authorise(c):
    save(c)
    r=request(c,'POST','/api/integrations/microsoft/authorise')
    assert r.status_code==200,r.text
    params=parse_qs(urlparse(r.json()['url']).query)
    state=params['state'][0]
    return c.get('/api/oauth/microsoft/callback?state='+state+'&code=SYNTHETIC-CODE',follow_redirects=False)

def diag(c):return c.get('/api/integrations/microsoft/diagnostics').json()
def sync(c):return request(c,'POST','/api/integrations/microsoft/sync')

def test_readiness_requires_full_mfa(pilot):
    c=TestClient(pilot,base_url=ORIGIN)
    assert c.get('/api/pilot/readiness').status_code==401
    r=request(c,'POST','/api/auth/register',{'agency':'A','name':'Owner','email':'a@test.example','password':'long-private-password'})
    assert r.status_code==201
    assert c.get('/api/pilot/readiness').status_code==401
    assert c.get('/api/integrations/microsoft/diagnostics').status_code==401

def test_runtime_checks_do_not_make_provider_requests(pilot,pilot_owner):
    r=pilot_owner.get('/api/pilot/readiness')
    assert r.status_code==200
    d=r.json()
    assert d['version']=='0.7.0' and d['backend_running'] and d['database_available'] and d['vault_roundtrip_ok']
    assert d['microsoft_callback']==ORIGIN+'/api/oauth/microsoft/callback'
    assert d['provider_requests_made'] is False and not pilot.state.feed.calls
    assert d['testing_workspace'] is False

def test_known_testing_workspace_is_flagged(pilot):
    from app.security import otp
    bootstrap_testing_account(pilot.state.settings,pilot.state.store)
    c=TestClient(pilot,base_url=ORIGIN)
    assert request(c,'POST','/api/auth/login',{'username':'testing123','password':'testing12345'}).status_code==200
    secret=c.get('/api/auth/enrolment').json()['secret']
    assert request(c,'POST','/api/auth/mfa',{'code':otp(secret,int(time.time()//30))}).status_code==200
    d=c.get('/api/pilot/readiness').json()
    assert d['testing_workspace'] and 'CREATE-PRIVATE-WORKSPACE' in d['warning']

def test_diagnostics_progress_is_not_a_fake_connection(pilot,pilot_owner):
    assert diag(pilot_owner)['next_action']=='save_credentials'
    save(pilot_owner)
    d=diag(pilot_owner)
    assert d['next_action']=='authorise' and not d['authorisation_present'] and d['credentials_saved']
    assert d['status']=='configured' and d['last_success'] is None
    assert not pilot.state.feed.calls

def test_diagnostic_payload_never_returns_secrets(pilot,pilot_owner):
    authorise(pilot_owner)
    result=pilot_owner.get('/api/integrations/microsoft/diagnostics')
    for secret in [SECRET,'TEST-CLIENT','TEST-DIRECTORY','SYNTHETIC-ACCESS','SYNTHETIC-REFRESH','SYNTHETIC-CODE']:
        assert secret not in result.text
    d=result.json()
    assert d['next_action']=='sync' and d['authorisation_present'] and d['refresh_available']
    assert d['snapshots']==[]

def test_pkce_and_account_selection_are_explicit():
    url=auth_url('microsoft',VALUES,ORIGIN+'/api/oauth/microsoft/callback','S','VERIFIER')
    p=parse_qs(urlparse(url).query)
    assert p['prompt']==['select_account'] and p['code_challenge_method']==['S256']
    assert set(p['scope'][0].split())=={'offline_access','Calendars.ReadBasic'}
    assert SECRET not in url

def test_real_adapter_import_update_delete_and_no_duplicates(pilot,pilot_owner):
    authorise(pilot_owner)
    pilot.state.feed.events=[event()]
    assert sync(pilot_owner).json()['counts']=={'calendar':1}
    assert sync(pilot_owner).json()['counts']=={'calendar':1}
    rows=pilot_owner.get('/api/brain/dashboard').json()['calendar']['rows']
    assert len(rows)==1 and rows[0]['title']=='TEST - CircleLogic inspection'
    pilot.state.feed.events=[event(title='TEST - Updated appointment')]
    assert sync(pilot_owner).status_code==200
    rows=pilot_owner.get('/api/brain/dashboard').json()['calendar']['rows']
    assert len(rows)==1 and rows[0]['title']=='TEST - Updated appointment'
    pilot.state.feed.events=[]
    assert sync(pilot_owner).status_code==200
    data=pilot_owner.get('/api/brain/dashboard').json()['calendar']
    assert data['total']==0 and data['rows']==[] and data['mode']=='live'

def test_graph_request_is_read_only_limited_and_utc(pilot,pilot_owner):
    authorise(pilot_owner);assert sync(pilot_owner).status_code==200
    graph=[r for r in pilot.state.feed.calls if r.url.host=='graph.microsoft.com'][0]
    assert graph.method=='GET' and graph.headers['Prefer']=='outlook.timezone="UTC"'
    assert 'body' not in graph.url.params['$select'] and 'attendees' not in graph.url.params['$select']
    assert 'isAllDay' in graph.url.params['$select']
    start=datetime.fromisoformat(graph.url.params['startDateTime'].replace('Z','+00:00'))
    end=datetime.fromisoformat(graph.url.params['endDateTime'].replace('Z','+00:00'))
    assert end-start==timedelta(days=30)

def test_all_day_in_progress_kept_but_cancelled_and_past_hidden(pilot,pilot_owner):
    now=datetime.now(timezone.utc)
    pilot.state.feed.events=[event(id='all',isAllDay=True,start=(now-timedelta(hours=2)).isoformat(),end=(now+timedelta(hours=20)).isoformat()),
        event(id='cancel',isCancelled=True),event(id='past',start=(now-timedelta(days=2)).isoformat(),end=(now-timedelta(days=1)).isoformat())]
    authorise(pilot_owner);assert sync(pilot_owner).status_code==200
    rows=pilot_owner.get('/api/brain/dashboard').json()['calendar']['rows']
    assert len(rows)==1 and rows[0]['external_id']=='all' and rows[0]['all_day'] is True

def test_paged_graph_response_imports_both_pages(pilot,pilot_owner):
    pilot.state.feed.events=[event(id='page1')];pilot.state.feed.page2=[event(id='page2')]
    authorise(pilot_owner);assert sync(pilot_owner).json()['counts']=={'calendar':2}
    assert len(pilot_owner.get('/api/brain/dashboard').json()['calendar']['rows'])==2

def test_early_token_rejection_refreshes_once_and_saves_rotation(pilot,pilot_owner):
    authorise(pilot_owner)
    pilot.state.feed.events=[event()];pilot.state.feed.graph_errors=[401,200]
    assert sync(pilot_owner).status_code==200
    tokens=[r for r in pilot.state.feed.calls if r.url.host=='login.microsoftonline.com']
    assert len(tokens)==2 and parse_qs(tokens[-1].content.decode())['grant_type']==['refresh_token']
    c=pilot.state.store.one("SELECT * FROM connections WHERE provider='microsoft'")
    credentials=pilot.state.vault.open(conn_context(c['tenant_id'],'microsoft',c['owner_id']),c['credentials'])
    assert credentials['access_token'].startswith('SYNTHETIC-ACCESS') and c['status']=='connected'

def test_repeated_401_does_not_loop_or_destroy_old_snapshot(pilot,pilot_owner):
    authorise(pilot_owner);pilot.state.feed.events=[event()];assert sync(pilot_owner).status_code==200
    pilot.state.feed.graph_errors=[401,401]
    assert sync(pilot_owner).status_code==502
    token_calls=[r for r in pilot.state.feed.calls if r.url.host=='login.microsoftonline.com']
    assert len(token_calls)==2
    data=pilot_owner.get('/api/brain/dashboard').json()['calendar']
    assert data['mode']=='stale' and len(data['rows'])==1
    assert 'PRIVATE-RESPONSE' not in json.dumps(diag(pilot_owner))

def test_403_does_not_refresh_or_expose_provider_response(pilot,pilot_owner):
    authorise(pilot_owner);pilot.state.feed.graph_errors=[403]
    r=sync(pilot_owner)
    assert r.status_code==502 and 'PRIVATE-RESPONSE' not in r.text
    assert len([r for r in pilot.state.feed.calls if r.url.host=='login.microsoftonline.com'])==1

@pytest.mark.parametrize('code,message',[(7000215,'VALUE'),(7000222,'expired'),(700016,'directory'),(50011,'redirect'),(65001,'consent'),(70011,'scope')])
def test_microsoft_errors_are_actionable_and_redacted(pilot,pilot_owner,code,message):
    pilot.state.feed.token_error={'error_codes':[code],'error_description':'LEAK '+SECRET,'private':'do-not-show'}
    r=authorise(pilot_owner)
    assert r.status_code==303 and 'oauth=failed' in r.headers['location']
    d=diag(pilot_owner)
    assert message.lower() in d['last_error'].lower() and str(code) in d['last_error']
    assert SECRET not in json.dumps(d) and 'do-not-show' not in json.dumps(d)
    assert not d['authorisation_present']

def test_unknown_error_is_not_reflected(pilot,pilot_owner):
    pilot.state.feed.token_error={'error_codes':[999999],'error_description':SECRET}
    authorise(pilot_owner)
    d=diag(pilot_owner)
    assert 'Microsoft refused' in d['last_error'] and SECRET not in json.dumps(d)

def test_expired_token_without_refresh_needs_reauthorisation(pilot,pilot_owner):
    authorise(pilot_owner)
    c=pilot.state.store.one("SELECT * FROM connections WHERE provider='microsoft'")
    ctx=conn_context(c['tenant_id'],'microsoft',c['owner_id'])
    creds=pilot.state.vault.open(ctx,c['credentials']);creds.pop('refresh_token');creds['expires_at']=0
    pilot.state.store.execute('UPDATE connections SET credentials=? WHERE id=?',(pilot.state.vault.seal(ctx,creds),c['id']))
    assert diag(pilot_owner)['next_action']=='authorise'

def test_private_diagnostics_do_not_cross_users_or_workspaces(pilot,pilot_owner):
    authorise(pilot_owner);pilot.state.feed.events=[event()];assert sync(pilot_owner).status_code==200
    member=add_member(pilot,pilot_owner)
    outsider=register(pilot,'different@test.example','Other workspace')
    for c in [member,outsider]:
        d=diag(c)
        assert not d['credentials_saved'] and d['snapshots']==[] and d['last_success'] is None
        assert c.get('/api/brain/dashboard').json()['calendar']['rows']==[]

def test_disconnect_clears_runtime_and_data(pilot,pilot_owner):
    authorise(pilot_owner);pilot.state.feed.events=[event()];assert sync(pilot_owner).status_code==200
    assert request(pilot_owner,'DELETE','/api/integrations/microsoft').status_code==200
    d=diag(pilot_owner)
    assert d['next_action']=='save_credentials' and not d['credentials_saved'] and d['snapshots']==[]
    assert pilot_owner.get('/api/brain/dashboard').json()['calendar']['rows']==[]

@pytest.mark.parametrize('provider',['agentbox','rpdata','proping'])
def test_unfinished_providers_do_not_accept_credentials(pilot,pilot_owner,provider):
    d=pilot_owner.get('/api/integrations/'+provider+'/diagnostics').json()
    assert d['next_action']=='connector_pending' and not d['implemented']
    assert request(pilot_owner,'PUT','/api/integrations/'+provider,{'values':VALUES}).status_code==422

def test_microsoft_directory_is_not_a_url(pilot,pilot_owner):
    r=request(pilot_owner,'PUT','/api/integrations/microsoft',{'values':{**VALUES,'directory_id':'https://evil.example/'}})
    assert r.status_code==400 and not pilot.state.feed.calls

@pytest.mark.parametrize('path',['/','/api/health','/api/auth/session','/api/brain/dashboard'])
def test_unexpected_host_rejected(pilot,path):
    c=TestClient(pilot,base_url='http://rebinding.example:8000')
    assert c.get(path).status_code==400

@pytest.mark.parametrize('origin',['http://0.0.0.0:8000','http://example.com:8000','https://localhost:8000','http://user:pass@localhost:8000','http://localhost:8000/wrong','http://localhost:8000?x=1','http://localhost:80'])
def test_local_launcher_rejects_remote_or_ambiguous_origin(origin):
    with pytest.raises(ValueError):local_address(origin)

def test_local_launcher_uses_matching_callback_port():
    assert local_address('http://localhost:8123')==('127.0.0.1',8123)

@pytest.mark.parametrize('lifetime',['broken',-10,float('inf')])
def test_malformed_token_metadata_fails_cleanly(pilot,pilot_owner,lifetime):
    pilot.state.feed.expires=lifetime
    # Nonfinite JSON is itself rejected by the HTTP fixture serializer. Use a string.
    if isinstance(lifetime,float):pilot.state.feed.expires=str(lifetime)
    r=authorise(pilot_owner)
    assert r.status_code==303 and 'failed' in r.headers['location']
    assert not diag(pilot_owner)['authorisation_present']


def test_validation_errors_do_not_reflect_request_secrets(pilot,pilot_owner):
    r=request(pilot_owner,'PUT','/api/integrations/microsoft',{'values':{'client_secret':{'secret':SECRET}}})
    assert r.status_code==422 and SECRET not in r.text and 'input' not in r.text
    r=request(pilot_owner,'POST','/api/auth/login',{'username':'a','password':{'raw':SECRET}})
    assert r.status_code==422 and SECRET not in r.text
