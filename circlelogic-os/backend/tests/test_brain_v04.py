"""v04 acceptance tests. Provider results are synthetic fixtures, never live accounts."""
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.db import Store
from app.provision import bootstrap_testing_account, create_workspace, validate_username
from app.connectors import Engine, ConnectorError, oauth_spec
from app.security import PASSWORDS, otp
from conftest import ORIGIN, PASSWORD, request, register, add_member


class Feed:
    results = {}
    failure = False
    def sync(self,provider,creds,save):
        if self.failure: raise ConnectorError('Fixture provider unavailable.')
        return self.results[provider]
    def exchange(self,provider,creds,**kwargs):
        assert kwargs.get('verifier')
        return {**creds,'access_token':'SYNTHETIC_TOKEN','refresh_token':'SYNTHETIC_REFRESH','expires_at':time.time()+3600}
    def close(self): pass


@pytest.fixture
def brain_app(tmp_path):
    class LocalFeed(Feed):
        results={'rea':{'campaigns':[]}, 'microsoft':{'calendar':[]}}
        failure=False
    app=create_app(Settings(tmp_path,ORIGIN,'test',Fernet.generate_key().decode(),True,''),engine_factory=LocalFeed)
    app.state.feed=LocalFeed
    return app


@pytest.fixture
def brain_owner(brain_app):return register(brain_app)


def configure_rea(client):
    r=request(client,'PUT','/api/integrations/rea',{'values':{'client_id':'FIXTURE_CLIENT','client_secret':'FIXTURE_SECRET','agency_id':'OFFICE_A'}})
    assert r.status_code==200,r.text


def configure_calendar(client):
    r=request(client,'PUT','/api/integrations/microsoft',{'values':{'directory_id':'TENANT','client_id':'CLIENT','client_secret':'SYNTHETIC_SECRET'}})
    assert r.status_code==200,r.text
    r=request(client,'POST','/api/integrations/microsoft/authorise')
    state=parse_qs(urlparse(r.json()['url']).query)['state'][0]
    r=client.get('/api/oauth/microsoft/callback?state='+state+'&code=synthetic',follow_redirects=False)
    assert r.status_code==303,r.text


def sync(client,provider='rea'):
    return request(client,'POST','/api/integrations/'+provider+'/sync')


def dashboard(client):return client.get('/api/brain/dashboard').json()


def test_testing_bootstrap_is_idempotent_and_no_data(app):
    s=app.state.settings;store=app.state.store
    assert bootstrap_testing_account(s,store) is True
    u=store.one("SELECT * FROM users WHERE username='testing123'")
    assert PASSWORDS.verify(u['password_hash'],'testing12345')
    assert u['mfa_enabled']==0 and u['totp_secret'] is None
    assert not store.all('SELECT * FROM records') and not store.all('SELECT * FROM connections')
    assert bootstrap_testing_account(s,store) is False
    assert store.one("SELECT * FROM users WHERE username='testing123'")['id']==u['id']


