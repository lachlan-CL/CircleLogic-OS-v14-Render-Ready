"""Embedded Chromium team and invitation UI checks with a FastAPI test bridge.

Synthetic identities only. No external providers, emails or production TLS.
Browser networking is not used. Storage persistence is tested with an explicit
in-memory Storage adapter and a fresh document. Requires playwright and Chromium.
"""
import argparse
import json
from pathlib import Path
import base64
import sys
import tempfile
import time
from fastapi.testclient import TestClient
from cryptography.fernet import Fernet
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.config import Settings
from app.main import create_app
from app.security import otp

p=argparse.ArgumentParser();p.add_argument('--chromium',default='/usr/bin/chromium');p.add_argument('--output',default=str(ROOT/'docs/ui-test-output'));args=p.parse_args()
out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
checks=[];errors=[]

def nav(page,route):
    page.evaluate('(route)=>location.hash=route',route)
    page.wait_for_timeout(180)
    if route=='team':page.wait_for_selector('.team-grid')

def submit(page,form):
    page.locator(f'#{form} button[type=submit]').click()

def wait_name(page,name):
    page.get_by_role('heading',name=name,exact=False).first.wait_for()

def load_preview(page, snapshot=None):
    data=json.dumps(snapshot or {}).replace('</','<\\/')
    shim="<script>window.__testStorage="+data+";Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem:k=>window.__testStorage[k]??null,setItem:(k,v)=>window.__testStorage[k]=String(v),removeItem:k=>delete window.__testStorage[k]}});</script>"
    html=(ROOT/'CircleLogic-OS-Interactive-Preview.html').read_text().replace('<head>','<head>'+shim)
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_content(html);page.wait_for_selector('.metric')

def load_app(page,client,fragment=''):
    def bridge(path,options):
        assert path.startswith('/api/')
        r=client.request(options.get('method','GET'),path,content=options.get('body'),headers={**options.get('headers',{}),'Origin':ORIGIN})
        return {'status':r.status_code,'body':r.text,'headers':{'Content-Type':r.headers.get('content-type','application/json')}}
    page.expose_function('testApiBridge',bridge)
    html=(ROOT/'frontend/index.html').read_text().replace('<link rel="stylesheet" href="/src/styles.css">','<style>'+(ROOT/'frontend/src/styles.css').read_text()+'</style>')
    for name in ['icons.js','app.js']:html=html.replace(f'<script defer src="/src/{name}"></script>','')
    shim="location.hash="+json.dumps(fragment)+";window.fetch=async(path,options={})=>{const r=await window.testApiBridge(path,options);return new Response(r.body,{status:r.status,headers:r.headers});};"
    scripts='<script>'+shim+'</script>'+''.join('<script>'+(ROOT/'frontend/src'/name).read_text()+'</script>' for name in ['icons.js','app.js'])
    html=html.replace('</body>',scripts+'</body>')
    logo='data:image/svg+xml;base64,'+base64.b64encode((ROOT/'frontend/assets/circlelogic-logo.svg').read_bytes()).decode()
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_content(html.replace('/assets/circlelogic-logo.svg',logo))

