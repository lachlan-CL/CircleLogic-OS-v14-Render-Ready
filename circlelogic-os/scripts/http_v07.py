"""v07 real loopback HTTP checks for Google Calendar setup. No external provider traffic."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlparse, parse_qs
import httpx
from cryptography.fernet import Fernet

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.config import Settings
from app.provision import bootstrap_testing_account
from app.security import otp

p=argparse.ArgumentParser();p.add_argument('--output',default=str(ROOT/'docs/evidence-v07/http-report.json'));args=p.parse_args()
checks=[]
def check(name,value=True):
    assert value,name;checks.append(name)

with tempfile.TemporaryDirectory() as directory:
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    origin=f'http://127.0.0.1:{port}'
    key=Fernet.generate_key().decode();settings=Settings(Path(directory),origin,'test',key,False,'')
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
                check('v07 starts through run.py',client.get('/api/health').json()['version']=='0.7.0')
                index=client.get('/')
                check('Frontend v07 assets are referenced',index.status_code==200 and 'v=0.7.0' in index.text)
                def post(path,body):
                    session=client.get('/api/auth/session').json();return client.post(path,json=body,headers={'Origin':origin,'X-CSRF-Token':session.get('csrf','')})
                r=post('/api/auth/login',{'username':'testing123','password':'testing12345'})
                secret=client.get('/api/auth/enrolment').json()['secret'];r=post('/api/auth/mfa',{'code':otp(secret,int(time.time()//30))})
                check('MFA completes over real HTTP',r.status_code==200)
                brain=client.get('/api/brain/dashboard').json();check('Fresh dashboard is empty',brain['mode']=='empty')
                connections=client.get('/api/brain/connections').json()['connections']
                check('Six Brain connections are returned',len(connections)==6)
                check('Google Calendar is present',any(c['id']=='google' for c in connections))
                runtime=client.get('/api/pilot/readiness').json()
                check('Exact Google callback follows actual origin',runtime['google_callback']==origin+'/api/oauth/google/callback')
                csrf=client.get('/api/auth/session').json()['csrf'];headers={'Origin':origin,'X-CSRF-Token':csrf}
                client_id='1234567890-syntheticcalendar.apps.googleusercontent.com';client_secret='SYNTHETIC-GOOGLE-SECRET'
                missing=post('/api/integrations/google/key',{'key':client_secret})
                check('Google key paste requires client ID setup first',missing.status_code==400 and 'Setup guide' in missing.text)
                setup=client.put('/api/integrations/google/setup',json={'values':{'client_id':client_id}},headers=headers)
                check('Google client ID setup saves',setup.status_code==200)
                setup_read=client.get('/api/integrations/google/setup').json()
                check('Setup read-back contains only client ID',setup_read['values']=={'client_id':client_id} and 'secret' not in json.dumps(setup_read).lower())
                saved=post('/api/integrations/google/key',{'key':client_secret})
                check('Single-field Google secret paste saves',saved.status_code==200)
                diag=client.get('/api/integrations/google/diagnostics').json()
                check('Saved key remains configured, not connected',diag['credentials_saved'] and diag['status']=='configured' and diag['next_action']=='authorise')
                check('Diagnostics does not echo secret',client_secret not in json.dumps(diag))
                auth=post('/api/integrations/google/authorise',{})
                check('Google authorisation URL builds without contacting Google',auth.status_code==200)
                u=urlparse(auth.json()['url']);q=parse_qs(u.query)
                check('Authorisation host is Google Accounts',u.scheme=='https' and u.hostname=='accounts.google.com')
                check('Read-only Calendar scope is requested',q['scope']==['https://www.googleapis.com/auth/calendar.events.readonly'])
                check('Offline access and explicit consent are requested',q['access_type']==['offline'] and q['include_granted_scopes']==['true'] and 'consent' in q['prompt'][0])
                check('Client secret is not exposed in authorisation URL',client_secret not in auth.json()['url'])
                check('Invalid callback state is rejected',client.get('/api/oauth/google/callback?state=wrong&code=fake').status_code==400)
                disconnect=client.delete('/api/integrations/google',headers={**headers,'Content-Type':'application/json'})
                check('Google disconnect succeeds',disconnect.status_code==200)
                check('Disconnect clears key and setup',not client.get('/api/integrations/google/diagnostics').json()['credentials_saved'] and not client.get('/api/integrations/google/setup').json()['ready'])
        finally:
            process.terminate()
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.kill();process.wait()

report={'checks_passed':len(checks),'checks':checks,'transport':'Real localhost HTTP via httpx and Uvicorn. No native browser networking or HTTPS.','external_provider_requests':0}
out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
