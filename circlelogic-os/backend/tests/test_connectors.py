import json
import time
from urllib.parse import parse_qs
import httpx
import pytest
from app.connectors import Engine,ConnectorError,oauth_spec,auth_url


def engine(handler):
    return Engine(transport=httpx.MockTransport(handler))

def response(payload,status=200):return httpx.Response(status,json=payload)

def test_rex_mock_login_and_paginated_normalisation():
    calls=[]
    def handler(req):
        body=json.loads(req.content);calls.append(req)
        if 'Authentication' in req.url.path:
            assert body['account_id']==123
            return response({'result':'rex-token'})
        assert req.headers['authorization']=='Bearer rex-token'
        if body['offset']>0:return response({'result':{'rows':[]}})
        if 'Contacts' in req.url.path:return response({'result':{'rows':[{'id':'1','first_name':'Alex','last_name':'Smith','email_address':'alex@example.invalid'}]}})
        return response({'result':{'rows':[{'id':'2','address_display':'24 Sample Street','system_listing_state':'current'}]}})
    e=engine(handler);d=e.sync('rex',{'email':'a','password':'b','account_id':'123'})
    assert d['contacts'][0]['title']=='Alex Smith' and d['listings'][0]['title']=='24 Sample Street'
    assert len(calls)==5;e.close()

def test_vaultre_mock_headers_and_pagination():
    def handler(req):
        assert req.headers['X-Api-Key']=='key' and req.headers['authorization']=='Bearer token'
        if req.url.params['page']=='2':return response({'items':[]})
        return response({'items':[{'id':3,'displayName':'Vault Contact','address':{'streetNumber':'6','street':'Example St','suburb':{'name':'Sydney'}}}]})
    e=engine(handler);d=e.sync('vaultre',{'api_key':'key','access_token':'token'})
    assert len(d['contacts'])==1 and 'Sydney' in d['listings'][0]['title'];e.close()

def test_domain_mock_auth_and_agency_check():
    def handler(req):
        if req.url.host=='auth.domain.com.au':
            assert req.headers['authorization'].startswith('Basic ')
            assert b'api_listings_read' in req.content
            return response({'access_token':'domain-token'})
        assert req.url.path=='/v1/agencies/123/listings'
        if req.url.params['pageNumber']=='2':return response([])
        return response([{'id':23,'status':'live','advertiserIdentifiers':{'advertiserId':123},'addressParts':{'displayAddress':'8 Demo Street'}}])
    e=engine(handler);d=e.sync('domain',{'client_id':'c','client_secret':'s','agency_id':'123'})
    assert d['portal_listings'][0]['external_id']=='23';e.close()

def test_rea_mock_hal_pages():
    def handler(req):
        if req.url.path=='/oauth/token':return response({'access_token':'rea-token'})
        if req.url.params.get('page')=='2':return response({'_embedded':{'items':[]},'_links':{}})
        return response({'_embedded':{'items':[{'id':'r1','listing':{'id':'l1'},'portalMetrics':{'views':22}}]},'_links':{'next':{'href':'/campaign/v1/listing-performance?agency_id=A1&page=2'}}})
    e=engine(handler);d=e.sync('rea',{'client_id':'c','client_secret':'s','agency_id':'A1'})
    assert d['campaigns'][0]['metrics']=={'views':22};e.close()

def test_microsoft_mock_calendar_only_and_pagination():
    calls=[]
    def handler(req):
        calls.append(req)
        assert 'calendarView' in req.url.path
        assert 'body' not in req.url.params.get('$select','')
        return response({'value':[{'id':'event1','subject':'Inspection','start':{'dateTime':'2026-10-01T11:00:00','timeZone':'UTC'}}]})
    e=engine(handler);d=e.sync('microsoft',{'access_token':'t','expires_at':time.time()+3600})
    assert set(d)=={'calendar'} and len(d['calendar'])==1 and d['calendar'][0]['title']=='Inspection'
    assert len(calls)==1;e.close()

def test_xero_mock_tenant_verification_and_invoices():
    def handler(req):
        if req.url.path=='/connections':return response([{'tenantId':'org-1'}])
        assert req.headers['Xero-tenant-id']=='org-1'
        if req.url.params['page']=='2':return response({'Invoices':[]})
        return response({'Invoices':[{'InvoiceID':'i1','InvoiceNumber':'INV-1','Type':'ACCREC','Status':'AUTHORISED','Total':100,'AmountDue':40,'CurrencyCode':'AUD','Contact':{'Name':'Client'}}]})
    e=engine(handler);d=e.sync('xero',{'access_token':'t','expires_at':time.time()+3600,'tenant_id':'org-1'})
    assert d['invoices'][0]['due']==40;e.close()

