"""UI plus FastAPI smoke check through an in-process test bridge.

This does not test browser network/cookie enforcement, TLS, live OAuth providers,
or deployment. Those are separately listed release gates.
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import time
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.config import Settings
from app.main import create_app
from app.security import otp

p=argparse.ArgumentParser();p.add_argument('--chromium',default='/usr/bin/chromium');p.add_argument('--output',default=str(ROOT/'docs/ui-test-output'));args=p.parse_args()
out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
origin='http://localhost:8000'
with tempfile.TemporaryDirectory() as temp:
    app=create_app(Settings(Path(temp),origin,'test',Fernet.generate_key().decode(),True,''))
    client=TestClient(app,base_url=origin)
    def bridge(path,options):
        assert path.startswith('/api/')
        headers={**options.get('headers',{}),'Origin':origin}
        r=client.request(options.get('method','GET'),path,content=options.get('body'),headers=headers)
        return {'status':r.status_code,'body':r.text,'headers':{'Content-Type':r.headers.get('content-type','application/json')}}
    html=(ROOT/'frontend/index.html').read_text().replace('<link rel="stylesheet" href="/src/styles.css">','<style>'+(ROOT/'frontend/src/styles.css').read_text()+'</style>')
    for name in ['icons.js','app.js']:html=html.replace(f'<script defer src="/src/{name}"></script>','')
    shim="window.fetch=async(path,options={})=>{const r=await window.testApiBridge(path,options);return new Response(r.body,{status:r.status,headers:r.headers});};"
    scripts='<script>'+shim+'</script>'+''.join('<script>'+(ROOT/'frontend/src'/name).read_text()+'</script>' for name in ['icons.js','app.js'])
    html=html.replace('</body>',scripts+'</body>')
    import base64
    logo='data:image/svg+xml;base64,'+base64.b64encode((ROOT/'frontend/assets/circlelogic-logo.svg').read_bytes()).decode()
    html=html.replace('/assets/circlelogic-logo.svg',logo)
    errors=[];checks=[]
    with sync_playwright() as pw:
        b=pw.chromium.launch(executable_path=args.chromium,headless=True,args=['--no-sandbox'])
        page=b.new_page(viewport={'width':1512,'height':982});page.on('pageerror',lambda e:errors.append(str(e)))
        page.expose_function('testApiBridge',bridge)
        page.set_content(html);page.wait_for_selector('#auth-login')
        page.screenshot(path=str(out/'login.png'),full_page=True)
        page.locator('[data-action=auth-register]').click()
        for key,value in {'name':'UI Test Owner','agency':'Synthetic UI Agency','email':'ui@agency.example','password':'Test-Only-Private-Passphrase'}.items():page.locator('#f-'+key).fill(value)
        page.locator('#auth-register button[type=submit]').click();page.wait_for_selector('.qr')
        assert client.get('/api/dashboard').status_code==401
        secret=client.get('/api/auth/enrolment').json()['secret']
        page.locator('#f-code').fill(otp(secret,int(time.time()//30)))
        page.locator('#auth-mfa button[type=submit]').click();page.wait_for_selector('#recovery-saved')
        codes=page.locator('.recovery-code').all_inner_texts();assert len(codes)==8
        page.locator('#recovery-saved').check();page.locator('[data-action=finish-enrolment]').click();page.wait_for_selector('.metric')
        checks.append('Create workspace, enrol TOTP, display eight recovery codes, enter dashboard')
        page.locator('[data-action=new-task]').click();page.locator('#f-title').fill('Saved UI workspace task');page.locator('#task-form button[type=submit]').click();page.wait_for_timeout(400)
        assert 'Saved UI workspace task' in page.inner_text('#page')
        assert client.get('/api/records/tasks').json()['mode']=='local'
        checks.append('UI-created task persists in the backend and replaces sample tasks')
        page.locator('.nav-item[data-nav=integrations]').click();page.wait_for_selector('.integration-card')
        page.locator('[data-action=configure][data-provider=rex]').click();page.wait_for_selector('#integration-form')
        values={'email':'integration@example.invalid','password':'TEST-ONLY-REX-SECRET','account_id':'123'}
        page.locator('#credentials-file').set_input_files({'name':'test-credentials.json','mimeType':'application/json','buffer':json.dumps(values).encode()})
        assert page.locator('#f-password').input_value()==values['password']
        page.locator('#integration-form button[type=submit]').click();page.wait_for_timeout(450)
        data=client.get('/api/integrations').json();rex=next(x for x in data['integrations'] if x['id']=='rex')
        assert rex['status']=='configured' and rex['has_credentials']
        assert client.get('/api/records/listings').json()['mode']=='demo'
        assert 'TEST-ONLY-REX-SECRET' not in json.dumps(data)
        checks.append('Credential JSON upload, encrypted save, redacted status and no premature live data')
        page.locator('.nav-item[data-nav=team]').click();page.wait_for_timeout(200)
        page.locator('[data-action=invite]').click();page.locator('#f-name').fill('Invited UI Person');page.locator('#f-email').fill('invite-ui@agency.example')
        page.locator('#invite-role').select_option('agent');page.locator('#invite-form button[type=submit]').click();page.wait_for_selector('#invite-url')
        assert '#join?token=' in page.locator('#invite-url').input_value();page.keyboard.press('Escape')
        checks.append('Team invitation generated without sending email')
        page.locator('.nav-item[data-nav=settings]').click();page.wait_for_selector('#settings-form')
        page.locator('[name=demo_enabled]').uncheck();page.locator('#settings-form button[type=submit]').click();page.wait_for_timeout(250)
        assert client.get('/api/records/listings').json()['mode']=='unavailable'
        checks.append('Workspace settings switch off samples in backend data')
        page.locator('[data-action=logout]').click();page.wait_for_selector('#auth-login')
        page.locator('#f-email').fill('ui@agency.example');page.locator('#f-password').fill('Test-Only-Private-Passphrase')
        page.locator('#auth-login button[type=submit]').click();page.wait_for_selector('#auth-mfa')
        page.locator('#f-code').fill(codes[0]);page.locator('#auth-mfa button[type=submit]').click();page.wait_for_selector('.metric')
        assert client.get('/api/records/tasks').json()['total']==1
        checks.append('Logout, password login, recovery-code MFA, persisted task after reauthentication')
        assert not errors,errors;b.close()
report={'method':'Chromium UI with in-process FastAPI bridge; browser networking/cookies and provider connections not covered','checks':checks,'javascript_errors':errors,'result':'passed'}
(out/'browser-api-report.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
