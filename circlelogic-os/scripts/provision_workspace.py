"""Create a distinct workspace from an approved server terminal (not a web page)."""
from pathlib import Path
import argparse
import getpass
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'backend'))
from run import load_env
from app.config import Settings
from app.db import Store
from app.provision import create_workspace
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--agency',required=True)
p.add_argument('--username',required=True)
p.add_argument('--email',required=True)
p.add_argument('--name',required=True)
a=p.parse_args()
load_env()
import os
os.environ.setdefault('DATA_DIR',str(ROOT/'data'))
s=Settings.load()
password=getpass.getpass('Initial password (minimum 12 characters): ')
if password!=getpass.getpass('Repeat password: '):
    raise SystemExit('Passwords do not match.')
try:
    result=create_workspace(Store(s.database),agency=a.agency,name=a.name,username=a.username,email=a.email,password=password)
except Exception as exc:
    raise SystemExit(getattr(exc,'detail',None) or str(exc)) from None
print('Created workspace:',result['workspace_id'])
print('Username:',result['username'])
print('The first sign-in requires authenticator enrolment. Share access details privately.')
