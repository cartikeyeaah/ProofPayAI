"""Sandbox HTTP client and transaction reporting. No live endpoint."""
from datetime import timedelta
from decimal import Decimal, InvalidOperation
import time
import math
from threading import RLock
from uuid import uuid4
import httpx
from backend.app.schemas import Transaction
from backend.app.errors import APIError
from backend.db.repository import now

SCOPE = 'https://uri.paypal.com/services/reporting/search/read'
BASE = 'https://api-m.sandbox.paypal.com'

class SandboxClient:
    def __init__(self, client_id, secret, transport=None):
        self.client_id, self.secret = client_id, secret
        self.transport = transport
        self.token, self.expires = None, 0
        self.scopes = set()
        self.lock = RLock()

    def request(self, method, path, **kwargs):
        try:
            with httpx.Client(base_url=BASE, timeout=15, follow_redirects=False, transport=self.transport, trust_env=False) as client:
                response = client.request(method, path, **kwargs)
            if response.status_code in (401,403):
                self.token = None
                raise APIError(503, 'PAYPAL_PERMISSION_DENIED', 'Sandbox credentials or Transaction Search permissions are unavailable.')
            if response.status_code == 429: raise APIError(503, 'PAYPAL_RATE_LIMITED', 'Sandbox rate limit reached. Wait before retrying.')
            if response.status_code == 422: raise APIError(422, 'PAYPAL_ORDER_NOT_READY', 'Sandbox order cannot be processed. Check approval and order status.')
            if response.status_code not in (200,201): raise APIError(503, 'PAYPAL_UNAVAILABLE', 'Sandbox service is unavailable. Retry later.')
            return response.json()
        except (httpx.HTTPError, ValueError):
            raise APIError(503, 'PAYPAL_UNAVAILABLE', 'Sandbox request failed safely. Retry later.')

    def access_token(self, required_scope=SCOPE):
        with self.lock:
            if not self.token or self.expires <= time.monotonic():
                data = self.request('POST','/v1/oauth2/token', auth=(self.client_id,self.secret), data={'grant_type':'client_credentials'})
                if not isinstance(data,dict):
                    raise APIError(503,'PAYPAL_UNAVAILABLE','Sandbox returned an invalid token response.')
                self.scopes = set(str(data.get('scope','')).split())
                if required_scope and required_scope not in self.scopes:
                    raise APIError(503,'PAYPAL_SCOPE_MISSING','The Sandbox app must grant the Transaction Search reporting scope.')
                expiry = data.get('expires_in')
                if not isinstance(data.get('access_token'),str) or not data['access_token'] or isinstance(expiry,bool) or not isinstance(expiry,(int,float)) or not math.isfinite(expiry) or expiry <= 0:
                    raise APIError(503,'PAYPAL_UNAVAILABLE','Sandbox returned an invalid token response.')
                self.token = data['access_token']; self.expires = time.monotonic()+max(0,expiry-60)
            if required_scope and required_scope not in self.scopes:
                raise APIError(503,'PAYPAL_SCOPE_MISSING','The Sandbox app must grant the Transaction Search reporting scope.')
            return self.token

    def authorized(self, method, path, required_scope=SCOPE, **kwargs):
        extra_headers = kwargs.pop('headers',{})
        for attempt in range(2):
            token = self.access_token(required_scope)
            try:
                return self.request(method,path,headers={'Authorization':'Bearer '+token,**extra_headers},**kwargs)
            except APIError as exc:
                if exc.code != 'PAYPAL_PERMISSION_DENIED' or attempt: raise
                self.token = None

    def check(self):
        end = now()
        data = self.authorized('GET','/v1/reporting/transactions',params={'start_date':(end-timedelta(days=1)).isoformat(timespec='seconds'),'end_date':end.isoformat(timespec='seconds'),'page_size':1,'page':1,'fields':'transaction_info','balance_affecting_records_only':'Y'})
        if not isinstance(data,dict) or not isinstance(data.get('transaction_details'),list):
            raise APIError(503,'PAYPAL_UNAVAILABLE','Sandbox returned an invalid reporting response.')
        return {'status':'connected','environment':'sandbox','reporting_access':True}

    def sync(self):
        end = now(); start = end-timedelta(days=7)
        records, skipped, seen = [], 0, set()
        # All-or-nothing bounded window. Never silently report a truncated successful sync.
        for page in range(1,11):
            data = self.authorized('GET','/v1/reporting/transactions', params={'start_date':start.isoformat(timespec='seconds'), 'end_date':end.isoformat(timespec='seconds'), 'page_size':100, 'page':page, 'fields':'transaction_info', 'balance_affecting_records_only':'Y'})
            if not isinstance(data,dict) or not isinstance(data.get('transaction_details'),list):
                raise APIError(503,'PAYPAL_UNAVAILABLE','Sandbox returned an invalid reporting response.')
            for item in data['transaction_details']:
                try:
                    info = item['transaction_info']; amount = info['transaction_amount']
                    if info['transaction_status'] != 'S': skipped += 1; continue
                    number = Decimal(amount['value'])
                    if not number.is_finite() or number != number.quantize(Decimal('.01')): skipped += 1; continue
                    external = info['transaction_id']
                    if external in seen: skipped += 1; continue
                    transaction = Transaction(id='txn_'+str(uuid4()), paypal_transaction_id=external, amount=format(number,'.2f'), currency=amount['currency_code'], status='COMPLETED', transaction_date=info['transaction_initiation_date'], evidence_count=0)
                    records.append(transaction); seen.add(external)
                except (KeyError, TypeError, ValueError, InvalidOperation, AttributeError): skipped += 1
            pages = data.get('total_pages',1)
            if isinstance(pages,bool) or not isinstance(pages,int) or pages < 0: raise APIError(503,'PAYPAL_UNAVAILABLE','Invalid Sandbox pagination.')
            if pages <= page: return records, skipped
        raise APIError(503,'PAYPAL_WINDOW_TOO_LARGE','More than 1,000 records exist in the sync window; no records were imported.')
