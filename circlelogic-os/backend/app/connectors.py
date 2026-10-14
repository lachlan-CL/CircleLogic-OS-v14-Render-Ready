"""Read-only provider adapters. No user-supplied upstream URLs are accepted.

Live credentials have not been available during development. Test these adapters
against each agency's approved sandbox before a client release.
"""
import math
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import re
import time
from urllib.parse import urlencode, urlparse, urljoin
import httpx
from .catalog import CATALOG

class ConnectorError(Exception):
    """A deliberately sanitised error safe to display to the tenant."""
    def __init__(self, message, *, code="provider_error"):
        super().__init__(message)
        self.code = code

def ident(value):
    value = str(value)
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,150}', value):
        raise ConnectorError('The configured account or agency identifier is invalid.')
    return value

def iso(dt):
    return dt.astimezone(timezone.utc).isoformat().replace('+00:00','Z')

def text(value, default=''):
    return str(value)[:1200] if value is not None and not isinstance(value,(dict,list)) else default

def nested(obj, *keys, default=None):
    for key in keys:
        if not isinstance(obj,dict):
            return default
        obj=obj.get(key)
    return obj if obj is not None else default

def address(row):
    for value in [nested(row,'addressParts','displayAddress'), nested(row,'address','displayAddress'),
                  row.get('address_display'), row.get('address_display_address'), row.get('fullAddress')]:
        if isinstance(value,str) and value:
            return value
    a = row.get('address') or row.get('property') or row
    if not isinstance(a,dict):
        return text(a, 'Address unavailable')
    parts=[a.get('unitNumber') or a.get('adr_unit_number'),a.get('streetNumber') or a.get('adr_street_number'),
           a.get('street') or a.get('streetName') or a.get('adr_street_name'),a.get('suburb') or a.get('adr_suburb_or_town')]
    parts=[nested(x,'name',default='') if isinstance(x,dict) else text(x) for x in parts]
    return ' '.join(x for x in parts if x) or 'Address unavailable'

def collection(obj, key):
    rows = obj.get(key) if isinstance(obj,dict) else None
    if not isinstance(rows,list):
        raise ConnectorError('The provider response did not match the expected collection schema. No cached data was replaced.')
    if any(not isinstance(r,dict) for r in rows):
        raise ConnectorError('The provider returned an invalid record. No cached data was replaced.')
    return rows

def normal(external_id,title,status='',**kwargs):
    if external_id is None or str(external_id)=='':
        raise ConnectorError('A provider record is missing its stable identifier. No cached data was replaced.')
    return {'external_id':str(external_id), 'title':text(title,'Untitled record'), 'status':text(status,'Unknown'), **kwargs}

def oauth_spec(provider, c):
    if provider=='microsoft':
        tenant=ident(c['directory_id'])
        host=f'https://login.microsoftonline.com/{tenant}/oauth2/v2.0'
        return {'auth':host+'/authorize','token':host+'/token','scope':'offline_access Calendars.ReadBasic','pkce':True,'basic':False}
    if provider=='google':
        return {'auth':'https://accounts.google.com/o/oauth2/v2/auth','token':'https://oauth2.googleapis.com/token',
                'scope':'https://www.googleapis.com/auth/calendar.events.readonly','pkce':False,'basic':False}
    if provider=='xero':
        return {'auth':'https://login.xero.com/identity/connect/authorize','token':'https://identity.xero.com/connect/token',
                'scope':'offline_access accounting.transactions.read','pkce':False,'basic':True}
    if provider=='docusign':
        host='https://account.docusign.com' if c.get('environment')=='production' else 'https://account-d.docusign.com'
        return {'auth':host+'/oauth/auth','token':host+'/oauth/token','userinfo':host+'/oauth/userinfo',
                'scope':'signature extended','pkce':True,'basic':True}
    raise ConnectorError('This provider does not use an authorisation-code connection in this build.')

