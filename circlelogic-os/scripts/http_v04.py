"""Real loopback HTTP smoke checks with an isolated database; no external providers."""
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
p=argparse.ArgumentParser();p.add_argument('--output',default=str(ROOT/'docs/http-test-output.json'));args=p.parse_args()
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
        process=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:create_app','--factory','--host','127.0.0.1','--port',str(port),'--no-access-log'],cwd=ROOT,env=env,stdout=log,stderr=log)
        try:
            with httpx.Client(base_url=origin,timeout=10) as client:
                for _ in range(80):
                    try:
                        if client.get('/api/health').status_code==200:break
                    except httpx.HTTPError:pass
                    time.sleep(.1)
                else:raise RuntimeError('Loopback server did not start.')
                check('Real loopback HTTP server starts and responds to health check')
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
