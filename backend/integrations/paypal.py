"""Read-only Sandbox Transaction Search. No live endpoint or payment operations."""
from datetime import timedelta
from decimal import Decimal, InvalidOperation
import time
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

    def request(self, method, path, **kwargs):
        try:
            with httpx.Client(base_url=BASE, timeout=15, follow_redirects=False, transport=self.transport) as client:
                response = client.request(method, path, **kwargs)
            if response.status_code in (401,403):
                self.token = None
                raise APIError(503, 'PAYPAL_PERMISSION_DENIED', 'Sandbox credentials or Transaction Search permissions are unavailable.')
            if response.status_code != 200: raise APIError(503, 'PAYPAL_UNAVAILABLE', 'Sandbox service is unavailable. Retry later.')
            return response.json()
        except (httpx.HTTPError, ValueError):
            raise APIError(503, 'PAYPAL_UNAVAILABLE', 'Sandbox request failed safely. Retry later.')

    def access_token(self):
        if self.token and self.expires > time.monotonic(): return self.token
        data = self.request('POST','/v1/oauth2/token', auth=(self.client_id,self.secret), data={'grant_type':'client_credentials'})
        if not isinstance(data,dict) or SCOPE not in str(data.get('scope','')).split():
            raise APIError(503,'PAYPAL_SCOPE_MISSING','The Sandbox app must grant the Transaction Search reporting scope.')
        if not isinstance(data.get('access_token'),str) or not isinstance(data.get('expires_in'),(int,float)):
            raise APIError(503,'PAYPAL_UNAVAILABLE','Sandbox returned an invalid token response.')
        self.token = data['access_token']; self.expires = time.monotonic()+max(0,data['expires_in']-60)
        return self.token

    def sync(self):
        token = self.access_token()
        end = now(); start = end-timedelta(days=7)
        records, skipped, seen = [], 0, set()
        # All-or-nothing bounded window. Never silently report a truncated successful sync.
        for page in range(1,11):
            data = self.request('GET','/v1/reporting/transactions', headers={'Authorization':'Bearer '+token}, params={'start_date':start.isoformat(timespec='seconds'), 'end_date':end.isoformat(timespec='seconds'), 'page_size':100, 'page':page, 'fields':'transaction_info', 'balance_affecting_records_only':'Y'})
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
                except (KeyError, TypeError, ValueError, InvalidOperation): skipped += 1
            pages = data.get('total_pages',1)
            if not isinstance(pages,int) or pages < 0: raise APIError(503,'PAYPAL_UNAVAILABLE','Invalid Sandbox pagination.')
            if pages <= page: return records, skipped
        raise APIError(503,'PAYPAL_WINDOW_TOO_LARGE','More than 1,000 records exist in the sync window; no records were imported.')
