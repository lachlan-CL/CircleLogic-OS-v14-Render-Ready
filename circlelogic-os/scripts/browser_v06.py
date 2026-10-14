"""v06 paste-only connection browser checks. Fetch uses a TestClient bridge; OAuth and Graph
responses are synthetic. Does not test native browser transport or live Microsoft.
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
parser.add_argument('--output',default=str(ROOT/'docs/evidence-v06/ui'))
parser.add_argument('--chromium',default='/usr/bin/chromium')
args=parser.parse_args()
OUT=Path(args.output);OUT.mkdir(parents=True,exist_ok=True)
ORIGIN='http://localhost:8000';TEMP=tempfile.TemporaryDirectory()
secret_value='SYNTHETIC-CLIENT-SECRET-NOT-A-REAL-KEY'
class GraphFixture:
    events=[];fail=False
    def __call__(self,req):
        if req.url.host=='login.microsoftonline.com':
            return httpx.Response(200,json={'access_token':'SYNTHETIC-TOKEN','refresh_token':'SYNTHETIC-REFRESH','expires_in':3600})
        assert req.url.host=='graph.microsoft.com' and req.method=='GET'
        if self.fail:return httpx.Response(403,json={'error':{'message':'RAW_GRAPH_ERROR_SENTINEL'}})
        return httpx.Response(200,json={'value':self.events})
feed=GraphFixture()
s=Settings(Path(TEMP.name),ORIGIN,'test',Fernet.generate_key().decode(),False,'')
app=create_app(s,engine_factory=lambda:Engine(transport=httpx.MockTransport(feed)))
create_workspace(app.state.store,agency='Private calendar test',name='Test operator',username='calendar.tester',
                 email='calendar.tester@example.invalid',password='Synthetic-private-password-2026')
client=TestClient(app,base_url=ORIGIN)
checks=[];errors=[]
def check(name,condition=True):
    assert condition,name
    checks.append(name)
    print("PASS: "+name,flush=True)
def req(method,path,data=None):
    csrf=client.get('/api/auth/session').json().get('csrf','')
    return client.request(method,path,json=data or {},headers={'Origin':ORIGIN,'X-CSRF-Token':csrf,'Content-Type':'application/json'})
def load_app(page):
    def bridge(path,options):
        assert path.startswith('/api/'),path
        r=client.request(options.get('method','GET'),path,content=options.get('body'),headers={**options.get('headers',{}),'Origin':ORIGIN})
        return {'status':r.status_code,'body':r.text,'headers':{'Content-Type':r.headers.get('content-type','application/json')}}
    page.expose_function('testApiBridge',bridge)
    html=(ROOT/'frontend/index.html').read_text().replace('<link rel="stylesheet" href="/src/styles.css?v=0.6.0">','<style>'+(ROOT/'frontend/src/styles.css').read_text()+'</style>')
    for name in ['icons.js','guides.js','app.js']:html=html.replace(f'<script defer src="/src/{name}?v=0.6.0"></script>','')
    shim="window.fetch=async(path,options={})=>{const r=await window.testApiBridge(path,options);return new Response(r.body,{status:r.status,headers:r.headers});};"
    scripts='<script>'+shim+'</script>'+''.join('<script>'+(ROOT/'frontend/src'/name).read_text()+'</script>' for name in ['icons.js','guides.js','app.js'])
    html=html.replace('</body>',scripts+'</body>')
    logo='data:image/svg+xml;base64,'+base64.b64encode((ROOT/'frontend/assets/circlelogic-logo.svg').read_bytes()).decode()
    page.set_content(html.replace('/assets/circlelogic-logo.svg',logo))
def screenshot(page,name):
    print('SCREENSHOT: '+name,flush=True)
    page.evaluate("""()=>{let x=document.createElement('div');x.id='test-watermark';x.textContent='AUTOMATED TEST / SYNTHETIC ACCOUNT AND PROVIDER RESPONSES / NOT A LIVE MICROSOFT CONNECTION';x.style='position:fixed;bottom:0;left:0;right:0;z-index:99999;background:#142742;color:white;padding:8px;text-align:center;font:10px sans-serif;letter-spacing:.6px;pointer-events:none';document.body.append(x)}""")
    page.screenshot(path=str(OUT/name),full_page=True,animations='disabled',timeout=12000)
    page.evaluate("document.getElementById('test-watermark').remove()")
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path=args.chromium,args=['--no-sandbox'])
    context=browser.new_context(viewport={'width':1536,'height':1060},device_scale_factor=1,accept_downloads=True)
    page=context.new_page();page.set_default_timeout(10000);page.on('pageerror',lambda e:errors.append(str(e)))
    load_app(page);expect(page.locator('#login-form')).to_be_visible()
    screenshot(page,'01-running-login.png')
    page.locator('#f-username').fill('calendar.tester');page.locator('#f-password').fill('Synthetic-private-password-2026')
    page.locator('#login-form button[type=submit]').click();expect(page.locator('#mfa-form')).to_be_visible()
    secret=client.get('/api/auth/enrolment').json()['secret']
    page.locator('#mfa-code').fill(otp(secret,int(time.time()//30)));page.locator('#mfa-form button[type=submit]').click()
    expect(page.locator('.recoveries code')).to_have_count(8)
    page.locator('#recovery-form input[type=checkbox]').check();page.locator('#recovery-form button[type=submit]').click()
    expect(page.get_by_role('heading',name='Real Estate Brain',exact=True)).to_be_visible()
    check('Private workspace login and real backend MFA work in embedded UI')
    check('Two pages retained',page.locator('nav[aria-label="Workspace pages"] button').count()==2)
    check('No example-data toggle in the running app',page.locator('[data-action=preview-example]').count()==0)
    check('All metrics remain empty before imports',page.locator('.metric-value.missing').count()==5)
    page.locator('nav [data-nav=integrations]').click();expect(page.locator('.pilot-banner')).to_be_visible()
    check('Pilot banner identifies running backend and approved test mailbox', 'approved Microsoft test mailbox' in page.locator('.pilot-banner').inner_text())
    screenshot(page,'02-api-connections.png')
    page.locator('[data-action=runtime-checks]').click();expect(page.locator('.check-row')).to_have_count(4)
    check('Runtime check shows four actual backend checks',page.locator('.check-row').count()==4)
    check('Runtime check explicitly disclaims provider access','do not contact Microsoft' in page.get_by_role('dialog').inner_text())
    expect(page.locator('#setup-callback')).to_have_value(ORIGIN+'/api/oauth/microsoft/callback')
    screenshot(page,'03-backend-checks.png')
    page.keyboard.press('Escape')
    page.locator('[data-provider-row=microsoft] [data-connect]').click();expect(page.locator('#credential-form')).to_be_visible()
    check('Microsoft paste box enabled',page.locator('#f-api_key').is_enabled())
    check('Exactly one credential entry field',page.locator('#credential-form input').count()==1)
    check('No file-upload or JSON UI in connection window',page.locator('dialog input[type=file]').count()==0 and 'JSON' not in page.get_by_role('dialog').inner_text())
    check('No client ID, tenant ID or redirect in the key window',page.locator('dialog #f-client_id, dialog #f-directory_id, dialog #redirect-uri').count()==0)
    check('One software name and guide link',page.get_by_role('dialog').get_by_role('heading').count()==1 and page.locator('dialog [data-action=guide]').count()==1)
    check('Key is masked with autofill discouraged',page.locator('#f-api_key').get_attribute('type')=='password' and page.locator('#f-api_key').get_attribute('autocomplete')=='new-password')
    screenshot(page,'04-paste-only-calendar.png')
    page.get_by_role('dialog').screenshot(path=str(OUT/'04-paste-dialog-only.png'),animations='disabled')
    page.locator('#f-api_key').fill('SYNTHETIC-KEY-BEFORE-SETUP')
    page.locator('#credential-form button[type=submit]').click()
    expect(page.locator('#credential-form .error-box')).to_contain_text('Setup guide')
    check('Missing setup gives actionable error, not a fake connection',not client.get('/api/integrations/microsoft/diagnostics').json()['credentials_saved'])
    page.locator('dialog [data-action=guide]').click()
    expect(page.locator('#connection-setup-form')).to_be_visible()
    expect(page.locator('#redirect-uri')).to_have_value(ORIGIN+'/api/oauth/microsoft/callback')
    check('Technical identifiers and callback are in guide only',page.locator('#connection-setup-form input').count()==3)
    check('Guide never shows or asks for a secret',page.locator('#connection-setup-form input[type=password]').count()==0)
    vals={'client_id':'11111111-2222-3333-4444-555555555555','directory_id':'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee','client_secret':secret_value}
    page.locator('#f-client_id').fill(vals['client_id']);page.locator('#f-directory_id').fill(vals['directory_id'])
    page.locator('#connection-setup-form button[type=submit]').click()
    expect(page.locator('#f-api_key')).to_have_value('')
    check('Saving setup returns to an empty key box',page.locator('#credential-form input').count()==1)
    check('Setup alone stores no active credentials',not client.get('/api/integrations/microsoft/diagnostics').json()['credentials_saved'])
    page.locator('#f-api_key').fill('testing12345');page.locator('#credential-form button[type=submit]').click()
    expect(page.locator('#credential-form .error-box')).to_contain_text('not an API key')
    check('Published testing password cannot be used as an API key')
    page.locator('#f-api_key').fill(secret_value)
    page.locator('dialog [data-action=show-secret]').click()
    check('Show-key control works',page.locator('#f-api_key').get_attribute('type')=='text')
    page.locator('dialog [data-action=show-secret]').click()
    page.locator('#credential-form button[type=submit]').click()
    expect(page.get_by_role('heading',name='Diary / Calendar',exact=True)).to_be_visible()
    expect(page.locator('dialog [data-action=sync]')).to_be_visible()
    check('Pasted key saved without creating a live connection','Credentials saved' in page.get_by_role('dialog').inner_text())
    check('Saved secret cleared from the DOM and not shown back',page.locator('#f-api_key').count()==0 and secret_value not in page.content())
    check('Test and sync still disabled before authorisation',page.locator('[data-action=sync]').is_disabled())
    screenshot(page,'05-saved-not-connected.png')
    page.locator('[data-action=diagnostics]').click();expect(page.get_by_role('heading',name='Diary / Calendar connection checks',exact=True)).to_be_visible()
    check('Connection progress identifies missing authorisation','Not authorised yet' in page.locator('.connection-progress').inner_text())
    check('Three explicit connection stages',page.locator('.connection-progress li').count()==3)
    screenshot(page,'06-connection-checks.png')
    with page.expect_download() as download:
        page.locator('[data-action=download-diagnostics]').click()
    path=download.value.path();report=Path(path).read_text()
    check('Diagnostic download contains no credential values',all(v not in report for v in vals.values()))
    page.keyboard.press('Escape')
    # A simulated OAuth redirect, not a live browser journey through Microsoft.
    target=req('POST','/api/integrations/microsoft/authorise').json()['url']
    params=parse_qs(urlparse(target).query)
    check('Generated OAuth uses PKCE and explicit account selection',params['code_challenge_method']==['S256'] and params['prompt']==['select_account'])
    callback=client.get('/api/oauth/microsoft/callback?state='+params['state'][0]+'&code=SYNTHETIC',follow_redirects=False)
    check('Synthetic token exchange returns to integrations',callback.status_code==303 and 'oauth=success' in callback.headers['location'])
    now=datetime.now(timezone.utc)
    feed.events=[{'id':'TEST-EVENT-1','subject':'TEST - CircleLogic inspection','start':{'dateTime':(now+timedelta(days=1)).isoformat(),'timeZone':'UTC'},'end':{'dateTime':(now+timedelta(days=1,hours=1)).isoformat(),'timeZone':'UTC'},'location':{'displayName':'Synthetic test location'},'isAllDay':False,'isCancelled':False}]
    page.evaluate('render()');expect(page.locator('[data-provider-row=microsoft] .status')).to_have_text('Ready to sync')
    page.locator('[data-provider-row=microsoft] [data-connect]').click();expect(page.locator('[data-action=sync]')).to_be_enabled()
    check('Authorisation enables test and sync')
    page.locator('[data-action=sync]').click();expect(page.get_by_role('heading',name='Calendar import completed',exact=True)).to_be_visible()
    check('Import result shows actual returned fixture count',page.locator('.import-result strong').inner_text()=='1')
    screenshot(page,'07-synthetic-import-result.png')
    page.locator('[data-action=calendar-test-result]').click();expect(page.locator('.event-title').filter(has_text='TEST - CircleLogic inspection')).to_be_visible()
    check('Actual adapter output appears in dashboard')
    screenshot(page,'08-synthetic-calendar-dashboard.png')
    page.locator('.event').filter(has_text='TEST - CircleLogic inspection').click();expect(page.get_by_role('dialog')).to_be_visible()
    check('Calendar detail shows private login visibility','Private to this login' in page.get_by_role('dialog').inner_text())
    page.keyboard.press('Escape')
    feed.events[0]['subject']='TEST - Updated inspection';page.locator('[data-action=refresh]').click()
    expect(page.locator('.event-title').filter(has_text='TEST - Updated inspection')).to_be_visible()
    check('Updated source appointment replaces original',page.locator('.event').count()==1)
    feed.fail=True;page.locator('[data-action=refresh]').click()
    expect(page.locator('.source-tile').filter(has_text='Calendar').locator('.status')).to_have_text('Needs attention')
    check('Failed provider refresh retains previous appointment',page.locator('.event-title').filter(has_text='TEST - Updated inspection').count()==1)
    page.locator('nav [data-nav=integrations]').click();page.locator('[data-provider-row=microsoft] [data-connect]').click();page.locator('[data-action=diagnostics]').click()
    expect(page.get_by_role('heading',name='Diary / Calendar connection checks',exact=True)).to_be_visible()
    expect(page.locator('.error-box')).to_be_visible()
    check('Provider failure appears as a safe diagnostic error','RAW_GRAPH_ERROR_SENTINEL' not in page.get_by_role('dialog').inner_text())
    page.keyboard.press('Escape');expect(page.get_by_role('dialog')).to_have_count(0)
    page.set_viewport_size({'width':390,'height':844})
    check('Pilot page has no horizontal mobile overflow',page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
    screenshot(page,'09-mobile-connections.png')
    page.locator('[data-provider-row=microsoft] [data-connect]').click();page.locator('[data-action=diagnostics]').click()
    expect(page.get_by_role('dialog')).to_be_visible()
    check('Diagnostic dialog fits mobile viewport',page.get_by_role('dialog').bounding_box()['width']<=390)
    screenshot(page,'10-mobile-checks.png')
    page.keyboard.press('Escape');expect(page.get_by_role('dialog')).to_have_count(0)
    page.set_viewport_size({'width':1536,'height':1060})
    page.locator('[data-provider-row=microsoft] [data-connect]').click();page.locator('[data-action=disconnect]').click();page.locator('[data-action=confirm-disconnect]').click()
    expect(page.get_by_role('dialog')).to_have_count(0)
    check('Disconnect clears saved credentials and snapshots',not client.get('/api/integrations/microsoft/diagnostics').json()['credentials_saved'] and client.get('/api/brain/dashboard').json()['calendar']['total'] is None)
    page.locator('[data-provider-row=rea] [data-connect]').click()
    expect(page.locator('#credential-form input')).to_have_count(1)
    check('REA also has one paste-only field')
    page.locator('dialog [data-action=guide]').click()
    expect(page.locator('#connection-setup-form')).to_be_visible()
    page.locator('#f-client_id').fill('REA-SYNTHETIC-CLIENT');page.locator('#f-agency_id').fill('TEST-AGENCY')
    page.locator('#connection-setup-form button[type=submit]').click()
    expect(page.locator('#f-api_key')).to_be_visible()
    page.locator('#f-api_key').fill('REA-SYNTHETIC-SECRET')
    page.locator('#credential-form button[type=submit]').click()
    expect(page.locator('dialog [data-action=sync]')).to_be_enabled()
    check('REA secret entry reaches the backend without an upload',client.get('/api/integrations/rea/diagnostics').json()['credentials_saved'])
    page.locator('dialog [data-action=replace-credentials]').click()
    expect(page.locator('#f-api_key')).to_have_value('')
    check('Replace key never returns stored secret')
    screenshot(page,'11-paste-only-rea.png')
    page.keyboard.press('Escape')
    page.locator('[data-provider-row=microsoft] [data-connect]').click()
    page.set_viewport_size({'width':390,'height':844})
    expect(page.locator('#f-api_key')).to_be_visible()
    check('Compact key dialog fits mobile without horizontal scroll',page.get_by_role('dialog').bounding_box()['width']<=390 and page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
    check('Mobile key field and save button fit without scrolling',page.locator('#credential-form button[type=submit]').bounding_box()['y']<844)
    screenshot(page,'12-mobile-key-entry.png')
    page.locator('#f-api_key').fill('SYNTHETIC-CANCELLED');page.keyboard.press('Escape')
    page.locator('[data-provider-row=microsoft] [data-connect]').click()
    expect(page.locator('#f-api_key')).to_have_value('')
    check('Closing key window discards unsaved secret')
    page.keyboard.press('Escape')
    for provider in ['agentbox','rpdata','proping']:
        page.locator('[data-provider-row='+provider+'] [data-connect]').click()
        expect(page.get_by_role('dialog')).to_be_visible()
        check(provider+' remains honestly gated with a setup guide',page.locator('dialog input').count()==0 and page.locator('dialog [data-action=guide]').count()==1)
        page.keyboard.press('Escape')
    check('No browser JavaScript errors',not errors)
    context.close();browser.close()
report={'checks_passed':len(checks),'checks':checks,'browser_errors':errors,
        'transport':'Embedded Chromium with TestClient fetch bridge. No native browser networking, HTTPS or live Microsoft consent tested.',
        'provider_requests':'Synthetic Microsoft token and Graph responses through the real Engine adapter. No real provider requests.'}
(OUT/'browser-report.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2));client.close();TEMP.cleanup()
