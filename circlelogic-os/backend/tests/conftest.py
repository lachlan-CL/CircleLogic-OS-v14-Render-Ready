import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import time
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.security import otp

ORIGIN='http://localhost:8000'
PASSWORD='Example-private-passphrase-2026'

@pytest.fixture
def app(tmp_path):
    return create_app(Settings(tmp_path,ORIGIN,'test',Fernet.generate_key().decode(),True,''))

def request(client,method,path,body=None,csrf=True):
    headers={'Origin':ORIGIN,'Content-Type':'application/json'}
    if csrf:
        session=client.get('/api/auth/session').json()
        if session.get('csrf'):headers['X-CSRF-Token']=session['csrf']
    return client.request(method,path,json=body or {},headers=headers)

def register(app,email='owner@agency.example',agency='Test Agency',invite=''):
    c=TestClient(app,base_url=ORIGIN)
    r=request(c,'POST','/api/auth/register',{'agency':agency,'name':email.split('@')[0].title(),'email':email,'password':PASSWORD,'invite_token':invite})
    assert r.status_code==201,r.text
    secret=c.get('/api/auth/enrolment').json()['secret']
    r=request(c,'POST','/api/auth/mfa',{'code':otp(secret,int(time.time()//30))})
    assert r.status_code==200,r.text
    c.secret=secret;c.recovery=r.json()['recovery_codes'];c.email=email
    c.user=c.get('/api/auth/session').json()['user']
    return c

@pytest.fixture
def owner(app):return register(app)

def add_member(app,owner,role='agent',email='agent@agency.example'):
    r=request(owner,'POST','/api/team/invite',{'email':email,'role':role})
    assert r.status_code==200,r.text
    invitation=r.json()['url'].split('token=')[1]
    return register(app,email,invite=invitation)
