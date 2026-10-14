"""v07 Google Calendar connector tests using synthetic Google responses only."""
import json
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from cryptography.fernet import Fernet

from app.config import Settings
from app.connectors import Engine, auth_url
from app.main import create_app
from app.services import conn_context
from conftest import ORIGIN, request, register, add_member

CLIENT_ID='1234567890-synthetic-circlelogic.apps.googleusercontent.com'
CLIENT_SECRET='SYNTHETIC-GOOGLE-SECRET-NEVER-LOG'
SETUP={'client_id':CLIENT_ID}


def gevent(id='google-event-1', title='TEST - Google Calendar inspection', start=None, end=None, **kwargs):
    now=datetime.now(timezone.utc)
    return {
        'id':id,'summary':title,
        'start':{'dateTime':start or (now+timedelta(days=1)).isoformat(),'timeZone':'Australia/Sydney'},
        'end':{'dateTime':end or (now+timedelta(days=1,hours=1)).isoformat(),'timeZone':'Australia/Sydney'},
        'status':'confirmed','location':'TEST location',**kwargs
    }


class GoogleFixture:
    def __init__(self):
        self.calls=[];self.events=[];self.page2=None;self.token_error=None;self.api_errors=[];self.expires=3600
    def __call__(self,r):
        self.calls.append(r)
        if r.url.host=='oauth2.googleapis.com':
            assert r.method=='POST' and r.url.path=='/token'
            data=parse_qs(r.content.decode())
            assert data['client_id']==[CLIENT_ID] and data['client_secret']==[CLIENT_SECRET]
            if self.token_error:
                return httpx.Response(400,json=self.token_error)
            if data['grant_type']==['authorization_code']:
                assert data['code']==['SYNTHETIC-GOOGLE-CODE']
                body={'access_token':'SYNTHETIC-GOOGLE-ACCESS','refresh_token':'SYNTHETIC-GOOGLE-REFRESH','expires_in':self.expires,
                      'scope':'https://www.googleapis.com/auth/calendar.events.readonly','token_type':'Bearer'}
            else:
                assert data['grant_type']==['refresh_token'] and data['refresh_token']==['SYNTHETIC-GOOGLE-REFRESH']
                body={'access_token':'SYNTHETIC-GOOGLE-ACCESS-REFRESHED','expires_in':self.expires,'token_type':'Bearer'}
            return httpx.Response(200,json=body)
        assert r.url.host=='www.googleapis.com'
        assert r.method=='GET' and r.url.path=='/calendar/v3/calendars/primary/events'
        assert r.headers['Authorization'].startswith('Bearer SYNTHETIC-GOOGLE-ACCESS')
        if self.api_errors:
            code=self.api_errors.pop(0)
            if code!=200:return httpx.Response(code,json={'error':{'message':'PRIVATE-GOOGLE-RESPONSE'}})
        if r.url.params.get('pageToken')=='next':
            return httpx.Response(200,json={'items':self.page2 or []})
        body={'items':self.events}
        if self.page2 is not None:body['nextPageToken']='next'
        return httpx.Response(200,json=body)


@pytest.fixture
def google_app(tmp_path):
    feed=GoogleFixture()
    app=create_app(Settings(tmp_path,ORIGIN,'test',Fernet.generate_key().decode(),True,''),engine_factory=lambda:Engine(transport=httpx.MockTransport(feed)))
    app.state.google_feed=feed
    return app

@pytest.fixture
def google_owner(google_app):return register(google_app)


def save_google(c):
    r=request(c,'PUT','/api/integrations/google/setup',{'values':SETUP});assert r.status_code==200,r.text
    r=request(c,'POST','/api/integrations/google/key',{'key':CLIENT_SECRET});assert r.status_code==200,r.text


def authorise_google(c):
    save_google(c)
    r=request(c,'POST','/api/integrations/google/authorise');assert r.status_code==200,r.text
    url=r.json()['url'];q=parse_qs(urlparse(url).query)
    state=q['state'][0]
    return url,c.get('/api/oauth/google/callback?state='+state+'&code=SYNTHETIC-GOOGLE-CODE',follow_redirects=False)


def sync_google(c):return request(c,'POST','/api/integrations/google/sync')


def diag_google(c):return c.get('/api/integrations/google/diagnostics').json()


def test_google_setup_and_single_secret_paste_are_separate(google_app,google_owner):
    r=google_owner.get('/api/integrations/google/setup');assert r.status_code==200
    d=r.json();assert d['fields']==[{'key':'client_id','label':'Google OAuth client ID'}]
    assert d['callback']==ORIGIN+'/api/oauth/google/callback' and not d['ready']
    save_google(google_owner)
    row=google_app.state.store.one("SELECT * FROM connections WHERE provider='google'")
    creds=google_app.state.vault.open(conn_context(row['tenant_id'],'google',row['owner_id']),row['credentials'])
    assert creds=={'client_id':CLIENT_ID,'client_secret':CLIENT_SECRET}
    assert CLIENT_SECRET not in google_owner.get('/api/integrations/google/diagnostics').text


