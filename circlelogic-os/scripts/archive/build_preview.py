"""Build a self-contained design preview, separate from the customer application."""
import base64
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.catalog import CATALOG, BRAIN_PROVIDERS
providers=[]
for key in BRAIN_PROVIDERS:
    providers.append({'id':key,**CATALOG[key], 'manageable':True,'private':bool(CATALOG[key].get('private')),
                      'status':'not_connected','has_credentials':False,'last_success':None,'error':None})
html=(ROOT/'frontend/index.html').read_text()
html=html.replace('CircleLogic OS | Real Estate Brain','CircleLogic OS | Interactive design preview')
html=html.replace('<link rel="stylesheet" href="/src/styles.css">','<style>'+(ROOT/'frontend/src/styles.css').read_text()+'</style>')
for file in ['icons.js','guides.js','app.js']:
    html=html.replace(f'<script defer src="/src/{file}"></script>','')
scripts=[(ROOT/'frontend/src/icons.js').read_text(),(ROOT/'frontend/src/guides.js').read_text(),
         'window.PREVIEW_CONNECTIONS='+json.dumps(providers)+';', (ROOT/'preview/runtime.js').read_text(),(ROOT/'frontend/src/app.js').read_text()]
html=html.replace('</body>',''.join('<script>'+script.replace('</script','<\\/script')+'</script>' for script in scripts)+'</body>')
logo='data:image/svg+xml;base64,'+base64.b64encode((ROOT/'frontend/assets/circlelogic-logo.svg').read_bytes()).decode()
html=html.replace('/assets/circlelogic-logo.svg',logo)
html=html.replace('<meta charset="UTF-8">','<meta charset="UTF-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'unsafe-inline\'; style-src \'unsafe-inline\'; img-src data:; connect-src \'none\'; form-action \'none\'; base-uri \'none\'">')
path=ROOT/'CircleLogic-OS-v04-Interactive-Preview.html';path.write_text(html)
print('Built:',path,'bytes:',len(html.encode()))
