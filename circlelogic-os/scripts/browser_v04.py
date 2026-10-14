"""Embedded Chromium interface checks against a temporary FastAPI backend.
Browser fetch is bridged to TestClient; native browser networking/TLS is not tested.
No real provider accounts or customer data are used.
"""
from pathlib import Path
import json
import sys
import time
import tempfile
import base64
from fastapi.testclient import TestClient
from cryptography.fernet import Fernet
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.security import otp
from app.config import Settings
from app.main import create_app
from app.provision import bootstrap_testing_account
from app.connectors import ConnectorError
import argparse
parser=argparse.ArgumentParser();parser.add_argument('--output',default=str(ROOT/'docs/ui-test-output'));args=parser.parse_args()
OUT=Path(args.output);OUT.mkdir(parents=True,exist_ok=True)
ORIGIN='http://localhost:8000'
TEMP=tempfile.TemporaryDirectory()
settings=Settings(Path(TEMP.name),ORIGIN,'test',Fernet.generate_key().decode(),False,'')
class BrowserFeed:
    failure=False
    def sync(self,provider,creds,save):
        if self.failure:raise ConnectorError('Synthetic provider failure.')
        assert provider=='rea'
        return {'campaigns':[{'external_id':'fixture-one','title':'REA listing TEST-ONE','status':'Report available','totals':{'page_views':2400,'email_enquiries':17,'saves':0}}]}
    def close(self):pass
app=create_app(settings,engine_factory=BrowserFeed);bootstrap_testing_account(settings,app.state.store)
client=TestClient(app,base_url=ORIGIN)

def load_app(page):
    def bridge(path,options):
        assert path.startswith('/api/')
        r=client.request(options.get('method','GET'),path,content=options.get('body'),headers={**options.get('headers',{}),'Origin':ORIGIN})
        return {'status':r.status_code,'body':r.text,'headers':{'Content-Type':r.headers.get('content-type','application/json')}}
    page.expose_function('testApiBridge',bridge)
    html=(ROOT/'frontend/index.html').read_text().replace('<link rel="stylesheet" href="/src/styles.css">','<style>'+(ROOT/'frontend/src/styles.css').read_text()+'</style>')
    for name in ['icons.js','guides.js','app.js']:html=html.replace(f'<script defer src="/src/{name}"></script>','')
    shim="window.fetch=async(path,options={})=>{const r=await window.testApiBridge(path,options);return new Response(r.body,{status:r.status,headers:r.headers});};"
    scripts='<script>'+shim+'</script>'+''.join('<script>'+(ROOT/'frontend/src'/name).read_text()+'</script>' for name in ['icons.js','guides.js','app.js'])
    html=html.replace('</body>',scripts+'</body>')
    logo='data:image/svg+xml;base64,'+base64.b64encode((ROOT/'frontend/assets/circlelogic-logo.svg').read_bytes()).decode()
    page.set_content(html.replace('/assets/circlelogic-logo.svg',logo))
