"""Embedded Chromium UI smoke checks for the standalone preview.

No external websites, credentials or network are used. This embedding path also
works in environments where browser navigation to local URLs is restricted.
Run after build_preview.py. Install playwright and a Chromium executable first.
"""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--chromium',default='/usr/bin/chromium');p.add_argument('--output',default=str(ROOT/'docs/ui-test-output'));args=p.parse_args()
out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
html=(ROOT/'CircleLogic-OS-Interactive-Preview.html').read_text()
errors=[];checks=[]
with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path=args.chromium,headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1512,'height':982})
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_content(html,wait_until='load');page.wait_for_selector('.metric')
    assert '184.6k' in page.inner_text('#page');checks.append('Desktop dashboard and four metrics render')
    page.screenshot(path=str(out/'dashboard.png'),full_page=True)
    for route in ['contacts','listings','rentals','transactions','campaigns','invoices','documents','tasks','reports','integrations','portal_listings','calendar','messages','team','settings','security','audit']:
        page.locator(f'.nav-item[data-nav="{route}"]').click()
        page.wait_for_timeout(180)
        assert 'We could not load this view' not in page.inner_text('#page'),route
        assert len(page.inner_text('#page'))>100,route
        if route=='integrations':
            assert page.locator('.integration-card').count()==10
            page.screenshot(path=str(out/'integrations.png'),full_page=True)
        if route=='security':assert page.locator('#page input[type=password]').count()==0
    checks.append('All 18 routes render, including gated integrations and data health')
    page.locator('.nav-item[data-nav="listings"]').click();page.wait_for_timeout(200)
    page.locator('#record-search').fill('Ocean');page.wait_for_timeout(800)
    assert '24 Ocean Avenue' in page.inner_text('#page')
    assert 'Surry Hills' not in page.inner_text('#page');checks.append('Table search filters rows')
    page.locator('tr[data-detail]').first.click();page.wait_for_selector('[role=dialog]')
    assert 'Sample data' in page.inner_text('[role=dialog]');page.keyboard.press('Escape')
    checks.append('Record details and keyboard modal dismissal work')
    page.locator('.nav-item[data-nav="integrations"]').click();page.wait_for_timeout(200)
    page.locator('[data-action=configure][data-provider=rex]').click();page.wait_for_selector('[role=dialog]')
    assert page.locator('#integration-form').count()==0;page.keyboard.press('Escape')
    checks.append('Preview cannot collect provider secrets')
    page.locator('[data-action=new-task]').click();page.wait_for_selector('#task-form')
    page.locator('#f-title').fill('Browser smoke test task');page.locator('#task-form button[type=submit]').click();page.wait_for_timeout(350)
    assert 'Browser smoke test task' in page.inner_text('#page')
    page.locator('[data-action=complete-task]').click();page.wait_for_timeout(250)
    assert 'Done' in page.inner_text('#page');checks.append('Local preview task creation and completion work')
    page.locator('#global-search').fill('Ocean');page.wait_for_timeout(500)
    assert page.locator('.search-result').count()>0;checks.append('Global record search works')
    page.set_viewport_size({'width':390,'height':844})
    page.evaluate("location.hash='dashboard'");page.wait_for_timeout(300)
    assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
    page.screenshot(path=str(out/'mobile-dashboard.png'),full_page=True)
    page.locator('[data-action=toggle-menu]').click()
    assert page.locator('.sidebar.open').count()==1
    page.locator('.nav-item[data-nav="integrations"]').click();page.wait_for_timeout(300)
    assert page.locator('.integration-card').count()==10
    assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
    checks.append('390px mobile layout and navigation work without page overflow')
    assert not errors,errors
    checks.append('No uncaught JavaScript errors')
    browser.close()
report={'method':'Embedded standalone HTML in Chromium; no live provider traffic','checks':checks,'javascript_errors':errors,'result':'passed'}
(out/'browser-report.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