ORIGIN='http://localhost:8000'
with tempfile.TemporaryDirectory() as temp:
    app=create_app(Settings(Path(temp),ORIGIN,'test',Fernet.generate_key().decode(),True,''))
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=args.chromium,headless=True,args=['--no-sandbox'])
        context=browser.new_context(viewport={'width':1512,'height':982})
        page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        load_preview(page);nav(page,'team');page.wait_for_selector('.team-grid')
        assert page.title()=='CircleLogic OS | Interactive preview'
        assert page.locator('.brand-logo').evaluate('(img)=>img.complete && img.naturalWidth>0')
        assert page.locator('.sample-profile').count()==4
        page.screenshot(path=str(out/'team-desktop.png'),full_page=True)
        # Replace current sample owner and an existing agent; preserve stable IDs.
        page.locator('[data-action=edit-member][data-id=preview-ava]').click()
        page.locator('#f-name').fill('Example Owner');page.locator('#f-email').fill('example.owner@example.invalid');submit(page,'member-form')
        wait_name(page,'Example Owner')
        assert page.locator('.profile-text strong').inner_text()=='Example Owner'
        page.locator('[data-action=invite]').click()
        page.locator('#f-name').fill('Example Agent');page.locator('#f-email').fill('example.agent@example.invalid')
        page.locator('#replace-profile').select_option('preview-james');submit(page,'invite-form');wait_name(page,'Example Agent')
        assert page.locator('[data-member-id=preview-james]').count()==1
        assert 'James Chen' not in page.inner_text('#page')
        checks.append('Replace sample owner and agent; update sidebar and preserve profile identifiers')
        page.locator('[data-action=invite]').click();page.locator('#f-name').fill('New Colleague')
        page.locator('#f-email').fill('new.colleague@example.invalid');page.locator('#invite-role').select_option('finance')
        submit(page,'invite-form');wait_name(page,'New Colleague')
        new_id=page.locator('.team-card').filter(has_text='new.colleague@example.invalid').get_attribute('data-member-id')
        assert page.locator('.team-card').count()==5
        # Duplicate email errors remain in the form.
        page.locator('[data-action=invite]').click();page.locator('#f-name').fill('Duplicate Example')
        page.locator('#f-email').fill('NEW.COLLEAGUE@EXAMPLE.INVALID');submit(page,'invite-form');page.wait_for_selector('#invite-form .error-box')
        assert 'already' in page.inner_text('#invite-form .error-box');page.keyboard.press('Escape')
        snapshot=page.evaluate('window.__testStorage');page.close();page=context.new_page();load_preview(page,snapshot);nav(page,'team');wait_name(page,'New Colleague');assert page.locator('.profile-text strong').inner_text()=='Example Owner'
        checks.append('Add profile, reject duplicate email, and persist team via serialized Storage state in a fresh document (storage adapter)')
        # Assign, rename and reassign a real draft task, then verify persistence.
        page.locator('[data-action=new-task]').click();page.wait_for_selector('#task-form')
        page.locator('#f-title').fill('Preview assigned follow-up');page.locator('#task-assignee').select_option('preview-james');submit(page,'task-form')
        page.wait_for_selector('tr[data-detail]');assert 'Example Agent' in page.inner_text('#page')
        nav(page,'team');page.locator('[data-action=edit-member][data-id=preview-james]').click()
        page.locator('#f-name').fill('Updated Agent');submit(page,'member-form');wait_name(page,'Updated Agent')
        nav(page,'tasks');assert 'Updated Agent' in page.inner_text('#page')
        page.locator('tr[data-detail]').first.click();page.wait_for_selector('[data-action=reassign-task]')
        page.locator('[data-action=reassign-task]').click();page.wait_for_selector('#reassign-task-form')
        page.locator('#task-assignee').select_option(new_id);submit(page,'reassign-task-form')
        page.wait_for_timeout(160);assert 'New Colleague' in page.inner_text('#page')
        snapshot=page.evaluate('window.__testStorage');page.close();page=context.new_page();load_preview(page,snapshot);nav(page,'tasks');page.wait_for_selector('tr[data-detail]');assert 'New Colleague' in page.inner_text('#page')
        checks.append('Assign draft task, propagate member rename, reassign task and rehydrate in a fresh document (storage adapter)')
        nav(page,'team');page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(350)
        assert page.locator('[data-action=invite]').is_visible()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        page.screenshot(path=str(out/'team-mobile.png'),full_page=True)
        page.locator('[data-action=invite]').click();page.wait_for_selector('#invite-form')
        assert page.locator('#f-name').is_visible();page.keyboard.press('Escape')
        checks.append('Mobile team cards, visible Add person button, no page overflow and usable form')
        page.set_viewport_size({'width':1512,'height':982});nav(page,'dashboard')
        page.screenshot(path=str(out/'dashboard-branded.png'),full_page=True)
        # Reset really removes all custom profiles and draft tasks.
        nav(page,'team');page.once('dialog',lambda d:d.accept());page.locator('[data-action=reset-preview]').click()
        page.wait_for_timeout(200);assert page.locator('.sample-profile').count()==4
        snapshot=page.evaluate('window.__testStorage');page.close();page=context.new_page();load_preview(page,snapshot);nav(page,'team');page.wait_for_selector('.team-grid');assert 'New Colleague' not in page.inner_text('#page')
        checks.append('Preview reset removes browser-only edits and restores the sample team')
        context.close()
        # Full UI workflow through isolated FastAPI TestClients, not browser networking.
        owner_context=browser.new_context(viewport={'width':1512,'height':982})
        owner=owner_context.new_page();owner.on('pageerror',lambda e:errors.append(str(e)))
        owner_client=TestClient(app,base_url=ORIGIN);load_app(owner,owner_client);owner.wait_for_selector('#auth-login')
        assert owner.locator('.brand-logo').evaluate('(img)=>img.naturalWidth>0')
        owner.screenshot(path=str(out/'login-branded.png'),full_page=True)
        owner.locator('[data-action=auth-register]').click()
        for k,v in {'name':'Test Owner','agency':'Synthetic Test Workspace','email':'owner@ui.example','password':'Synthetic-Test-Only-Passphrase-2026'}.items():owner.locator('#f-'+k).fill(v)
        submit(owner,'auth-register');owner.wait_for_selector('.qr')
        secret=owner_client.get('/api/auth/enrolment').json()['secret']
        owner.locator('#f-code').fill(otp(secret,int(time.time()//30)));submit(owner,'auth-mfa')
        owner.wait_for_selector('#recovery-saved');owner.locator('#recovery-saved').check();owner.locator('[data-action=finish-enrolment]').click();owner.wait_for_selector('.metric')
        nav(owner,'team');assert owner.locator('.team-card').count()==1
        owner.locator('[data-action=invite]').click();owner.locator('#f-name').fill('Invited Colleague');owner.locator('#f-email').fill('colleague@ui.example')
        submit(owner,'invite-form');owner.wait_for_selector('#invite-url')
        old_link=owner.locator('#invite-url').input_value();owner.keyboard.press('Escape')
        assert owner.locator('.invitation-row').count()==1
        owner.locator('[data-action=reissue-invite]').click();owner.locator('#f-name').fill('Updated Colleague');submit(owner,'reissue-invite-form');owner.wait_for_selector('#invite-url')
        link=owner.locator('#invite-url').input_value();assert link!=old_link;owner.keyboard.press('Escape')
        owner.screenshot(path=str(out/'team-live-pending.png'),full_page=True)
        checks.append('UI-to-FastAPI signup, authenticator enrollment, persisted named invitation and reissue')
        invalid_context=browser.new_context();invalid=invalid_context.new_page();load_app(invalid,TestClient(app,base_url=ORIGIN),'#'+old_link.split('#')[1])
        invalid.wait_for_selector('.auth-card h2');assert 'Invitation unavailable' in invalid.inner_text('.auth-card')
        invalid_context.close()
        colleague_context=browser.new_context(viewport={'width':1280,'height':900})
        colleague=colleague_context.new_page();colleague.on('pageerror',lambda e:errors.append(str(e)))
        colleague_client=TestClient(app,base_url=ORIGIN);load_app(colleague,colleague_client,'#'+link.split('#')[1]);colleague.wait_for_selector('#auth-register')
        assert colleague.locator('#f-name').input_value()=='Updated Colleague'
        assert colleague.locator('#f-email').input_value()=='colleague@ui.example'
        colleague.locator('#f-password').fill('Colleague-Private-Test-Passphrase-2026');submit(colleague,'auth-register');colleague.wait_for_selector('.qr')
        assert colleague_client.get('/api/dashboard').status_code==401
        owner.close();owner=owner_context.new_page();load_app(owner,owner_client,'#team');owner.wait_for_selector('.team-grid');assert '2FA setup pending' in owner.inner_text('#page')
        owner.locator('[data-action=new-task]').click();owner.wait_for_selector('#task-assignee')
        assert 'Updated Colleague' not in owner.inner_text('#task-assignee');owner.keyboard.press('Escape')
        secret=colleague_client.get('/api/auth/enrolment').json()['secret']
        colleague.locator('#f-code').fill(otp(secret,int(time.time()//30)));submit(colleague,'auth-mfa');colleague.wait_for_selector('#recovery-saved')
        colleague.locator('#recovery-saved').check();colleague.locator('[data-action=finish-enrolment]').click();colleague.wait_for_selector('.metric')
        assert colleague.locator('.nav-item[data-nav=team]').count()==0
        assert colleague.locator('.nav-item[data-nav=invoices]').count()==0
        owner.close();owner=owner_context.new_page();load_app(owner,owner_client,'#team');owner.wait_for_selector('.team-grid');assert owner.locator('.invitation-row').count()==0
        member_id=owner.locator('.team-card').filter(has_text='colleague@ui.example').get_attribute('data-member-id')
        owner.locator('[data-action=new-task]').click();owner.wait_for_selector('#task-assignee')
        owner.locator('#f-title').fill('Real workspace assigned task');owner.locator('#task-assignee').select_option(member_id);submit(owner,'task-form')
        owner.wait_for_selector('tr[data-detail]');assert 'Updated Colleague' in owner.inner_text('#page')
        checks.append('Invite accepted in separate browser context; own MFA required, correct role, task assignment enabled only after enrollment')
        # Deactivation invalidates the member's TestClient session at the API boundary.
        nav(owner,'team');owner.locator(f'[data-action=edit-member][data-id="{member_id}"]').click()
        owner.locator('[name=active]').uncheck();submit(owner,'member-form');owner.wait_for_timeout(200)
        assert colleague_client.get('/api/dashboard').status_code==401
        colleague.close();colleague=colleague_context.new_page();load_app(colleague,colleague_client);colleague.wait_for_selector('#auth-login')
        checks.append('Admin deactivation revokes a test-backed session and blocks further workspace access')
        assert not errors,errors
        owner_context.close();colleague_context.close();browser.close()
report={'method':'Embedded Chromium UI with isolated FastAPI TestClients and a simulated Storage adapter; synthetic identities only','checks':checks,'javascript_errors':errors,'result':'passed','not_covered':['Actual browser networking/cookies/TLS','Actual browser localStorage/file-origin persistence','External email delivery','Live provider accounts','Production TLS or hosting','Other browsers or mobile operating systems','Independent security audit']}
(out/'browser-team-v03-report.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
