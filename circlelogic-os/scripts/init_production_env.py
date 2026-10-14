"""Generate a non-overwriting local production configuration template.

Run on the approved deployment host. Do not email, commit or paste the output
file into chat. Migrate secrets to the operator's approved secret manager.
"""
import argparse
import os
from pathlib import Path
import secrets
from urllib.parse import urlparse
from cryptography.fernet import Fernet
p=argparse.ArgumentParser()
p.add_argument('--origin',required=True,help='Example: https://agencyos.your-company.example')
p.add_argument('--output',default='.env.production')
a=p.parse_args();u=urlparse(a.origin)
if u.scheme!='https' or not u.hostname or u.path not in ('','/') or u.query or u.fragment or u.port not in (None,443):
    p.error('Use an HTTPS origin on port 443, without a path, query or fragment.')
path=Path(a.output)
fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as f:
    f.write('APP_ENV=production\nALLOW_SIGNUP=false\n')
    f.write('PUBLIC_ORIGIN='+a.origin.rstrip('/')+'\nDOMAIN='+u.hostname+'\n')
    f.write('VAULT_KEY='+Fernet.generate_key().decode()+'\n')
    f.write('PROVISION_TOKEN='+secrets.token_urlsafe(48)+'\n')
print('Created',str(path),'- keep this file private and back up the vault key separately.')
print('Review docs/DEPLOYMENT.md before starting any public service.')
