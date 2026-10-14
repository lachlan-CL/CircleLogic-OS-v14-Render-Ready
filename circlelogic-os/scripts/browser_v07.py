"""v07 Google Calendar browser checks.

The CircleLogic frontend is the real HTML/CSS/JS and the backend is a real
FastAPI TestClient. Google OAuth/token/calendar responses are synthetic. This
is not a live Google or native-browser networking test.
"""
import argparse
import base64
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import time
from urllib.parse import urlparse, parse_qs
import httpx
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.config import Settings
from app.main import create_app
from app.provision import create_workspace
from app.security import otp
from app.connectors import Engine

parser=argparse.ArgumentParser()
parser.add_argument('--output',default=str(ROOT/'docs/evidence-v07/ui'))
parser.add_argument('--chromium',default='/usr/bin/chromium')
args=parser.parse_args()
OUT=Path(args.output);OUT.mkdir(parents=True,exist_ok=True)
ORIGIN='http://localhost:8000';TEMP=tempfile.TemporaryDirectory()
CLIENT_ID='1234567890-syntheticcalendar.apps.googleusercontent.com'
CLIENT_SECRET='SYNTHETIC-GOOGLE-CLIENT-SECRET-NOT-REAL'

class GoogleFixture:
    events=[]
    fail=False
    token_calls=0
    calendar_calls=0
    def __call__(self,req):
        if req.url.host=='oauth2.googleapis.com':
            self.token_calls+=1
            return httpx.Response(200,json={
                'access_token':'SYNTHETIC-GOOGLE-TOKEN',
                'refresh_token':'SYNTHETIC-GOOGLE-REFRESH',
                'expires_in':3600,
                'token_type':'Bearer',
            })
        if req.url.host=='www.googleapis.com':
            self.calendar_calls+=1
            assert req.method=='GET'
            assert req.url.path=='/calendar/v3/calendars/primary/events'
            if self.fail:
                return httpx.Response(403,json={'error':{'message':'RAW_GOOGLE_ERROR_SENTINEL'}})
            return httpx.Response(200,json={'items':self.events})
        raise AssertionError('Unexpected synthetic upstream: '+str(req.url))

feed=GoogleFixture()
s=Settings(Path(TEMP.name),ORIGIN,'test',Fernet.generate_key().decode(),False,'')
app=create_app(s,engine_factory=lambda:Engine(transport=httpx.MockTransport(feed)))
create_workspace(app.state.store,agency='Private Google test',name='Test operator',username='google.tester',
                 email='google.tester@example.invalid',password='Synthetic-private-password-2026')
client=TestClient(app,base_url=ORIGIN)
checks=[];errors=[]

def check(name,condition=True):
    assert condition,name
    checks.append(name)
    print('PASS: '+name,flush=True)

def req(method,path,data=None):
    csrf=client.get('/api/auth/session').json().get('csrf','')
    return client.request(method,path,json=data or {},headers={'Origin':ORIGIN,'X-CSRF-Token':csrf,'Content-Type':'application/json'})

def load_app(page):
    def bridge(path,options):
        assert path.startswith('/api/'),path
        r=client.request(options.get('method','GET'),path,content=options.get('body'),headers={**options.get('headers',{}),'Origin':ORIGIN})
        return {'status':r.status_code,'body':r.text,'headers':{'Content-Type':r.headers.get('content-type','application/json')}}
    page.expose_function('testApiBridge',bridge)
    html=(ROOT/'frontend/index.html').read_text().replace(
        '<link rel="stylesheet" href="/src/styles.css?v=0.7.0">',
        '<style>'+(ROOT/'frontend/src/styles.css').read_text()+'</style>')
    for name in ['icons.js','guides.js','app.js']:
        html=html.replace(f'<script defer src="/src/{name}?v=0.7.0"></script>','')
    shim="window.fetch=async(path,options={})=>{const r=await window.testApiBridge(path,options);return new Response(r.body,{status:r.status,headers:r.headers});};"
    scripts='<script>'+shim+'</script>'+''.join('<script>'+(ROOT/'frontend/src'/name).read_text()+'</script>' for name in ['icons.js','guides.js','app.js'])
    html=html.replace('</body>',scripts+'</body>')
    logo='data:image/svg+xml;base64,'+base64.b64encode((ROOT/'frontend/assets/circlelogic-logo.svg').read_bytes()).decode()
    page.set_content(html.replace('/assets/circlelogic-logo.svg',logo))