def test_google_client_id_validation(google_owner):
    bad=request(google_owner,'PUT','/api/integrations/google/setup',{'values':{'client_id':'not-a-google-client'}})
    assert bad.status_code==400 and 'OAuth client ID' in bad.text


def test_google_authorisation_url_is_offline_read_only_and_stateful(google_owner):
    save_google(google_owner)
    r=request(google_owner,'POST','/api/integrations/google/authorise');assert r.status_code==200
    u=urlparse(r.json()['url']);q=parse_qs(u.query)
    assert u.scheme=='https' and u.hostname=='accounts.google.com'
    assert q['client_id']==[CLIENT_ID]
    assert q['redirect_uri']==[ORIGIN+'/api/oauth/google/callback']
    assert q['scope']==['https://www.googleapis.com/auth/calendar.events.readonly']
    assert q['access_type']==['offline'] and q['include_granted_scopes']==['true']
    assert 'consent' in q['prompt'][0] and 'select_account' in q['prompt'][0]
    assert 'state' in q and CLIENT_SECRET not in r.json()['url']


def test_google_imports_primary_calendar_and_dashboard(google_app,google_owner):
    url,callback=authorise_google(google_owner)
    assert callback.status_code==303 and 'oauth=success&provider=google' in callback.headers['location']
    google_app.state.google_feed.events=[gevent()]
    r=sync_google(google_owner);assert r.status_code==200 and r.json()['counts']=={'calendar':1}
    request_call=[x for x in google_app.state.google_feed.calls if x.url.host=='www.googleapis.com'][0]
    assert request_call.url.path=='/calendar/v3/calendars/primary/events'
    assert request_call.url.params['singleEvents']=='true' and request_call.url.params['orderBy']=='startTime'
    assert request_call.url.params['timeZone']=='Australia/Sydney'
    assert 'attendees' not in request_call.url.params['fields'] and 'description' not in request_call.url.params['fields']
    cal=google_owner.get('/api/brain/dashboard').json()['calendar']
    assert cal['total']==1 and cal['sources']==['Google Calendar']
    assert cal['rows'][0]['title']=='TEST - Google Calendar inspection'
    assert cal['rows'][0]['calendar_source']=='Google Calendar'


def test_google_all_day_and_pagination(google_app,google_owner):
    tomorrow=(datetime.now(timezone.utc)+timedelta(days=1)).date()
    google_app.state.google_feed.events=[{'id':'all','summary':'TEST all day','start':{'date':tomorrow.isoformat()},'end':{'date':(tomorrow+timedelta(days=1)).isoformat()},'status':'confirmed'}]
    google_app.state.google_feed.page2=[gevent(id='page2')]
    authorise_google(google_owner);r=sync_google(google_owner)
    assert r.json()['counts']=={'calendar':2}
    rows=google_owner.get('/api/brain/dashboard').json()['calendar']['rows']
    assert len(rows)==2 and next(x for x in rows if x['external_id']=='all')['all_day'] is True


def test_google_401_refreshes_once_and_preserves_refresh_token(google_app,google_owner):
    authorise_google(google_owner);google_app.state.google_feed.events=[gevent()];google_app.state.google_feed.api_errors=[401,200]
    assert sync_google(google_owner).status_code==200
    token_calls=[x for x in google_app.state.google_feed.calls if x.url.host=='oauth2.googleapis.com']
    assert len(token_calls)==2 and parse_qs(token_calls[-1].content.decode())['grant_type']==['refresh_token']
    row=google_app.state.store.one("SELECT * FROM connections WHERE provider='google'")
    creds=google_app.state.vault.open(conn_context(row['tenant_id'],'google',row['owner_id']),row['credentials'])
    assert creds['access_token']=='SYNTHETIC-GOOGLE-ACCESS-REFRESHED' and creds['refresh_token']=='SYNTHETIC-GOOGLE-REFRESH'


def test_google_oauth_error_is_sanitised(google_app,google_owner):
    google_app.state.google_feed.token_error={'error':'invalid_client','error_description':'LEAK '+CLIENT_SECRET}
    url,callback=authorise_google(google_owner)
    assert callback.status_code==303 and 'oauth=failed&provider=google' in callback.headers['location']
    d=diag_google(google_owner)
    assert 'rejected' in d['last_error'].lower() and CLIENT_SECRET not in json.dumps(d) and 'LEAK' not in json.dumps(d)


def test_google_calendar_is_private_to_login_and_disconnects(google_app,google_owner):
    authorise_google(google_owner);google_app.state.google_feed.events=[gevent()];assert sync_google(google_owner).status_code==200
    member=add_member(google_app,google_owner)
    assert member.get('/api/brain/dashboard').json()['calendar']['rows']==[]
    assert request(google_owner,'DELETE','/api/integrations/google').status_code==200
    assert google_owner.get('/api/brain/dashboard').json()['calendar']['rows']==[]
    assert diag_google(google_owner)['next_action']=='save_credentials'