def test_docusign_mock_discovered_base_and_relative_pagination():
    def handler(req):
        if req.url.path=='/oauth/userinfo':return response({'accounts':[{'account_id':'a1','base_uri':'https://demo.docusign.net'}]})
        assert req.url.path=='/restapi/v2.1/accounts/a1/envelopes'
        if req.url.params.get('start_position')=='1':return response({'resultSetSize':'0'})
        return response({'envelopes':[{'envelopeId':'e1','emailSubject':'Agency agreement','status':'sent'}], 'nextUri':'/v2.1/accounts/a1/envelopes?start_position=1'})
    e=engine(handler);d=e.sync('docusign',{'access_token':'t','expires_at':time.time()+3600,'account_id':'a1','environment':'demo'})
    assert d['documents'][0]['status']=='sent';e.close()

def test_rotated_refresh_saved_before_subsequent_data_failure():
    persisted=[]
    def handler(req):
        if req.url.host=='identity.xero.com':return response({'access_token':'new-access','refresh_token':'new-refresh','expires_in':1800})
        assert persisted and persisted[0]['refresh_token']=='new-refresh'
        return response({'error':'PRIVATE PROVIDER MESSAGE'},403)
    e=engine(handler)
    with pytest.raises(ConnectorError):e.sync('xero',{'access_token':'old','refresh_token':'old-refresh','expires_at':0,'client_id':'c','client_secret':'s','tenant_id':'o'},lambda c:persisted.append(dict(c)))
    assert persisted[0]['access_token']=='new-access';e.close()

@pytest.mark.parametrize('url',['http://graph.microsoft.com/v1.0/me/calendar/calendarView','https://evil.example/v1.0/me/calendar/calendarView','https://graph.microsoft.com/v1.0/users/other/calendarView'])
def test_pagination_ssrf_and_cross_resource_guard(url):
    calls=[]
    def handler(req):
        calls.append(req);return response({'value':[],'@odata.nextLink':url})
    e=engine(handler)
    with pytest.raises(ConnectorError):e.paged_links('https://graph.microsoft.com/v1.0/me/calendar/calendarView',{'Authorization':'Bearer private'},'value')
    assert len(calls)==1;e.close()

def test_wrong_xero_organisation_stops_before_fetching_data():
    calls=[]
    def handler(req):calls.append(req);return response([{'tenantId':'other-org'}])
    e=engine(handler)
    with pytest.raises(ConnectorError):e.sync_xero({'access_token':'t','tenant_id':'org-1'})
    assert len(calls)==1;e.close()

def test_wrong_domain_agency_rejected():
    def handler(req):return response({'access_token':'t'}) if 'auth.domain' in req.url.host else response([{'id':1,'advertiserIdentifiers':{'advertiserId':999}}])
    e=engine(handler)
    with pytest.raises(ConnectorError):e.sync_domain({'client_id':'c','client_secret':'s','agency_id':'123'})
    e.close()

def test_untrusted_docusign_base_rejected():
    e=engine(lambda req:response({'accounts':[{'account_id':'a1','base_uri':'https://evil.example'}]}))
    with pytest.raises(ConnectorError):e.sync_docusign({'access_token':'t','account_id':'a1','environment':'demo'})
    e.close()

def test_provider_error_does_not_expose_response_secret():
    e=engine(lambda req:response({'secret':'LEAKED-CLIENT-SECRET'},403))
    with pytest.raises(ConnectorError) as err:e.request('GET','https://graph.microsoft.com/v1.0/me')
    assert 'LEAKED' not in str(err.value);e.close()

def test_rate_limit_retry_and_limit(monkeypatch):
    monkeypatch.setattr('app.connectors.time.sleep',lambda _:None);calls=[]
    def handler(req):calls.append(req);return response({},429)
    e=engine(handler)
    with pytest.raises(ConnectorError):e.request('GET','https://graph.microsoft.com/v1.0/me')
    assert len(calls)==3;e.close()

def test_repeated_page_rejected_without_silent_truncation():
    e=engine(lambda req:response({'value':[{'id':1}],'@odata.nextLink':'https://graph.microsoft.com/v1.0/me/messages'}))
    with pytest.raises(ConnectorError):e.paged_links('https://graph.microsoft.com/v1.0/me/messages',{},'value')
    e.close()