def screenshot(page,name):
    watermark='AUTOMATED TEST / SYNTHETIC GOOGLE RESPONSES / NOT A LIVE GOOGLE CONNECTION'
    page.evaluate("""(txt)=>{let x=document.createElement('div');x.id='test-watermark';x.textContent=txt;x.style='position:fixed;bottom:0;left:0;right:0;z-index:99999;background:#142742;color:white;padding:8px;text-align:center;font:10px sans-serif;letter-spacing:.6px;pointer-events:none';document.body.append(x)}""",watermark)
    page.screenshot(path=str(OUT/name),full_page=True,animations='disabled',timeout=12000)
    page.evaluate("document.getElementById('test-watermark').remove()")

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path=args.chromium,args=['--no-sandbox'])
    context=browser.new_context(viewport={'width':1536,'height':1060},device_scale_factor=1,accept_downloads=True)
    page=context.new_page();page.set_default_timeout(10000);page.on('pageerror',lambda e:errors.append(str(e)))
    load_app(page);expect(page.locator('#login-form')).to_be_visible()
    page.locator('#f-username').fill('google.tester');page.locator('#f-password').fill('Synthetic-private-password-2026')
    page.locator('#login-form button[type=submit]').click();expect(page.locator('#mfa-form')).to_be_visible()
    secret=client.get('/api/auth/enrolment').json()['secret']
    page.locator('#mfa-code').fill(otp(secret,int(time.time()//30)));page.locator('#mfa-form button[type=submit]').click()
    expect(page.locator('.recoveries code')).to_have_count(8)
    page.locator('#recovery-form input[type=checkbox]').check();page.locator('#recovery-form button[type=submit]').click()
    expect(page.get_by_role('heading',name='Real Estate Brain',exact=True)).to_be_visible()
    check('Private workspace login and real backend MFA work')
    check('Dashboard starts without fabricated metrics',page.locator('.metric-value.missing').count()==5)
    check('Six integration source tiles are visible',page.locator('.source-tile').count()==6)
    check('Google Calendar tile is visible',page.locator('.source-tile').filter(has_text='Google Calendar').count()==1)

    page.locator('nav [data-nav=integrations]').click();expect(page.locator('.pilot-banner')).to_be_visible()
    check('Google Calendar connection row is present',page.locator('[data-provider-row=google]').count()==1)
    check('Microsoft Calendar remains present as an alternative',page.locator('[data-provider-row=microsoft]').count()==1)
    screenshot(page,'01-google-calendar-row.png')

    page.locator('[data-action=runtime-checks]').click();expect(page.locator('#google-callback')).to_be_visible()
    expect(page.locator('#google-callback')).to_have_value(ORIGIN+'/api/oauth/google/callback')
    check('Backend setup shows exact Google callback')
    check('Runtime checks do not claim provider access','do not contact Google' in page.get_by_role('dialog').inner_text())
    page.keyboard.press('Escape')

    page.locator('[data-provider-row=google] [data-connect]').click();expect(page.locator('#credential-form')).to_be_visible()
    check('Google connection window has exactly one paste field',page.locator('#credential-form input').count()==1)
    check('Google key field is masked',page.locator('#f-api_key').get_attribute('type')=='password')
    check('No JSON upload exists',page.locator('dialog input[type=file]').count()==0 and 'JSON' not in page.get_by_role('dialog').inner_text())
    check('Setup guide is directly available',page.locator('dialog [data-action=guide]').count()==1)
    screenshot(page,'02-google-paste-dialog.png')

    page.locator('#f-api_key').fill(CLIENT_SECRET);page.locator('#credential-form button[type=submit]').click()
    expect(page.locator('#credential-form .error-box')).to_contain_text('Setup guide')
    check('Client secret cannot be saved before client ID setup')
    page.locator('dialog [data-action=guide]').click();expect(page.locator('#connection-setup-form')).to_be_visible()
    check('Google guide contains one one-time identifier field',page.locator('#connection-setup-form input:not([readonly])').count()==1)
    expect(page.locator('#redirect-uri')).to_have_value(ORIGIN+'/api/oauth/google/callback')
    check('Guide displays exact Google redirect URI')
    check('Guide explains OAuth rather than a standalone API key','not a standalone Google API key' in page.get_by_role('dialog').inner_text())
    page.locator('#f-client_id').fill(CLIENT_ID);page.locator('#connection-setup-form button[type=submit]').click()
    expect(page.locator('#f-api_key')).to_be_visible()
    check('Saving Google client ID returns to simple key paste field')
    page.locator('#f-api_key').fill(CLIENT_SECRET);page.locator('#credential-form button[type=submit]').click()
    expect(page.get_by_role('heading',name='Google Calendar',exact=True)).to_be_visible()
    check('Client secret saves without marking connection live',client.get('/api/integrations/google/diagnostics').json()['status']=='configured')
    check('Stored secret is not returned into the DOM',CLIENT_SECRET not in page.content())
    check('Sync is disabled until OAuth consent',page.locator('[data-action=sync]').is_disabled())

    page.locator('[data-action=diagnostics]').click()
    expect(page.get_by_role('heading',name='Google Calendar connection checks',exact=True)).to_be_visible()
    check('Diagnostics shows Google read-only scope','calendar.events.readonly' in page.get_by_role('dialog').inner_text())
    page.keyboard.press('Escape')

    target=req('POST','/api/integrations/google/authorise').json()['url']
    parsed=urlparse(target);params=parse_qs(parsed.query)
    check('OAuth starts on official Google Accounts host',parsed.scheme=='https' and parsed.hostname=='accounts.google.com')
    check('OAuth requests read-only calendar events scope',params['scope']==['https://www.googleapis.com/auth/calendar.events.readonly'])
    check('OAuth requests offline access and explicit consent',params.get('access_type')==['offline'] and params.get('include_granted_scopes')==['true'] and 'consent' in params.get('prompt',[''])[0])
    check('Client secret is never placed in the browser authorisation URL',CLIENT_SECRET not in target)
    callback=client.get('/api/oauth/google/callback?state='+params['state'][0]+'&code=SYNTHETIC',follow_redirects=False)
    check('Synthetic Google callback returns to integrations',callback.status_code==303 and 'provider=google' in callback.headers['location'])

    now=datetime.now(timezone.utc)
    feed.events=[{
        'id':'GOOGLE-TEST-1','summary':'TEST - Google Calendar inspection',
        'start':{'dateTime':(now+timedelta(days=1)).isoformat(),'timeZone':'Australia/Sydney'},
        'end':{'dateTime':(now+timedelta(days=1,hours=1)).isoformat(),'timeZone':'Australia/Sydney'},
        'location':'Synthetic test location','status':'confirmed'}]
    page.evaluate('render()');expect(page.locator('[data-provider-row=google] .status')).to_have_text('Ready to sync')
    page.locator('[data-provider-row=google] [data-connect]').click();expect(page.locator('[data-action=sync]')).to_be_enabled()
    page.locator('[data-action=sync]').click();expect(page.get_by_role('heading',name='Calendar import completed',exact=True)).to_be_visible()
    check('Google import displays returned calendar count',page.locator('.import-result strong').inner_text()=='1')
    page.locator('[data-action=calendar-test-result]').click()
    expect(page.locator('.event-title').filter(has_text='TEST - Google Calendar inspection')).to_be_visible()
    check('Imported Google event appears in the dashboard')
    check('Dashboard labels the Google source','Google Calendar' in page.locator('.panel').filter(has_text='Upcoming Events').inner_text())
    screenshot(page,'03-google-event-dashboard.png')

    feed.events[0]['summary']='TEST - Updated Google event'
    page.locator('[data-action=refresh]').click();expect(page.locator('.event-title').filter(has_text='TEST - Updated Google event')).to_be_visible()
    check('Updated Google event replaces the previous snapshot entry',page.locator('.event').count()==1)
    feed.events=[];page.locator('[data-action=refresh]').click()
    expect(page.locator('.event-title')).to_have_count(0)
    check('Successful empty Google import removes previous event instead of inventing data')

    page.locator('nav [data-nav=integrations]').click();page.set_viewport_size({'width':390,'height':844})
    check('Six source tiles do not cause horizontal mobile overflow',page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
    page.locator('[data-provider-row=google] [data-connect]').click();page.locator('[data-action=replace-credentials]').click()
    expect(page.locator('#f-api_key')).to_be_visible()
    check('Google paste dialog fits mobile viewport',page.get_by_role('dialog').bounding_box()['width']<=390)
    screenshot(page,'04-google-mobile-paste.png')
    page.keyboard.press('Escape')

    page.set_viewport_size({'width':1536,'height':1060})
    page.locator('[data-provider-row=google] [data-connect]').click();page.locator('[data-action=disconnect]').click();page.locator('[data-action=confirm-disconnect]').click()
    check('Disconnect clears Google credentials',not client.get('/api/integrations/google/diagnostics').json()['credentials_saved'])
    check('Disconnect clears Google one-time setup',not client.get('/api/integrations/google/setup').json()['ready'])
    check('No browser JavaScript errors',not errors)
    context.close();browser.close()

report={
    'checks_passed':len(checks),'checks':checks,'browser_errors':errors,
    'transport':'Embedded Chromium with FastAPI TestClient fetch bridge. No native browser networking or HTTPS.',
    'provider_requests':'Synthetic Google token and Calendar API responses through the real Engine adapter. No real Google account was used.'
}
(OUT/'browser-report.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2));client.close();TEMP.cleanup()
