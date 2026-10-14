import json
import time
from .catalog import CATALOG, DEFAULT_SOURCES
from .connectors import ConnectorError, Engine
from .db import uid

FRESH_SECONDS=3600

def settings_for(store,tenant):
    row=store.one('SELECT settings FROM tenants WHERE id=?',(tenant,))
    current=json.loads(row['settings']) if row else {}
    return {'demo_enabled':False, 'sources':{**DEFAULT_SOURCES,**current.get('sources',{})}}

def conn_context(tenant,provider,owner):
    return f'connection:{tenant}:{provider}:{owner}'

def dataset(store,user,kind):
    tenant=user['tenant_id'];cfg=settings_for(store,tenant)
    provider=cfg['sources'].get(kind,'manual')
    owner=user['id'] if CATALOG.get(provider,{}).get('private') else ''
    if provider=='manual':
        records=store.all('SELECT id,payload FROM records WHERE tenant_id=? AND kind=? AND provider=? AND owner_id=? ORDER BY updated_at DESC',
                          (tenant,kind,provider,''))
        if records:
            return {'mode':'local','provider':'CircleLogic OS','synced_at':None,'rows':[dict(json.loads(r['payload']),id=r['id']) for r in records], 'note':'Saved in this agency workspace. Not sent to an external CRM.'}
        # A local data source remains local even after the last item is deleted.
        marker=store.one('SELECT id FROM audit WHERE tenant_id=? AND action=? LIMIT 1',(tenant,'task.created')) if kind=='tasks' else None
        if marker:
            return {'mode':'local','provider':'CircleLogic OS','synced_at':None,'rows':[],'note':'No tasks in this workspace.'}
    else:
        connection=store.one('SELECT * FROM connections WHERE tenant_id=? AND provider=? AND owner_id=?',(tenant,provider,owner))
        if connection:
            snapshot=store.one('SELECT * FROM snapshots WHERE connection_id=? AND kind=?',(connection['id'],kind))
            if snapshot:
                records=store.all('SELECT id,payload FROM records WHERE tenant_id=? AND connection_id=? AND kind=? AND owner_id=? ORDER BY external_id',
                                  (tenant,connection['id'],kind,owner))
                mode='live' if connection['status']=='connected' and snapshot['synced_at']>time.time()-FRESH_SECONDS else 'stale'
                if connection['status']=='disconnected':
                    mode='disconnected'
                return {'mode':mode,'provider':CATALOG[provider]['name'],'synced_at':snapshot['synced_at'],
                        'rows':[dict(json.loads(r['payload']),id=r['id']) for r in records],
                        'note':connection.get('error') or ('Last successful snapshot; not current.' if mode=='stale' else 'Imported snapshot, not a real-time feed.')}
    return {'mode':'unavailable','provider':CATALOG.get(provider,{}).get('name','CircleLogic OS'),'synced_at':None,'rows':[],
            'note':'No imported data yet. Connect and sync an approved source.'}

def perform_sync(store,vault,connection,user_id,engine_factory=Engine):
    now=time.time(); lease=uid(); cid=connection['id'];tenant=connection['tenant_id'];revision=connection['revision']
    with store.transaction() as db:
        row=db.execute('SELECT * FROM connections WHERE id=? AND tenant_id=?',(cid,tenant)).fetchone()
        if not row or row['revision']!=revision or not row['credentials']:
            raise ConnectorError('The connection was changed or disconnected. Start again.')
        if row['lease_until']>now:
            raise ConnectorError('A sync is already running for this connection.')
        db.execute('UPDATE connections SET lease_until=?,lease_token=? WHERE id=? AND tenant_id=?',(now+300,lease,cid,tenant))
    ctx=conn_context(tenant,connection['provider'],connection['owner_id'])
    engine=engine_factory()
    def save(c):
        changed=store.execute('UPDATE connections SET credentials=? WHERE id=? AND tenant_id=? AND revision=? AND lease_token=?',
                             (vault.seal(ctx,c),cid,tenant,revision,lease))
        if not changed:
            raise ConnectorError('Connection changed while syncing. Results were not saved.')
    try:
        creds=vault.open(ctx,connection['credentials'])
        result=engine.sync(connection['provider'],creds,save)
        expected=set(CATALOG[connection['provider']]['kinds'])
        if set(result)!=expected:
            raise ConnectorError('Connector returned an incomplete module set. Existing data was preserved.')
        prepared=[]
        for kind,records in result.items():
            ids=set()
            if not isinstance(records,list):
                raise ConnectorError('Invalid connector result.')
            for r in records:
                external=str(r.get('external_id',''))
                if not external or external in ids:
                    raise ConnectorError('Missing or duplicate provider IDs. Cached data was preserved.')
                ids.add(external)
                prepared.append((uid(),tenant,cid,connection['provider'],connection['owner_id'],kind,external,json.dumps(r,allow_nan=False),time.time()))
        with store.transaction() as db:
            current=db.execute('SELECT revision,lease_token,credentials FROM connections WHERE id=? AND tenant_id=?',(cid,tenant)).fetchone()
            if not current or current['revision']!=revision or current['lease_token']!=lease or not current['credentials']:
                raise ConnectorError('Connection changed during sync. Results were discarded.')
            # All pages and every module succeed before the old snapshot is replaced.
            db.execute('DELETE FROM records WHERE tenant_id=? AND connection_id=?',(tenant,cid))
            db.executemany('INSERT INTO records VALUES(?,?,?,?,?,?,?,?,?)',prepared)
            synced=time.time()
            for kind in result:
                db.execute('INSERT OR REPLACE INTO snapshots VALUES(?,?,?)',(cid,kind,synced))
            db.execute('UPDATE connections SET status=?,last_success=?,error=NULL,lease_until=0,lease_token=NULL WHERE id=? AND tenant_id=?',
                       ('connected',synced,cid,tenant))
            db.execute('INSERT INTO audit VALUES(?,?,?,?,?,?)',(uid(),tenant,user_id,'sync.succeeded',connection['provider']+': '+str(len(prepared))+' records',synced))
        return {'counts':{k:len(v) for k,v in result.items()},'synced_at':synced}
    except Exception as exc:
        message=str(exc) if isinstance(exc,ConnectorError) else 'Sync failed an internal validation. Cached data was preserved; ask the operator to review the adapter.'
        store.execute('UPDATE connections SET status=?,error=?,lease_until=0,lease_token=NULL WHERE id=? AND tenant_id=? AND revision=? AND lease_token=?',
                      ('error',message[:500],cid,tenant,revision,lease))
        store.audit(tenant,user_id,'sync.failed',connection['provider'])
        raise ConnectorError(message) from None
    finally:
        engine.close()
