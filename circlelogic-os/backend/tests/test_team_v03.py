"""CircleLogic OS v03 team lifecycle, identity, migration and assignment checks."""
import json
import time
import pytest
from fastapi.testclient import TestClient
from app.db import Store
from app.security import digest, otp
from conftest import ORIGIN, PASSWORD, request, register, add_member


def invite(owner, email='new@agency.example', name='New Person', role='agent'):
    r=request(owner,'POST','/api/team/invite',{'name':name,'email':email,'role':role})
    assert r.status_code==200,r.text
    data=r.json();data['token']=data['url'].split('token=')[1]
    return data


def test_named_invitation_is_visible_but_token_is_not(app,owner):
    invitation=invite(owner)
    pending=owner.get('/api/team').json()['invitations']
    assert pending[0]['id']==invitation['id'] and pending[0]['name']=='New Person'
    assert 'token_hash' not in pending[0] and invitation['token'] not in json.dumps(pending)
    data=TestClient(app,base_url=ORIGIN).get('/api/auth/invitation?token='+invitation['token']).json()
    assert data['name']=='New Person' and data['role']=='agent'
    stored=app.state.store.one('SELECT * FROM invitations WHERE id=?',(invitation['id'],))
    assert stored['token_hash']==digest(invitation['token'])
    assert invitation['token'] not in owner.get('/api/audit').text


def test_duplicate_email_cannot_create_duplicate_invitation(owner):
    invite(owner,email='Same@agency.example')
    r=request(owner,'POST','/api/team/invite',{'name':'Another Name','email':' SAME@AGENCY.EXAMPLE ','role':'agent'})
    assert r.status_code==409
    assert len(owner.get('/api/team').json()['invitations'])==1


def test_reissue_rotates_email_bound_token_and_role(app,owner):
    original=invite(owner)
    r=request(owner,'POST',f"/api/team/invitations/{original['id']}/reissue",{'name':'Updated Person','role':'finance'})
    assert r.status_code==200,r.text
    replacement=r.json()['url'].split('token=')[1]
    assert replacement!=original['token']
    assert owner.get('/api/auth/invitation?token='+original['token']).status_code==404
    assert owner.get('/api/auth/invitation?token='+replacement).json()['name']=='Updated Person'
    joined=register(app,'new@agency.example',invite=replacement)
    assert joined.user['role']=='finance'
    assert not owner.get('/api/team').json()['invitations']
    assert request(owner,'POST',f"/api/team/invitations/{original['id']}/reissue").status_code==404


def test_revoke_invalidates_invite_and_cannot_be_replayed(owner):
    invitation=invite(owner)
    assert request(owner,'DELETE',f"/api/team/invitations/{invitation['id']}").status_code==200
    assert owner.get('/api/auth/invitation?token='+invitation['token']).status_code==404
    assert request(owner,'DELETE',f"/api/team/invitations/{invitation['id']}").status_code==404


def test_expired_invitation_visible_and_can_be_reissued(app,owner):
    invitation=invite(owner)
    app.state.store.execute('UPDATE invitations SET expires_at=? WHERE id=?',(time.time()-1,invitation['id']))
    assert owner.get('/api/auth/invitation?token='+invitation['token']).status_code==404
    assert len(owner.get('/api/team').json()['invitations'])==1
    assert request(owner,'POST',f"/api/team/invitations/{invitation['id']}/reissue").status_code==200


@pytest.mark.parametrize('method,suffix',[('DELETE',''),('POST','/reissue')])
def test_invitation_mutations_are_tenant_scoped(app,owner,method,suffix):
    invitation=invite(owner)
    other=register(app,'other@other.example','Other workspace')
    assert request(other,method,f"/api/team/invitations/{invitation['id']}"+suffix).status_code==404
    assert owner.get('/api/auth/invitation?token='+invitation['token']).status_code==200


def test_admin_cannot_mutate_owner_invitation_or_grant_admin(app,owner):
    admin=add_member(app,owner,'admin','admin@agency.example')
    invitation=invite(owner,role='owner')
    assert request(admin,'POST',f"/api/team/invitations/{invitation['id']}/reissue",{'role':'agent'}).status_code==403
    assert request(admin,'DELETE',f"/api/team/invitations/{invitation['id']}").status_code==403
    assert request(admin,'POST','/api/team/invite',{'email':'power@agency.example','role':'admin'}).status_code==403
    assert request(admin,'POST','/api/team/invite',{'email':invitation['email'],'role':'agent'}).status_code==403
    member_invite=invite(admin,email='allowed@agency.example')
    assert request(admin,'DELETE',f"/api/team/invitations/{member_invite['id']}").status_code==200


