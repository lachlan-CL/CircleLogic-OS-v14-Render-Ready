"""RE Unite dashboard helpers.

This version keeps Google Calendar live while providing tasteful demonstration
content for the other real-estate modules when no approved live connector is
available yet.
"""
from __future__ import annotations
from datetime import datetime, timezone
import json
import time
from .catalog import CATALOG
from .security import ROLES
from .services import FRESH_SECONDS

ACCESS={'agentbox':'contacts','rea':'campaigns','rpdata':'contacts','proping':'contacts','microsoft':'calendar','google':'calendar'}
EXAMPLE_PROVIDERS={'agentbox','rea','rpdata','proping'}

EXAMPLE_METRICS={
    'contacts': {'value':2841,'delta':12,'series':[22,27,24,29,33,36,41]},
    'enquiries': {'value':148,'delta':18,'series':[9,11,10,14,13,18,22]},
    'buyers': {'value':64,'delta':9,'series':[5,6,8,7,9,10,12]},
    'listings': {'value':37,'delta':4,'series':[24,23,26,27,28,31,37]},
    'properties': {'value':1258,'delta':7,'series':[14,16,15,18,17,19,21]},
}
EXAMPLE_BUYER_ROWS=[
    {'title':'17 Harbour View Avenue','suburb':'Coogee','score':94,'stage':'Appraisal booked','weekly_change':'+14%'},
    {'title':'4 Melrose Crescent','suburb':'Maroubra','score':88,'stage':'Second inspection','weekly_change':'+10%'},
    {'title':'26 The Esplanade','suburb':'Drummoyne','score':83,'stage':'Offer preparing','weekly_change':'+8%'},
    {'title':'8 Parkside Lane','suburb':'Leichhardt','score':79,'stage':'Finance confirmed','weekly_change':'+6%'},
    {'title':'11 Aurora Street','suburb':'Lane Cove','score':74,'stage':'Campaign launch','weekly_change':'+4%'},
]
EXAMPLE_MARKET_ROWS=[
    {'title':'New listings','count':12,'status':'+8% vs last week','tone':'warm'},
    {'title':'Price changes','count':7,'status':'4 strategic reductions','tone':'accent'},
    {'title':'Buyer follow-ups','count':28,'status':'15 due today','tone':'success'},
    {'title':'Appraisal opportunities','count':9,'status':'3 high-priority suburbs','tone':'sun'},
    {'title':'Sold activity','count':5,'status':'Average 24 DOM','tone':'plum'},
]


def connection_status(store,user,provider,origin=''):
    meta=CATALOG[provider]
    owner=user['id'] if meta.get('private') else ''
    allowed=ACCESS[provider] in ROLES[user['role']]
    manageable=('integrations' in ROLES[user['role']] and (meta.get('private') or user['role'] in ('owner','admin')))
    c=store.one('SELECT * FROM connections WHERE tenant_id=? AND provider=? AND owner_id=?',
                (user['tenant_id'],provider,owner)) if allowed else None
    if c:
        status=c['status']
        if status=='connected' and (c['last_success'] or 0)<time.time()-FRESH_SECONDS:
            status='stale'
    elif allowed and provider in EXAMPLE_PROVIDERS:
        status='example'
    else:
        status='not_connected' if allowed else 'restricted'
    return {'id':provider,'name':meta['name'],'description':meta['description'],'auth':meta['auth'],
            'implemented':meta['implemented'],'private':bool(meta.get('private')),
            'status':status,'last_success':c['last_success'] if c else None,
            'has_credentials':bool(c and c['credentials'] and manageable),
            'error':c['error'] if c and manageable else None,
            'manageable':bool(manageable),'fields':meta['fields'] if manageable else [],
            'callback':origin+'/api/oauth/'+provider+'/callback' if meta['auth']=='oauth' and manageable else None,
            'docs':meta['docs'],'syncing':bool(c and c['lease_until']>time.time())}


def snapshot(store,user,provider,kind):
    empty={'provider':provider,'kind':kind,'rows':[],'total':None,'synced_at':None,'mode':'unavailable'}
    if ACCESS[provider] not in ROLES[user['role']]:
        return {**empty,'mode':'restricted'}
    owner=user['id'] if CATALOG[provider].get('private') else ''
    c=store.one('SELECT * FROM connections WHERE tenant_id=? AND provider=? AND owner_id=?',
                (user['tenant_id'],provider,owner))
    if not c or c['status']=='disconnected':
        return empty
    snap=store.one('SELECT synced_at FROM snapshots WHERE connection_id=? AND kind=?',(c['id'],kind))
    if not snap:
        return empty
    mode='live' if c['status']=='connected' and snap['synced_at']>=time.time()-FRESH_SECONDS else 'stale'
    rows=store.all('SELECT id,payload FROM records WHERE tenant_id=? AND connection_id=? AND owner_id=? AND kind=? ORDER BY external_id',
                   (user['tenant_id'],c['id'],owner,kind))
    records=[{**json.loads(r['payload']),'id':r['id']} for r in rows]
    return {'provider':provider,'kind':kind,'rows':records,'total':len(records),'mode':mode,'synced_at':snap['synced_at']}


def metric(key,title,source,data,description,icon,derive=None,delta=None,series=None):
    available=data['total'] is not None
    return {
        'id':key,
        'title':title,
        'provider':source,
        'value':(derive(data['rows']) if derive else data['total']) if available else None,
        'mode':data['mode'],
        'synced_at':data['synced_at'],
        'description':description,
        'icon':icon,
        'delta':delta,
        'series':series or [],
    }