def auth_url(provider,c,callback,state,verifier):
    spec=oauth_spec(provider,c)
    params={'client_id':c['client_id'],'response_type':'code','redirect_uri':callback,'scope':spec['scope'],'state':state}
    if spec['pkce']:
        params.update(code_challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('='),code_challenge_method='S256')
    if provider == 'microsoft':
        params['prompt'] = 'select_account'  # Make the chosen test mailbox explicit.
    if provider == 'google':
        params.update(access_type='offline',include_granted_scopes='true',prompt='consent select_account')
    return spec['auth']+'?'+urlencode(params)

class Engine:
    def __init__(self, transport=None, max_pages=100):
        self.transport=transport
        self.max_pages=max_pages
        self.deadline=time.monotonic()+180
        self.client=httpx.Client(timeout=httpx.Timeout(15.0,connect=8.0),follow_redirects=False,transport=transport)
    def close(self):
        self.client.close()
    def request(self, method, url, *, allowed_host=None, **kwargs):
        parsed=urlparse(url)
        if parsed.scheme!='https' or parsed.username or parsed.password or parsed.port not in (None,443):
            raise ConnectorError('An unsafe upstream address was rejected.')
        if allowed_host and parsed.hostname!=allowed_host:
            raise ConnectorError('The provider returned a pagination link outside its allowed host.')
        headers={'Accept':'application/json',**kwargs.pop('headers',{})}
        for attempt in range(3):
            if time.monotonic()>self.deadline:
                raise ConnectorError('Sync exceeded the pilot time budget. Cached data was preserved.')
            try:
                with self.client.stream(method,url,headers=headers,**kwargs) as r:
                    if r.status_code in (429,500,502,503,504) and attempt<2:
                        retry=r.headers.get('retry-after','1')
                        delay=float(retry) if retry.replace('.','',1).isdigit() else 2**attempt
                        time.sleep(min(delay,8))
                        continue
                    if parsed.hostname == 'login.microsoftonline.com' and r.status_code in (400,401,403):
                        # Whitelist numeric AADSTS codes; discard message, token and ID values.
                        error_data = bytearray()
                        for part in r.iter_bytes():
                            error_data.extend(part)
                            if len(error_data) > 32768:
                                break
                        import json
                        try:
                            payload = json.loads(error_data) if len(error_data) <= 32768 else {}
                        except (ValueError,TypeError):
                            payload = {}
                        codes = payload.get('error_codes', []) if isinstance(payload,dict) else []
                        messages = {
                            7000215: 'Microsoft rejected the client secret. Use the secret VALUE, not its Secret ID, from the same app registration.',
                            7000222: 'The Microsoft client secret has expired. Create a new secret, replace the saved credentials and authorise again.',
                            700016: 'Microsoft could not find this app in the selected directory. Check the Application client ID and Directory tenant ID.',
                            50011: 'Microsoft rejected the redirect URI. Register the exact Web callback shown in CircleLogic OS.',
                            65001: 'Microsoft consent is required. Ask your administrator to approve the requested delegated calendar permissions.',
                            70011: 'Microsoft rejected the requested permission scope. Review the delegated calendar configuration.',
                        }
                        found = next((x for x in codes if type(x) is int and x in messages),None) if isinstance(codes,list) else None
                        message = messages[found] + ' (AADSTS'+str(found)+')' if found else 'Microsoft refused authorisation. Check the app, secret, tenant and consent. Authorise again; no provider details were logged.'
                        raise ConnectorError(message,code='oauth_refused')
                    if parsed.hostname == 'oauth2.googleapis.com' and r.status_code in (400,401,403):
                        # Google token errors can contain user/account details. Only map
                        # stable OAuth error codes; never reflect descriptions or payloads.
                        error_data = bytearray()
                        for part in r.iter_bytes():
                            error_data.extend(part)
                            if len(error_data) > 32768:
                                break
                        import json
                        try:
                            payload = json.loads(error_data) if len(error_data) <= 32768 else {}
                        except (ValueError,TypeError):
                            payload = {}
                        code = payload.get('error') if isinstance(payload,dict) else None
                        messages = {
                            'invalid_client':'Google rejected the OAuth client ID or client secret. Check that both come from the same Web application credential.',
                            'invalid_grant':'Google rejected or expired the authorisation code or refresh token. Authorise Google Calendar again.',
                            'redirect_uri_mismatch':'Google rejected the redirect URI. Add the exact callback shown in CircleLogic OS to the Web application credential.',
                            'unauthorized_client':'This Google OAuth client is not permitted to use this authorisation flow. Check the Web application credential and consent configuration.',
                            'access_denied':'Google Calendar access was denied. Authorise again with the intended Google account.',
                        }
                        raise ConnectorError(messages.get(code,'Google refused authorisation. Check the OAuth client, redirect URI, consent screen and test-user access, then authorise again.'),code='oauth_refused')
                    if r.status_code in (401,403):
                        raise ConnectorError('Provider access was refused. Check authorisation, account, approval and scopes.',code='provider_unauthorised' if r.status_code==401 else 'provider_forbidden')
                    if r.status_code==429:
                        raise ConnectorError('Provider rate limit reached. Retry later; cached data was preserved.')
                    if not 200<=r.status_code<300:
                        raise ConnectorError(f'Provider returned HTTP {r.status_code}. Check the connection setup; cached data was preserved.')
                    data=bytearray()
                    for chunk in r.iter_bytes():
                        data.extend(chunk)
                        if len(data)>8*1024*1024:
                            raise ConnectorError('A response exceeded the 8 MB pilot safety limit.')
                    import json
                    return json.loads(data)
            except httpx.HTTPError:
                if attempt<2:
                    time.sleep(2**attempt)
                    continue
                raise ConnectorError('Provider could not be reached. Cached data was preserved.') from None
            except ValueError:
                raise ConnectorError('Provider returned invalid JSON. Cached data was preserved.') from None
        raise ConnectorError('Provider request failed.')

    def exchange(self,provider,c, *, code=None, callback=None, verifier=None, refresh=False):
        spec=oauth_spec(provider,c)
        form={'grant_type':'refresh_token' if refresh else 'authorization_code'}
        if refresh:
            if not c.get('refresh_token'):
                raise ConnectorError('This authorisation has expired. Reconnect the provider.')
            form['refresh_token']=c['refresh_token']
        else:
            form.update(code=code,redirect_uri=callback)
            if spec['pkce']:
                form['code_verifier']=verifier
        kwargs={}
        if spec['basic']:
            kwargs['auth']=(c['client_id'],c['client_secret'])
        else:
            form.update(client_id=c['client_id'],client_secret=c['client_secret'])
            if provider == 'microsoft':
                form['scope']=spec['scope']
        result=self.request('POST',spec['token'],data=form,**kwargs)
        if not isinstance(result,dict) or not result.get('access_token'):
            raise ConnectorError('Provider did not return an access token.')
        try:
            lifetime = float(result.get('expires_in',1800))
        except (ValueError,TypeError):
            raise ConnectorError('Provider returned an invalid token lifetime.') from None
        if not math.isfinite(lifetime) or lifetime <= 0 or not isinstance(result['access_token'],str):
            raise ConnectorError('Provider returned invalid token metadata.')
        c.update(access_token=result['access_token'],expires_at=time.time()+lifetime)
        if result.get('refresh_token'):
            if not isinstance(result['refresh_token'],str):
                raise ConnectorError('Provider returned invalid refresh metadata.')
            c['refresh_token']=result['refresh_token']
        return c

    def client_credentials(self,provider,c):
        if provider=='domain':
            url='https://auth.domain.com.au/v1/connect/token'
            form={'grant_type':'client_credentials','scope':'api_listings_read'}
        else:
            url='https://api.realestate.com.au/oauth/token'
            form={'grant_type':'client_credentials'}
        res=self.request('POST',url,data=form,auth=(c['client_id'],c['client_secret']))
        if not isinstance(res,dict) or not res.get('access_token'):
            raise ConnectorError('Provider did not return an access token.')
        return {'Authorization':'Bearer '+res['access_token']}

    def paged_links(self,url,headers,key,params=None,base_path=None):
        host=urlparse(url).hostname
        path_prefix=base_path or urlparse(url).path
        rows=[]; visited=set()
        for _ in range(self.max_pages):
            if url in visited:
                raise ConnectorError('Provider repeated a pagination link. Cached data was preserved.')
            visited.add(url)
            if not urlparse(url).path.startswith(path_prefix):
                raise ConnectorError('An unexpected provider pagination path was rejected.')
            data=self.request('GET',url,headers=headers,params=params,allowed_host=host)
            params=None
            # DocuSign omits the envelopes array for an explicitly empty result.
            if key=='envelopes' and isinstance(data,dict) and 'envelopes' not in data and str(data.get('resultSetSize'))=='0':
                data={**data,'envelopes':[]}
            rows.extend(collection(data,key))
            nxt=data.get('@odata.nextLink') or data.get('nextUri')
            if not nxt:
                return rows
            # DocuSign nextUri is relative to its /restapi root, unlike Graph.
            if key=='envelopes' and isinstance(nxt,str) and nxt.startswith('/v2.1/'):
                nxt='/restapi'+nxt
            url=urljoin(url,nxt)
        raise ConnectorError('More pages than the pilot limit. Increase the reviewed sync budget before retrying.')

    def sync(self,provider,c,save_credentials=lambda c:None):
        if not CATALOG[provider]['implemented']:
            raise ConnectorError('This connector is not implemented. Obtain the partner contract and complete its adapter first.')
        if CATALOG[provider]['auth']=='oauth':
            if not c.get('access_token'):
                raise ConnectorError('Authorise this provider before syncing.')
            if c.get('expires_at',0)<time.time()+60:
                self.exchange(provider,c,refresh=True)
                save_credentials(c)  # Persist rotated refresh tokens BEFORE data fetching.
        try:
            return getattr(self,'sync_'+provider)(c)
        except ConnectorError as exc:
            # The provider may reject a still-locally-valid access token. Refresh
            # at most once, persist rotation, then retry the complete read.
            if provider not in ('microsoft','google') or exc.code!='provider_unauthorised' or not c.get('refresh_token'):
                raise
            self.exchange(provider,c,refresh=True)
            save_credentials(c)
            return getattr(self,'sync_'+provider)(c)

    def sync_rex(self,c):
        account=ident(c['account_id'])
        if not account.isdigit():
            raise ConnectorError('Rex account ID must be numeric.')
        auth=self.request('POST','https://api.rexsoftware.com/v1/rex/Authentication/login',json={
            'email':c['email'],'password':c['password'],'account_id':int(account)})
        if not isinstance(auth,dict) or auth.get('error'):
            raise ConnectorError('Rex login failed.')
        value=auth.get('result')
        bearer=value if isinstance(value,str) else nested(value,'token')
        if not isinstance(bearer,str):
            raise ConnectorError('Rex returned an unexpected authentication schema.')
        headers={'Authorization':'Bearer '+bearer}
        output={}
        for kind,service in [('contacts','Contacts'),('listings','PublishedListings')]:
            rows=[]; ids=set(); offset=0
            for page in range(self.max_pages):
                res=self.request('POST',f'https://api.rexsoftware.com/v1/rex/{service}/search',headers=headers,
                                 json={'criteria':[],'limit':100,'offset':offset})
                if not isinstance(res,dict) or res.get('error'):
                    raise ConnectorError('Rex search failed; cached data was preserved.')
                batch=collection(res.get('result'),'rows')
                if not batch:
                    break
                for r in batch:
                    rid=str(r.get('id',''))
                    if not rid or rid in ids:
                        raise ConnectorError('Rex pagination returned missing or repeated IDs.')
                    ids.add(rid)
                rows.extend(batch); offset+=len(batch)
                total=nested(res,'result','total')
                if total is not None and offset>=int(total):
                    break
            else:
                raise ConnectorError('Rex sync reached the page limit. No records were replaced.')
            if kind=='contacts':
                output[kind]=[normal(r.get('id'),r.get('name') or r.get('system_search_key') or
                    ' '.join(filter(None,[text(r.get('first_name')),text(r.get('last_name'))])),
                    'Contact',email=text(r.get('email_address')),phone=text(r.get('phone_number')),owner='Rex',category='CRM contact') for r in rows]
            else:
                output[kind]=[normal(r.get('id'),address(r),r.get('system_listing_state'),
                    price=text(r.get('price_advertise_as')),suburb=text(nested(r,'property','adr_suburb_or_town')),
                    owner=text(nested(r,'listing_agent_1','name'),'Rex'),beds=nested(r,'property','attr_bedrooms'),baths=nested(r,'property','attr_bathrooms')) for r in rows]
        return output

    def sync_vaultre(self,c):
        headers={'Authorization':'Bearer '+c['access_token'],'X-Api-Key':c['api_key']}
        output={}
        for kind,path in [('contacts','contacts'),('listings','properties/residential/sale/available')]:
            rows=[]; ids=set()
            for page in range(1,self.max_pages+1):
                data=self.request('GET','https://ap-southeast-2.api.vaultre.com.au/api/v1.3/'+path,
                                  headers=headers,params={'page':page,'perPage':100})
                batch=collection(data,'items')
                if not batch:
                    break
                for r in batch:
                    rid=str(r.get('id',''))
                    if not rid or rid in ids:
                        raise ConnectorError('VaultRE pagination returned missing or repeated IDs. Verify the approved contract.')
                    ids.add(rid)
                rows.extend(batch)
                pages=data.get('totalPages') or nested(data,'pagination','totalPages')
                if pages is not None and page>=int(pages):
                    break
            else:
                raise ConnectorError('VaultRE sync reached the page limit; cached data was preserved.')
            if kind=='contacts':
                output[kind]=[normal(r.get('id'),r.get('displayName') or
                    ' '.join(filter(None,[text(r.get('firstName')),text(r.get('lastName'))])),
                    'Contact',email=text(r.get('email')),phone=text(r.get('phone')),owner='VaultRE',category='CRM contact') for r in rows]
            else:
                output[kind]=[normal(r.get('id'),address(r),'Available',price=text(r.get('displayPrice')),
                                     owner='VaultRE',beds=r.get('bed'),baths=r.get('bath')) for r in rows]
        return output

    def sync_domain(self,c):
        headers=self.client_credentials('domain',c)
        rows=[]; ids=set()
        for page in range(1,self.max_pages+1):
            batch=self.request('GET',f'https://api.domain.com.au/v1/agencies/{ident(c["agency_id"])}/listings',
                               headers=headers,params={'listingStatusFilter':'live','pageNumber':page,'pageSize':200})
            if not isinstance(batch,list):
                raise ConnectorError('Domain returned an unexpected listing schema.')
            if not batch:
                break
            for r in batch:
                if not isinstance(r,dict) or str(r.get('id')) in ids:
                    raise ConnectorError('Domain returned an invalid or repeated listing.')
                advertiser=nested(r,'advertiserIdentifiers','advertiserId')
                if advertiser is not None and str(advertiser)!=str(c['agency_id']):
                    raise ConnectorError('Domain returned a listing belonging to a different agency.')
                ids.add(str(r.get('id')))
            rows.extend(batch)
        else:
            raise ConnectorError('Domain sync reached the page limit; cached data was preserved.')
        return {'portal_listings':[normal(r.get('id'),address(r),r.get('status'),
                  price=nested(r,'priceDetails','displayPrice',default=''),owner='Domain',
                  suburb=nested(r,'addressParts','suburb',default=''),beds=r.get('bedrooms'),baths=r.get('bathrooms')) for r in rows]}

    @staticmethod
    def rea_totals(portal_metrics):
        """Select documented campaign totals, never sum daily + lifetime periods.

        Source: REA Campaign / Listing Performance Usage (checked 2026-09-25).
        Unknown/missing metrics stay null; listing events are not unique buyers.
        """
        totals={'page_views':None,'email_enquiries':None,'saves':None}
        names={'pageView':'page_views','emailEnquiry':'email_enquiries','listingSaved':'saves'}
        if not isinstance(portal_metrics,list):return totals
        for portal in portal_metrics:
            if not isinstance(portal,dict) or portal.get('portalName')!='realestate_au':continue
            for metric in portal.get('all') or []:
                if not isinstance(metric,dict) or metric.get('metricName')!='listingEvents':continue
                for period in metric.get('metricPeriods') or []:
                    if not isinstance(period,dict) or period.get('period')!='all':continue
                    for item in period.get('metricValues') or []:
                        if not isinstance(item,dict):continue
                        key=names.get(item.get('name'));value=item.get('value')
                        if key and type(value) in (int,float) and value>=0 and math.isfinite(value):
                            if totals[key] is not None and totals[key]!=value:
                                raise ConnectorError('REA returned ambiguous duplicate totals; the previous snapshot was preserved.')
                            totals[key]=value
        return totals

    def sync_rea(self,c):
        headers=self.client_credentials('rea',c)
        url='https://api.realestate.com.au/campaign/v1/listing-performance'
        params={'agency_id':ident(c['agency_id'])}; rows=[]; seen=set()
        for _ in range(self.max_pages):
            if url in seen:
                raise ConnectorError('REA repeated a pagination link.')
            seen.add(url)
            parsed=urlparse(url)
            if parsed.path!='/campaign/v1/listing-performance':
                raise ConnectorError('REA returned an unexpected pagination path.')
            data=self.request('GET',url,headers=headers,params=params,allowed_host='api.realestate.com.au')
            rows.extend(collection(data.get('_embedded',{}),'items'))
            nxt=nested(data,'_links','next','href')
            if not nxt:
                break
            url=urljoin(url,nxt); params=None
        else:
            raise ConnectorError('REA sync reached the page limit; cached data was preserved.')
        for row in rows:
            agency=nested(row,'listing','agencyId')
            if agency is not None and str(agency)!=str(c['agency_id']):
                raise ConnectorError('REA returned a report for a different agency. Nothing was imported.')
        return {'campaigns':[normal(r.get('id'),'REA listing '+text(nested(r,'listing','id'),text(r.get('id'))),
                    'Report available',period=r.get('reportingPeriod'),metrics=r.get('portalMetrics'),
                    totals=self.rea_totals(r.get('portalMetrics')),
                    owner='REA',updated=r.get('lastModifiedAt')) for r in rows]}

    def sync_microsoft(self,c):
        headers={'Authorization':'Bearer '+c['access_token'],'Prefer':'outlook.timezone="UTC"'}
        now=datetime.now(timezone.utc)
        events=self.paged_links('https://graph.microsoft.com/v1.0/me/calendar/calendarView',headers,'value',{
            'startDateTime':iso(now),'endDateTime':iso(now+timedelta(days=30)),
            '$select':'id,subject,start,end,location,isCancelled,isAllDay','$top':100})
        return {'calendar': [normal(r.get('id'), r.get('subject') or 'Calendar event',
            'Cancelled' if r.get('isCancelled') else 'Scheduled',
            start=nested(r,'start','dateTime'), end=nested(r,'end','dateTime'),
            timezone=nested(r,'start','timeZone',default='UTC'),all_day=bool(r.get('isAllDay',False)),
            location=nested(r,'location','displayName',default=''), owner='You') for r in events]}

    def sync_google(self,c):
        headers={'Authorization':'Bearer '+c['access_token']}
        now=datetime.now(timezone.utc)
        params={
            'timeMin':iso(now),
            'timeMax':iso(now+timedelta(days=30)),
            'singleEvents':'true',
            'orderBy':'startTime',
            'maxResults':250,
            'timeZone':'Australia/Sydney',
            'fields':'items(id,summary,start,end,location,status),nextPageToken',
        }
        rows=[];seen=set();page_token=None
        for _ in range(self.max_pages):
            request_params={**params}
            if page_token:
                request_params['pageToken']=page_token
            data=self.request('GET','https://www.googleapis.com/calendar/v3/calendars/primary/events',
                              headers=headers,params=request_params,allowed_host='www.googleapis.com')
            batch=collection(data,'items')
            for row in batch:
                rid=str(row.get('id',''))
                if not rid or rid in seen:
                    raise ConnectorError('Google Calendar returned a missing or repeated event ID. The previous snapshot was preserved.')
                seen.add(rid)
            rows.extend(batch)
            page_token=data.get('nextPageToken') if isinstance(data,dict) else None
            if not page_token:
                break
        else:
            raise ConnectorError('Google Calendar sync reached the page limit. The previous snapshot was preserved.')
        events=[]
        for r in rows:
            start=r.get('start') if isinstance(r.get('start'),dict) else {}
            end=r.get('end') if isinstance(r.get('end'),dict) else {}
            all_day=bool(start.get('date') and not start.get('dateTime'))
            start_value=start.get('dateTime') or start.get('date')
            end_value=end.get('dateTime') or end.get('date')
            events.append(normal(r.get('id'),r.get('summary') or 'Calendar event',
                'Cancelled' if r.get('status')=='cancelled' else 'Scheduled',
                start=start_value,end=end_value,timezone=start.get('timeZone') or 'Australia/Sydney',
                all_day=all_day,location=text(r.get('location')),owner='You',calendar_source='Google Calendar'))
        return {'calendar':events}

    def sync_xero(self,c):
        headers={'Authorization':'Bearer '+c['access_token']}
        connections=self.request('GET','https://api.xero.com/connections',headers=headers)
        if not isinstance(connections,list) or not any(str(x.get('tenantId'))==str(c['tenant_id']) for x in connections):
            raise ConnectorError('The selected Xero organisation was not authorised. No invoices were imported.')
        headers['Xero-tenant-id']=c['tenant_id']
        rows=[];ids=set()
        for page in range(1,self.max_pages+1):
            data=self.request('GET','https://api.xero.com/api.xro/2.0/Invoices',headers=headers,params={'page':page,'pageSize':100})
            batch=collection(data,'Invoices')
            if not batch:
                break
            for r in batch:
                rid=str(r.get('InvoiceID',''))
                if not rid or rid in ids:
                    raise ConnectorError('Xero pagination returned missing or repeated invoice IDs.')
                ids.add(rid)
            rows.extend(batch)
        else:
            raise ConnectorError('Xero sync reached the page limit; cached data was preserved.')
        return {'invoices':[normal(r.get('InvoiceID'),r.get('InvoiceNumber'),r.get('Status'),
                 contact=nested(r,'Contact','Name',default=''),type=r.get('Type'),amount=r.get('Total'),due=r.get('AmountDue'),
                 currency=r.get('CurrencyCode'),date=r.get('DateString'),due_date=r.get('DueDateString'),owner='Xero') for r in rows]}

    def sync_docusign(self,c):
        headers={'Authorization':'Bearer '+c['access_token']}
        info=self.request('GET',oauth_spec('docusign',c)['userinfo'],headers=headers)
        accounts=collection(info,'accounts')
        account=next((a for a in accounts if str(a.get('account_id'))==str(c['account_id'])),None)
        if not account:
            raise ConnectorError('The selected DocuSign account was not authorised.')
        base=account.get('base_uri','')
        p=urlparse(base)
        if p.scheme!='https' or not re.fullmatch(r'[a-zA-Z0-9-]+\.docusign\.net',p.hostname or '') or p.path not in ('','/') or p.port not in (None,443):
            raise ConnectorError('DocuSign returned an unrecognised API base address.')
        prefix='/restapi/v2.1/accounts/'+ident(c['account_id'])+'/envelopes'
        rows=self.paged_links(base.rstrip('/')+prefix,headers,'envelopes',{
            'from_date':iso(datetime.now(timezone.utc)-timedelta(days=90)),'count':100},base_path=prefix)
        return {'documents':[normal(r.get('envelopeId'),r.get('emailSubject'),r.get('status'),
                 updated=r.get('statusChangedDateTime'),created=r.get('createdDateTime'),owner='DocuSign',type='Envelope') for r in rows]}