def test_joining_member_requires_own_mfa_before_data_or_assignment(app,owner):
    invitation=invite(owner)
    c=TestClient(app,base_url=ORIGIN)
    r=request(c,'POST','/api/auth/register',{'name':'New Person','email':invitation['email'],'password':PASSWORD,'invite_token':invitation['token']})
    assert r.status_code==201
    person=next(m for m in owner.get('/api/team').json()['members'] if m['email']==invitation['email'])
    assert not person['mfa_enabled'] and not person['can_assign']
    assert c.get('/api/dashboard').status_code==401
    assert request(owner,'POST','/api/tasks',{'title':'Cannot yet assign','assigned_to':person['id']}).status_code==400
    secret=c.get('/api/auth/enrolment').json()['secret']
    assert request(c,'POST','/api/auth/mfa',{'code':otp(secret,int(time.time()//30))}).status_code==200
    assert c.get('/api/dashboard').status_code==200
    assert request(owner,'POST','/api/tasks',{'title':'Assigned work','assigned_to':person['id']}).status_code==200
    person=next(m for m in owner.get('/api/team').json()['members'] if m['email']==invitation['email'])
    assert person['can_assign'] and person['open_tasks']==1


def test_self_display_name_changes_without_changing_login_or_revoking_session(app,owner):
    task=request(owner,'POST','/api/tasks',{'title':'Owned task'}).json()['id']
    before=app.state.store.one('SELECT * FROM users WHERE id=?',(owner.user['id'],))
    r=request(owner,'PATCH','/api/team/'+owner.user['id'],{'name':'Updated Owner','role':'owner','active':True})
    assert r.status_code==200 and not r.json()['sessions_revoked']
    assert owner.get('/api/auth/session').json()['user']['name']=='Updated Owner'
    after=app.state.store.one('SELECT * FROM users WHERE id=?',(owner.user['id'],))
    for key in ['email','password_hash','totp_secret','tenant_id','role']:
        assert before[key]==after[key]
    assert owner.get('/api/record/tasks/'+task).json()['record']['owner']=='Updated Owner'
    assert request(owner,'PATCH','/api/team/'+owner.user['id'],{'role':'viewer'}).status_code==400
    assert request(owner,'PATCH','/api/team/'+owner.user['id'],{'role':'owner','active':False}).status_code==400


def test_member_rename_preserves_identity_and_updates_manual_task(app,owner):
    member=add_member(app,owner)
    task=request(owner,'POST','/api/tasks',{'title':'Member work','assigned_to':member.user['id']}).json()['id']
    r=request(owner,'PATCH','/api/team/'+member.user['id'],{'name':'Renamed Agent','role':'agent'})
    assert r.status_code==200 and not r.json()['sessions_revoked']
    assert member.get('/api/auth/session').json()['user']['name']=='Renamed Agent'
    assert owner.get('/api/record/tasks/'+task).json()['record']['owner']=='Renamed Agent'
    assert request(owner,'PATCH','/api/team/'+member.user['id'],{'name':'Different Person','email':'not-same@agency.example','role':'agent'}).status_code==422


def test_admin_self_name_edit_allowed_but_self_elevation_denied(app,owner):
    admin=add_member(app,owner,'admin','admin@agency.example')
    assert request(admin,'PATCH','/api/team/'+admin.user['id'],{'name':'Admin Name','role':'admin'}).status_code==200
    assert request(admin,'PATCH','/api/team/'+admin.user['id'],{'name':'Admin Name','role':'owner'}).status_code==400


@pytest.mark.parametrize('name',['  ',' X '])
def test_names_are_validated_after_trimming(owner,name):
    assert request(owner,'POST','/api/team/invite',{'name':name,'email':'short@agency.example','role':'agent'}).status_code==400
    assert request(owner,'PATCH','/api/team/'+owner.user['id'],{'name':name,'role':'owner'}).status_code==400


def test_task_reassignment_updates_owner_and_requires_privilege(app,owner):
    member=add_member(app,owner)
    viewer=add_member(app,owner,'viewer','viewer@agency.example')
    task=request(owner,'POST','/api/tasks',{'title':'Reassignment test'}).json()['id']
    assert request(owner,'PATCH','/api/tasks/'+task,{'assigned_to':member.user['id']}).status_code==200
    assert owner.get('/api/record/tasks/'+task).json()['record']['owner']==member.user['name']
    assert request(member,'PATCH','/api/tasks/'+task,{'assigned_to':owner.user['id']}).status_code==403
    assert request(owner,'PATCH','/api/tasks/'+task,{'assigned_to':viewer.user['id']}).status_code==400
    assert request(owner,'POST','/api/tasks',{'title':'Viewer task','assigned_to':viewer.user['id']}).status_code==400
    assert request(owner,'PATCH','/api/tasks/'+task,{}).status_code==400
    assert request(member,'PATCH','/api/tasks/'+task,{'status':'Done'}).status_code==200
    person=next(m for m in owner.get('/api/team').json()['members'] if m['id']==member.user['id'])
    assert person['open_tasks']==0


def test_recent_mfa_and_csrf_required_for_all_team_writes(app,owner):
    invitation=invite(owner)
    assert request(owner,'DELETE',f"/api/team/invitations/{invitation['id']}",csrf=False).status_code==403
    app.state.store.execute('UPDATE sessions SET mfa_at=?',(time.time()-601,))
    assert request(owner,'POST',f"/api/team/invitations/{invitation['id']}/reissue").status_code==403
    assert request(owner,'PATCH','/api/team/'+owner.user['id'],{'name':'Owner name','role':'owner'}).status_code==403
    assert request(owner,'DELETE',f"/api/team/invitations/{invitation['id']}").status_code==403


def test_existing_database_migration_is_additive_idempotent(tmp_path):
    import sqlite3
    path=tmp_path/'legacy.sqlite'
    db=sqlite3.connect(path)
    db.executescript("""CREATE TABLE tenants(id TEXT PRIMARY KEY,name TEXT NOT NULL,settings TEXT NOT NULL DEFAULT '{}',created_at REAL NOT NULL);
    INSERT INTO tenants VALUES('tenant-old','Existing agency','{}',1);
    CREATE TABLE invitations(token_hash TEXT PRIMARY KEY,tenant_id TEXT NOT NULL,email TEXT NOT NULL,role TEXT NOT NULL,expires_at REAL NOT NULL,created_by TEXT NOT NULL);
    INSERT INTO invitations VALUES('existing-hash','tenant-old','old@agency.example','agent',9999999999,'existing-owner');""")
    db.close()
    store=Store(path)
    row=store.one('SELECT * FROM invitations')
    assert row['token_hash']=='existing-hash' and row['id'] and row['name']==''
    Store(path)
    assert store.one('SELECT * FROM invitations')['id']==row['id']
    assert store.one('SELECT name FROM tenants')['name']=='Existing agency'