def example_metric(key,title,source,description,icon):
    e=EXAMPLE_METRICS[key]
    return {
        'id':key,
        'title':title,
        'provider':source,
        'value':e['value'],
        'mode':'example',
        'synced_at':None,
        'description':description,
        'icon':icon,
        'delta':e['delta'],
        'series':e['series'],
    }


def example_panel(provider,kind,rows,sourcestr):
    return {'provider':provider,'kind':kind,'rows':rows,'total':len(rows),'synced_at':None,'mode':'example','sources':[sourcestr]}


def brain_dashboard(store,user):
    contacts=snapshot(store,user,'agentbox','contacts')
    listings=snapshot(store,user,'agentbox','listings')
    enquiries=snapshot(store,user,'agentbox','enquiries')
    properties=snapshot(store,user,'rpdata','properties')
    campaigns=snapshot(store,user,'rea','campaigns')
    market=snapshot(store,user,'proping','market_alerts')
    google_calendar=snapshot(store,user,'google','calendar')

    calendar_sources=[x for x in (google_calendar,) if x['total'] is not None]
    if calendar_sources:
        calendar={
            'provider':'calendar','kind':'calendar',
            'rows':[dict(row,calendar_source=CATALOG[src['provider']]['name']) for src in calendar_sources for row in src['rows']],
            'total':sum(src['total'] for src in calendar_sources),
            'synced_at':min((src['synced_at'] for src in calendar_sources if src['synced_at'] is not None),default=None),
            'mode':'stale' if any(src['mode']=='stale' for src in calendar_sources) else 'live',
            'sources':[CATALOG[src['provider']]['name'] for src in calendar_sources],
        }
    else:
        calendar={'provider':'calendar','kind':'calendar','rows':[],'total':None,'synced_at':None,'mode':'unavailable','sources':[]}

    metrics=[]
    metrics.append(metric('contacts','Total contacts','agentbox',contacts,'Contacts in the latest approved CRM snapshot.','users',
               delta=EXAMPLE_METRICS['contacts']['delta'] if contacts['total'] is not None else None,
               series=EXAMPLE_METRICS['contacts']['series'] if contacts['total'] is not None else []))
    metrics.append(metric('enquiries','New enquiries','agentbox',enquiries,'New enquiries captured in the current reporting window.','message',
               delta=EXAMPLE_METRICS['enquiries']['delta'] if enquiries['total'] is not None else None,
               series=EXAMPLE_METRICS['enquiries']['series'] if enquiries['total'] is not None else []))
    high_intent_live={'total':None,'mode':'unavailable','synced_at':None,'rows':[]}
    metrics.append(example_metric('buyers','High-intent buyers','rea','Illustrative engagement scorecard shown for demonstration until a live buyer feed is approved.','activity'))
    metrics.append(metric('listings','Active listings','agentbox',listings,'Active, available or published listings in the latest CRM snapshot.','home',
               lambda rows:sum(str(r.get('status','')).lower() in {'active','current','available','published','for sale'} for r in rows),
               delta=EXAMPLE_METRICS['listings']['delta'] if listings['total'] is not None else None,
               series=EXAMPLE_METRICS['listings']['series'] if listings['total'] is not None else []))
    metrics.append(metric('properties','Property records','rpdata',properties,'Licensed records from the approved Australian property-data feed.','chart',
               delta=EXAMPLE_METRICS['properties']['delta'] if properties['total'] is not None else None,
               series=EXAMPLE_METRICS['properties']['series'] if properties['total'] is not None else []))

    metric_map={m['id']:m for m in metrics}
    if contacts['total'] is None:
        metric_map['contacts']=example_metric('contacts','Total contacts','agentbox','Illustrative CRM volume shown for presentation and design preview purposes.','users')
    if enquiries['total'] is None:
        metric_map['enquiries']=example_metric('enquiries','New enquiries','agentbox','Illustrative enquiry activity shown for presentation and design preview purposes.','message')
    if listings['total'] is None:
        metric_map['listings']=example_metric('listings','Active listings','agentbox','Illustrative listings volume shown for presentation and design preview purposes.','home')
    if properties['total'] is None:
        metric_map['properties']=example_metric('properties','Property records','rpdata','Illustrative property intelligence volume shown for presentation and design preview purposes.','chart')
    metrics=[metric_map[k] for k in ['contacts','enquiries','buyers','listings','properties']]

    if campaigns['total'] is None:
        campaigns=example_panel('rea','campaigns',EXAMPLE_BUYER_ROWS,'REA Ignite')
    if market['total'] is None:
        market=example_panel('proping','market_alerts',EXAMPLE_MARKET_ROWS,'Proping')

    calendar['rows']=[r for r in calendar['rows'] if r.get('status')!='Cancelled']
    calendar['rows'].sort(key=lambda r:r.get('start') or '')

    def upcoming(row):
        start=row.get('end') or row.get('start')
        if not start:
            return False
        try:
            dt=datetime.fromisoformat(start.replace('Z','+00:00'))
            if dt.tzinfo is None:
                if row.get('timezone','UTC') not in ('UTC','Etc/UTC'):
                    return True
                dt=dt.replace(tzinfo=timezone.utc)
            return dt>=datetime.now(timezone.utc)
        except (ValueError,TypeError):
            return False

    calendar['rows']=[r for r in calendar['rows'] if upcoming(r)]
    if calendar['total'] is not None:
        calendar['total']=len(calendar['rows'])

    for panel in (campaigns,market,calendar):
        panel['rows']=panel['rows'][:50]

    return {
        'metrics':metrics,
        'buyer_activity':campaigns,
        'market_activity':market,
        'calendar':calendar,
        'mode':'workspace',
        'generated_at':time.time(),
        'workspace_id':user['tenant_id'],
        'notice':'RE Unite shows live Google Calendar data and tasteful placeholder visual data for the remaining modules until those connectors are available.'
    }
