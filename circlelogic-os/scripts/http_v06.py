"""v06 direct-key real loopback HTTP checks using run.py and an isolated database; no external providers."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import httpx
from cryptography.fernet import Fernet
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.config import Settings
from app.provision import bootstrap_testing_account
from app.security import otp
p=argparse.ArgumentParser();p.add_argument('--output',default=str(ROOT/'docs/evidence-v06/http-report.json'));args=p.parse_args()
checks=[]
def check(name,value=True):
    assert value,name
    checks.append(name)
with tempfile.TemporaryDirectory() as directory:
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    origin=f'http://127.0.0.1:{port}'
    key=Fernet.generate_key().decode()
    settings=Settings(Path(directory),origin,'test',key,False,'')
    bootstrap_testing_account(settings)
    env={**os.environ,'PYTHONPATH':str(ROOT/'backend'),'DATA_DIR':directory,'PUBLIC_ORIGIN':origin,'VAULT_KEY':key,'APP_ENV':'test','ALLOW_SIGNUP':'false'}
    with open(Path(directory)/'server.log','w') as log:
        process=subprocess.Popen([sys.executable,'run.py','--no-browser'],cwd=ROOT,env=env,stdout=log,stderr=log)
        try:
            with httpx.Client(base_url=origin,timeout=10) as client:
                for _ in range(80):
                    try:
                        if client.get('/api/health').status_code==200:break
                    except httpx.HTTPError:pass
                    time.sleep(.1)
                else:raise RuntimeError('Loopback server did not start.')
                check('Real loopback server starts through the new local launcher',client.get('/api/health').json()['version']=='0.6.0')
                check('Unknown Host header rejected over real HTTP',client.get('/api/health',headers={'Host':'untrusted.example'}).status_code==400)
                check('Readiness endpoint needs MFA',client.get('/api/pilot/readiness').status_code==401)
                page=client.get('/')
                check('Frontend index served over HTTP',page.status_code==200 and 'Real Estate Brain' in page.text)
                for name in ['styles.css','icons.js','guides.js','app.js']:
                    r=client.get('/src/'+name);check('Frontend asset served: '+name,r.status_code==200 and len(r.content)>100)
                check('Company logo served',client.get('/assets/circlelogic-logo.svg').status_code==200)
                check('Anonymous dashboard is denied',client.get('/api/brain/dashboard').status_code==401)
                def post(path,body):
                    session=client.get('/api/auth/session').json()
                    return client.post(path,json=body,headers={'Origin':origin,'X-CSRF-Token':session.get('csrf','')})
                r=post('/api/auth/login',{'username':'testing123','password':'testing12345'})
                check('Username login returns enrolment stage',r.status_code==200 and r.json()['stage']=='enrol')
                cookie=r.headers['set-cookie'].lower()
                check('Session cookie is HttpOnly SameSite Lax API-scoped','httponly' in cookie and 'samesite=lax' in cookie and 'path=/api' in cookie)
                check('Password-only session cannot read dashboard',client.get('/api/brain/dashboard').status_code==401)
                secret=client.get('/api/auth/enrolment').json()['secret']
                r=post('/api/auth/mfa',{'code':otp(secret,int(time.time()//30))})
                check('TOTP enrolment completes over HTTP',r.status_code==200 and len(r.json()['recovery_codes'])==8)
                response=client.get('/api/brain/dashboard');data=response.json()
                check('Fresh workspace is empty after MFA',data['mode']=='empty' and all(m['value'] is None for m in data['metrics']))
                check('Five connections returned',len(client.get('/api/brain/connections').json()['connections'])==5)
                check('API response disables caching and restricts framing',response.headers['cache-control']=='no-store' and response.headers['x-frame-options']=='DENY')
                runtime=client.get('/api/pilot/readiness').json()
                check('Readiness confirms actual database and vault checks',runtime['database_available'] and runtime['vault_roundtrip_ok'])
                check('Published testing workspace flagged in running backend',runtime['testing_workspace'])
                check('Callback agrees with the actual listening port',runtime['microsoft_callback']==origin+'/api/oauth/microsoft/callback')
                csrf=client.get('/api/auth/session').json()['csrf']
                headers={'Origin':origin,'X-CSRF-Token':csrf}
                creds={'client_id':'11111111-2222-3333-4444-555555555555','directory_id':'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee','client_secret':'SYNTHETIC-SECRET'}
                ids={k:v for k,v in creds.items() if k!='client_secret'}
                missing=post('/api/integrations/microsoft/key',{'key':creds['client_secret']})
                check('Direct paste requires saved provider identifiers',missing.status_code==400 and 'Setup guide' in missing.text)
                setup=client.put('/api/integrations/microsoft/setup',json={'values':ids},headers=headers)
                check('One-time IDs save over real HTTP',setup.status_code==200)
                check('Setup alone is not a connected integration',not client.get('/api/integrations/microsoft/diagnostics').json()['credentials_saved'])
                visible=client.get('/api/integrations/microsoft/setup')
                check('Setup read-back contains IDs only',visible.json()['values']==ids and 'client_secret' not in visible.text)
                wrong=post('/api/integrations/microsoft/key',{'key':'testing12345'})
                check('App test login rejected as provider key',wrong.status_code==400)
                saved=post('/api/integrations/microsoft/key',{'key':creds['client_secret']})
                check('Direct secret paste works over real HTTP',saved.status_code==200)
                diagnostic=client.get('/api/integrations/microsoft/diagnostics')
                check('Credential saving is not marked connected',diagnostic.json()['status']=='configured' and diagnostic.json()['next_action']=='authorise')
                check('Saved credentials never echoed by diagnostics',all(x not in diagnostic.text for x in creds.values()))
                auth=post('/api/integrations/microsoft/authorise',{})
                check('Server builds Microsoft authorisation URL',auth.status_code==200 and auth.json()['url'].startswith('https://login.microsoftonline.com/'))
                check('Token exchange is protected against invented state',client.get('/api/oauth/microsoft/callback?state=wrong&code=fake').status_code==400)
                invalid=client.put('/api/integrations/microsoft',json={'values':{'client_secret':{'secret':'SYNTHETIC-NO-ECHO'}}},headers=headers)
                check('Validation responses omit sensitive inputs',invalid.status_code==422 and 'SYNTHETIC-NO-ECHO' not in invalid.text)
                disconnect=client.delete('/api/integrations/microsoft',headers={**headers,'Content-Type':'application/json'})
                check('Disconnect clears saved credentials over HTTP',disconnect.status_code==200 and not client.get('/api/integrations/microsoft/diagnostics').json()['credentials_saved'])
                check('Disconnect also clears one-time provider IDs',not client.get('/api/integrations/microsoft/setup').json()['ready'])
                check('Incorrect origin rejected',client.post('/api/auth/logout',json={},headers={'Origin':'https://untrusted.invalid'}).status_code==403)
                check('Missing CSRF rejected',client.post('/api/auth/logout',json={},headers={'Origin':origin}).status_code==403)
                check('Authenticated logout works',post('/api/auth/logout',{}).status_code==200)
                check('Logout removes access',client.get('/api/brain/dashboard').status_code==401)
        finally:
            process.terminate()
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.kill();process.wait()
report={'checks_passed':len(checks),'checks':checks,'transport':'Real localhost HTTP with httpx and Uvicorn. Not browser-native networking or HTTPS.','external_provider_requests':0}
out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