def test_username_login_requires_real_mfa_before_dashboard(app):
    bootstrap_testing_account(app.state.settings,app.state.store)
    client=TestClient(app,base_url=ORIGIN)
    r=request(client,'POST','/api/auth/login',{'username':'TESTING123','password':'testing12345'})
    assert r.status_code==200 and r.json()['stage']=='enrol'
    for path in ['/api/brain/dashboard','/api/brain/connections']:
        assert client.get(path).status_code==401
    secret=client.get('/api/auth/enrolment').json()['secret']
    assert request(client,'POST','/api/auth/mfa',{'code':otp(secret,int(time.time()//30))}).status_code==200
    session=client.get('/api/auth/session').json()
    assert session['user']['username']=='testing123' and session['user']['agency']=='CircleLogic Testing'
    assert dashboard(client)['workspace_id']==session['user']['workspace_id']
    assert session['environment']=='test'


def test_testing_account_not_created_or_accepted_in_production(tmp_path):
    key=Fernet.generate_key().decode()
    prod=Settings(tmp_path,'https://brain.example','production',key,False,'')
    with pytest.raises(RuntimeError):bootstrap_testing_account(prod)
    dev=Settings(tmp_path,ORIGIN,'test',key,False,'')
    bootstrap_testing_account(dev)
    with pytest.raises(RuntimeError,match='testing account'):create_app(prod)


def test_operator_creates_separate_workspace_and_rejects_duplicate(app):
    bootstrap_testing_account(app.state.settings,app.state.store)
    args=dict(agency='Approved Customer',name='Owner',username='customer.owner',email='owner@customer.invalid',password=PASSWORD)
    row=create_workspace(app.state.store,**args)
    test=app.state.store.one("SELECT * FROM users WHERE username='testing123'")
    assert row['workspace_id']!=test['tenant_id']
    with pytest.raises(ValueError,match='already exists'):create_workspace(app.state.store,**args)


@pytest.mark.parametrize('username',['../agency','two users','ab','x@agency','x'*65])
def test_username_rejects_ambiguous_or_invalid_values(username):
    with pytest.raises(HTTPException):validate_username(username)


def test_customer_cannot_use_published_testing_username_or_short_password(app):
    for username,password in [('testing123',PASSWORD),('realcustomer','short')]:
        with pytest.raises(ValueError):
            create_workspace(app.state.store,agency='Agency',name='Owner',username=username,email='x@y.invalid',password=password)


def test_public_signup_off_by_default(tmp_path,monkeypatch):
    monkeypatch.setenv('DATA_DIR',str(tmp_path));monkeypatch.setenv('APP_ENV','development')
    monkeypatch.delenv('ALLOW_SIGNUP',raising=False);monkeypatch.delenv('PROVISION_TOKEN',raising=False)
    settings=Settings.load();assert not settings.allow_signup
    c=TestClient(create_app(settings),base_url=ORIGIN)
    assert request(c,'POST','/api/auth/register',{'agency':'Uninvited','name':'Test','email':'x@y.invalid','password':PASSWORD}).status_code==403


def test_six_sources_and_null_not_fake_zero(brain_owner):
    data=dashboard(brain_owner)
    assert len(data['metrics'])==5 and all(m['value'] is None and m['delta'] is None for m in data['metrics'])
    assert data['mode']=='empty'
    sources=brain_owner.get('/api/brain/connections').json()['connections']
    assert [c['id'] for c in sources]==['agentbox','rea','rpdata','proping','microsoft','google']
    assert all(c['status']=='not_connected' and not c['has_credentials'] for c in sources)
    assert all(data[key]['rows']==[] and data[key]['total'] is None for key in ['buyer_activity','market_activity','calendar'])


def test_synthetic_data_setting_is_refused(brain_owner):
    assert request(brain_owner,'PUT','/api/settings',{'demo_enabled':True,'sources':{}}).status_code==400
    assert dashboard(brain_owner)['mode']=='empty'


def test_v03_migration_disables_samples_but_preserves_user_and_data(app,owner):
    store=app.state.store
    assert request(owner,'POST','/api/tasks',{'title':'PRESERVE_EXISTING_CUSTOMER_TASK'}).status_code==200
    store.execute('UPDATE tenants SET settings=?',(json.dumps({'demo_enabled':True,'sources':{'listings':'rex'}}),))
    store.execute('DELETE FROM schema_version WHERE version=4')
    before=store.one('SELECT id,password_hash,totp_secret FROM users WHERE id=?',(owner.user['id'],))
    reopened=Store(app.state.settings.database)
    settings=json.loads(reopened.one('SELECT settings FROM tenants')['settings'])
    assert settings['demo_enabled'] is False and settings['sources']['listings']=='rex'
    assert reopened.one('SELECT id,password_hash,totp_secret FROM users WHERE id=?',(owner.user['id'],))==before
    assert 'PRESERVE_EXISTING_CUSTOMER_TASK' in reopened.one('SELECT payload FROM records')['payload']


@pytest.mark.parametrize('provider',['agentbox','rpdata','proping'])
def test_gated_sources_do_not_collect_secrets(brain_owner,provider):
    assert request(brain_owner,'PUT','/api/integrations/'+provider,{'values':{'api_key':'UNNEEDED_SECRET'}}).status_code==422


def test_saving_credentials_is_not_live_and_secret_is_not_returned(brain_app,brain_owner):
    configure_rea(brain_owner)
    assert dashboard(brain_owner)['buyer_activity']['total'] is None
    result=brain_owner.get('/api/brain/connections')
    rea=result.json()['connections'][1]
    assert rea['status']=='configured' and rea['has_credentials'] and rea['last_success'] is None
    assert 'FIXTURE_SECRET' not in result.text and 'FIXTURE_CLIENT' not in result.text
    stored=brain_app.state.store.one("SELECT credentials FROM connections WHERE provider='rea'")
    assert 'FIXTURE_SECRET' not in stored['credentials']


def test_successful_zero_is_connected_and_zero_not_unavailable(brain_owner):
    configure_rea(brain_owner);assert sync(brain_owner).status_code==200
    data=dashboard(brain_owner)
    assert data['buyer_activity']['total']==0 and data['buyer_activity']['mode']=='live'
    assert data['mode']=='workspace'
    assert data['metrics'][2]['value'] is None  # No buyer-score feed, even after a valid report import.


def test_real_report_snapshot_no_score_inference_and_failed_refresh_preserves(brain_app,brain_owner):
    configure_rea(brain_owner)
    brain_app.state.feed.results['rea']={'campaigns':[{'external_id':'one','title':'PRIVATE_OFFICE_A_REPORT','totals':{'page_views':2450,'email_enquiries':16,'saves':27}}]}
    assert sync(brain_owner).status_code==200
    data=dashboard(brain_owner)
    assert data['buyer_activity']['rows'][0]['totals']['page_views']==2450 and data['metrics'][2]['value'] is None
    brain_app.state.feed.failure=True
    assert sync(brain_owner).status_code==502
    data=dashboard(brain_owner)
    assert data['buyer_activity']['mode']=='stale' and data['buyer_activity']['total']==1
    assert 'PRIVATE_OFFICE_A_REPORT' in json.dumps(data)


def test_partial_report_rejected_without_replacing_snapshot(brain_app,brain_owner):
    configure_rea(brain_owner);assert sync(brain_owner).status_code==200
    brain_app.state.feed.results['rea']={'campaigns':[{'title':'NO_EXTERNAL_ID'}]}
    assert sync(brain_owner).status_code==502
    assert dashboard(brain_owner)['buyer_activity']['total']==0


def test_connection_and_report_isolation_ignores_tenant_query(brain_app,brain_owner):
    configure_rea(brain_owner)
    brain_app.state.feed.results['rea']={'campaigns':[{'external_id':'one','title':'PRIVATE_OFFICE_A_REPORT'}]}
    assert sync(brain_owner).status_code==200
    other=register(brain_app,'second@other.invalid','Other office')
    data=other.get('/api/brain/dashboard?tenant_id='+brain_owner.user['workspace_id']).json()
    assert data['mode']=='empty' and 'PRIVATE_OFFICE_A_REPORT' not in json.dumps(data)
    assert data['workspace_id']!=brain_owner.user['workspace_id']
    assert other.get('/api/brain/connections').json()['connections'][1]['status']=='not_connected'


def test_roles_cannot_read_restricted_report_or_credentials(brain_app,brain_owner):
    configure_rea(brain_owner)
    brain_app.state.feed.results['rea']={'campaigns':[{'external_id':'one','title':'RESTRICTED_REPORT'}]}
    assert sync(brain_owner).status_code==200
    viewer=add_member(brain_app,brain_owner,role='viewer',email='viewer@office.invalid')
    data=dashboard(viewer)
    assert 'RESTRICTED_REPORT' not in json.dumps(data) and data['buyer_activity']['mode']=='restricted'
    rea=viewer.get('/api/brain/connections').json()['connections'][1]
    assert not rea['manageable'] and not rea['has_credentials'] and rea['fields']==[]


def test_calendar_is_private_to_connecting_user_not_tenant_owner(brain_app,brain_owner):
    member=add_member(brain_app,brain_owner)
    configure_calendar(member)
    start=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()
    brain_app.state.feed.results['microsoft']={'calendar':[{'external_id':'one','title':'PRIVATE_MEMBER_APPOINTMENT','start':start,'timezone':'UTC'}]}
    assert sync(member,'microsoft').status_code==200
    assert dashboard(member)['calendar']['total']==1
    assert 'PRIVATE_MEMBER_APPOINTMENT' not in json.dumps(dashboard(brain_owner))
    assert dashboard(brain_owner)['calendar']['total'] is None


def test_calendar_excludes_cancelled_past_and_invalid_dates(brain_app,brain_owner):
    configure_calendar(brain_owner);now=datetime.now(timezone.utc)
    brain_app.state.feed.results['microsoft']={'calendar':[
        {'external_id':'1','title':'Future','start':(now+timedelta(days=1)).isoformat(),'timezone':'UTC'},
        {'external_id':'2','title':'Past','start':(now-timedelta(days=1)).isoformat(),'timezone':'UTC'},
        {'external_id':'3','title':'Cancelled','start':(now+timedelta(days=1)).isoformat(),'status':'Cancelled'},
        {'external_id':'4','title':'Invalid','start':'not-a-date'}]}
    assert sync(brain_owner,'microsoft').status_code==200
    assert [r['title'] for r in dashboard(brain_owner)['calendar']['rows']]==['Future']


def test_freshness_and_disconnect_purge(brain_app,brain_owner):
    configure_rea(brain_owner);assert sync(brain_owner).status_code==200
    brain_app.state.store.execute('UPDATE snapshots SET synced_at=?',(time.time()-3601,))
    brain_app.state.store.execute('UPDATE connections SET last_success=?',(time.time()-3601,))
    assert dashboard(brain_owner)['buyer_activity']['mode']=='stale'
    assert brain_owner.get('/api/brain/connections').json()['connections'][1]['status']=='stale'
    assert request(brain_owner,'DELETE','/api/integrations/rea').status_code==200
    assert not brain_app.state.store.all('SELECT * FROM snapshots')
    assert dashboard(brain_owner)['buyer_activity']['total'] is None


def test_calendar_permissions_read_only_and_no_mail():
    spec=oauth_spec('microsoft',{'directory_id':'TEST'})
    assert set(spec['scope'].split())=={'offline_access','Calendars.ReadBasic'}
    assert 'Mail' not in spec['scope'] and 'Write' not in spec['scope'] and spec['pkce']


def test_live_bundle_contains_no_design_fixtures():
    root=Path(__file__).resolve().parents[2]
    code='\n'.join(p.read_text() for p in (root/'frontend/src').glob('*.js'))
    assert '12 Oceanview Road' not in code and '8432' not in code
    assert not (root/'frontend/preview.html').exists()
    assert 'runtime.js' not in (root/'frontend/index.html').read_text()


def portal_fixture():
    return [{'portalName':'realestate_au','all':[{'metricName':'listingEvents','metricType':'sum','metricPeriods':[{'period':'all','metricValues':[{'name':'pageView','value':2400},{'name':'emailEnquiry','value':17},{'name':'listingSaved','value':0}]}]}],
             'daily':[{'metricName':'listingEvents','metricPeriods':[{'period':'2026-09-20','metricValues':[{'name':'pageView','value':99}]}]}]}]


def test_rea_metric_mapping_uses_totals_not_daily_and_keeps_true_zero():
    result=Engine.rea_totals(portal_fixture())
    assert result=={'page_views':2400,'email_enquiries':17,'saves':0}
    assert not any('buyer' in k or 'score' in k for k in result)


@pytest.mark.parametrize('payload',[None,{},[],[{'portalName':'another_portal'}]])
def test_rea_unknown_or_missing_metrics_stay_null(payload):
    assert all(v is None for v in Engine.rea_totals(payload).values())


def test_rea_ambiguous_duplicate_metrics_rejected():
    fixture=portal_fixture();fixture[0]['all'][0]['metricPeriods'][0]['metricValues'].append({'name':'pageView','value':3})
    with pytest.raises(ConnectorError):Engine.rea_totals(fixture)


def test_rea_rejects_wrong_agency_in_authorised_response():
    def handler(req):
        if req.url.path=='/oauth/token':return httpx.Response(200,json={'access_token':'SYNTHETIC'})
        return httpx.Response(200,json={'_embedded':{'items':[{'id':'x','listing':{'id':'x','agencyId':'WRONG_OFFICE'},'portalMetrics':portal_fixture()}]}})
    engine=Engine(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(ConnectorError,match='different agency'):engine.sync('rea',{'client_id':'C','client_secret':'S','agency_id':'OFFICE_A'})
    finally:engine.close()