checks=[];errors=[]
def check(name,condition=True):
    if not condition: raise AssertionError(name)
    checks.append(name)
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
    context=browser.new_context(viewport={'width':1536,'height':1060},device_scale_factor=1)
    page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_content((ROOT/'docs/archive/v04/CircleLogic-OS-v04-Interactive-Preview.html').read_text())
    expect(page.locator('#login-form')).to_be_visible()
    page.screenshot(path=str(OUT/'login-desktop.png'),full_page=True)
    check('Preview opens at sign-in, not at dashboard',page.locator('.source-grid').count()==0)
    page.locator('#f-username').fill('testing123');page.locator('#f-password').fill('wrongpassword')
    page.locator('#login-form button[type=submit]').click();expect(page.locator('#login-form .error-box')).to_be_visible()
    check('Preview rejects incorrect login')
    page.locator('#f-password').fill('testing12345');page.locator('#login-form button[type=submit]').click()
    expect(page.locator('#mfa-form')).to_be_visible();check('Preview explains that 2FA is simulated','Simulated two-factor' in page.inner_text('body'))
    page.locator('#mfa-code').fill('123456');page.locator('#mfa-form button[type=submit]').click()
    expect(page.get_by_role('heading',name='Real Estate Brain',exact=True)).to_be_visible()
    check('Exactly two sidebar navigation buttons',page.locator('nav[aria-label="Workspace pages"] button').count()==2)
    check('New dashboard has five empty KPI widgets',page.locator('.metric-value.missing').count()==5)
    check('New dashboard has exactly five source tiles',page.locator('.source-tile').count()==5)
    page.screenshot(path=str(OUT/'dashboard-empty-desktop.png'),full_page=True)
    page.get_by_role('button',name='Example data',exact=True).click()
    expect(page.locator('[data-metric=contacts] .metric-value')).to_have_text('8,432')
    check('Example mode labelled explicitly',page.locator('.preview-strip').inner_text().startswith('EXAMPLE DATA'))
    page.screenshot(path=str(OUT/'dashboard-example-desktop.png'),full_page=True)
    page.locator('.buyer-row').first.click();expect(page.get_by_role('dialog')).to_be_visible()
    check('Example record warns score is illustrative','score is illustrative' in page.get_by_role('dialog').inner_text())
    page.keyboard.press('Escape');expect(page.get_by_role('dialog')).to_have_count(0)
    check('Escape closes dialogs')
    page.locator('#calendar-window').select_option('7')
    check('Calendar filter reduces displayed sample events',page.locator('.event-list .event').count()==3)
    page.locator('#calendar-window').select_option('30')
    check('Calendar 30-day view restores sample events',page.locator('.event-list .event').count()==4)
    page.get_by_role('button',name='Empty dashboard',exact=True).click()
    expect(page.locator('.metric-value.missing')).to_have_count(5)
    check('Example data can be removed without entering customer storage')
    page.locator('nav [data-nav=integrations]').click()
    expect(page.get_by_role('heading',name='API Connections',exact=True)).to_be_visible()
    page.screenshot(path=str(OUT/'connections-desktop.png'),full_page=True)
    check('One connection panel contains five rows',page.locator('.connection-list .connection-row').count()==5)
    page.locator('[data-provider-row=rea] [data-connect]').click()
    expect(page.locator('#credential-form')).to_be_visible()
    check('Standalone preview disables credential text fields',page.locator('#f-client_secret').is_disabled())
    check('Standalone preview disables credential uploads',page.locator('#credential-file').is_disabled())
    page.keyboard.press('Escape')
    for provider in ['agentbox','rea','rpdata','proping','microsoft']:
        page.locator('.help-list [data-provider='+provider+']').click()
        expect(page.locator('.guide-steps')).to_be_visible()
        check('Guide has numbered steps and official sources: '+provider,page.locator('.guide-step').count()>=5 and page.locator('.guide-sources a').count()>=1)
        if provider=='microsoft':page.screenshot(path=str(OUT/'calendar-guide-desktop.png'),full_page=True)
        page.keyboard.press('Escape')
    page.get_by_role('button',name='Example data',exact=True).click();page.set_viewport_size({'width':390,'height':844})
    expect(page.get_by_role('heading',name='Real Estate Brain',exact=True)).to_be_visible()
    page.screenshot(path=str(OUT/'dashboard-example-mobile.png'),full_page=True)
    check('Mobile dashboard has no horizontal overflow',page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
    page.get_by_role('button',name='Toggle navigation').click()
    page.locator('nav [data-nav=integrations]').click()
    expect(page.get_by_role('heading',name='API Connections',exact=True)).to_be_visible()
    page.screenshot(path=str(OUT/'connections-mobile.png'),full_page=True)
    check('Mobile API Connections has no horizontal overflow',page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
    page.locator('[data-provider-row=rea] [data-connect]').click()
    check('Mobile credential dialog fits viewport',page.locator('.dialog').bounding_box()['width']<=390)
    page.keyboard.press('Escape');context.close()
    # Real backend: all provider credentials below are synthetic test sentinels.
    context=browser.new_context(viewport={'width':1536,'height':1060},device_scale_factor=1)
    page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
    load_app(page)
    expect(page.locator('#login-form')).to_be_visible()
    page.screenshot(path=str(OUT/'application-login.png'),full_page=True)
    page.locator('#f-username').fill('testing123');page.locator('#f-password').fill('testing12345');page.locator('#login-form button[type=submit]').click()
    expect(page.locator('#mfa-form')).to_be_visible()
    check('Backend dashboard is blocked before MFA',client.get('/api/brain/dashboard').status_code==401)
    enrol=client.get('/api/auth/enrolment')
    if enrol.status_code!=200:raise AssertionError('Use a fresh throwaway DATA_DIR before rerunning this script.')
    secret=enrol.json()['secret']
    expect(page.locator('.qr-block img')).to_be_visible()
    check('Real backend returns a scannable enrolment QR',page.locator('.qr-block img').get_attribute('src').startswith('data:image/png;base64,'))
    page.locator('#mfa-code').fill(otp(secret,int(time.time()//30)));page.locator('#mfa-form button[type=submit]').click()
    expect(page.locator('.recoveries code')).to_have_count(8)
    recovery=page.locator('.recoveries code').all_text_contents()
    page.locator('#recovery-form input[type=checkbox]').check();page.locator('#recovery-form button[type=submit]').click()
    expect(page.get_by_role('heading',name='Real Estate Brain',exact=True)).to_be_visible()
    check('Real first login goes through TOTP and recovery codes')
    check('No example toggle in real application',page.locator('[data-action=preview-example]').count()==0)
    check('Real dashboard starts empty',page.locator('.metric-value.missing').count()==5)
    page.screenshot(path=str(OUT/'application-dashboard-empty.png'),full_page=True)
    page.locator('nav [data-nav=integrations]').click()
    expect(page.locator('.connection-row')).to_have_count(5)
    page.screenshot(path=str(OUT/'application-connections.png'),full_page=True)
    page.locator('[data-provider-row=agentbox] [data-connect]').click()
    check('Agentbox is gated, not a false API form',page.locator('#credential-form').count()==0 and 'not implemented' in page.get_by_role('dialog').inner_text())
    page.keyboard.press('Escape');page.locator('[data-provider-row=rea] [data-connect]').click()
    expect(page.locator('#credential-file')).to_be_visible()
    page.screenshot(path=str(OUT/'secure-connection-blank.png'),full_page=True)
    page.locator('#credential-file').set_input_files({'name':'bad.json','mimeType':'application/json','buffer':b'{not-valid-json'})
    expect(page.locator('#credential-form .error-box')).to_be_visible()
    check('Malformed credential JSON is rejected')
    values={'client_id':'TEST_ONLY_CLIENT','client_secret':'TEST_ONLY_SECRET_NEVER_A_REAL_KEY','agency_id':'TESTOFFICE'}
    page.locator('#credential-file').set_input_files({'name':'test.json','mimeType':'application/json','buffer':json.dumps(values).encode()})
    expect(page.locator('#f-client_id')).to_have_value(values['client_id'])
    check('Valid JSON fills fields but does not auto-save',client.get('/api/brain/connections').json()['connections'][1]['has_credentials'] is False)
    page.locator('#credential-form button[type=submit]').click()
    expect(page.get_by_role('heading',name='Manage REA Ignite',exact=True)).to_be_visible()
    check('Saving credentials does not claim a live connection','Credentials saved' in page.get_by_role('dialog').inner_text())
    page.screenshot(path=str(OUT/'credentials-saved.png'),full_page=True)
    body=client.get('/api/brain/connections').text
    check('API never returns saved secrets',values['client_secret'] not in body and values['client_id'] not in body)
    check('Saved secrets removed from DOM',values['client_secret'] not in page.content())
    page.locator('[data-action=sync]').click()
    expect(page.get_by_role('dialog')).to_have_count(0)
    expect(page.locator('[data-provider-row=rea] .status')).to_have_text('Connected')
    check('Successful synthetic import changes connection status to connected')
    page.locator('nav [data-nav=dashboard]').click()
    expect(page.get_by_role('heading',name='Listing performance',exact=True)).to_be_visible()
    expect(page.locator('.event-time').filter(has_text='2,400 views')).to_be_visible()
    check('Actual dashboard renders imported report-period views and enquiry counts')
    check('Report import never populates an invented high-intent buyer count',page.locator('[data-metric=buyers] .metric-value.missing').count()==1)
    BrowserFeed.failure=True
    page.locator('[data-action=refresh]').click()
    expect(page.locator('.panel .subtitle').filter(has_text='needs refresh')).to_be_visible()
    expect(page.locator('.event-time').filter(has_text='2,400 views')).to_be_visible()
    check('Failed refresh retains actual imported rows with a stale warning')
    page.locator('nav [data-nav=integrations]').click()
    expect(page.locator('[data-provider-row=rea] [data-connect]')).to_be_visible()
    page.locator('[data-provider-row=rea] [data-connect]').click()
    page.locator('[data-action=disconnect]').click();page.locator('[data-action=confirm-disconnect]').click()
    expect(page.get_by_role('dialog')).to_have_count(0)
    check('Disconnect removes saved credentials',client.get('/api/brain/connections').json()['connections'][1]['has_credentials'] is False)
    check('Disconnect removes previously imported rows',client.get('/api/brain/dashboard').json()['buyer_activity']['total'] is None)
    page.locator('[data-provider-row=microsoft] [data-connect]').click()
    expect(page.locator('#redirect-uri')).to_have_value('http://localhost:8000/api/oauth/microsoft/callback')
    check('Microsoft shows exact server callback URI')
    page.keyboard.press('Escape');page.locator('.profile [data-action=logout]').click()
    expect(page.locator('#login-form')).to_be_visible()
    check('Logout revokes backend session',client.get('/api/brain/dashboard').status_code==401)
    page.locator('#f-username').fill('testing123');page.locator('#f-password').fill('testing12345');page.locator('#login-form button[type=submit]').click()
    expect(page.get_by_role('heading',name="Confirm it's you.")).to_be_visible()
    check('Subsequent login challenges MFA instead of re-enrolling',page.locator('.qr-block').count()==0)
    page.locator('#mfa-code').fill(recovery[0]);page.locator('#mfa-form button[type=submit]').click()
    expect(page.get_by_role('heading',name='Real Estate Brain',exact=True)).to_be_visible()
    check('One-time recovery code works in full browser login')
    check('No browser JavaScript errors',not errors)
    context.close();browser.close()
report={'checks_passed':len(checks),'checks':checks,'browser_errors':errors,'provider_requests':'Synthetic fixture imports through the real backend. Zero live provider requests or credentials.'}
(OUT/'browser-report.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
client.close();TEMP.cleanup()
