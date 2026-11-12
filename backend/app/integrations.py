import os
from fastapi import APIRouter, Request
from .schemas import ContractModel
from pydantic import Field
from .errors import APIError
from .auth import rate_limit
from .ocr import available
from backend.db.repository import get_store, event, save
from backend.integrations.paypal import SandboxClient

router = APIRouter(prefix='/api/v1/integrations')
class IntegrationStatus(ContractModel):
    mode: str
    persistence: str
    ocr: str
    paypal: str
    paypal_verified: bool
    analysis_engine: str = 'deterministic-local-v1'
    limitations: list[str]
    configuration_issues: list[str] = Field(default_factory=list)
    merchant_id: str | None = None
class SyncResult(ContractModel):
    imported: int
    skipped: int
    mode: str = 'sandbox'

def configuration_issues(request):
    store = get_store(request)
    issues = []
    if not store.repository: issues.append('Use a PostgreSQL account to connect Sandbox.')
    for key in ('PAYPAL_CLIENT_ID','PAYPAL_CLIENT_SECRET'):
        value = os.getenv(key,'').strip()
        if not value or value.startswith(('YOUR_','REPLACE_')):
            issues.append(key + ' is missing in the backend configuration.')
    if os.getenv('PAYPAL_MERCHANT_ID','').strip() != store.merchant_id:
        issues.append('PAYPAL_MERCHANT_ID must match your workspace ID below.')
    return issues


def configured(request):
    return not configuration_issues(request)

@router.get('', response_model=IntegrationStatus)
def status(request: Request):
    store = get_store(request)
    verified = configured(request) and any(e['action']=='paypal_sandbox_sync_verified' for e in store.events)
    return IntegrationStatus(mode='persistent' if store.repository else 'demo', persistence='postgresql' if store.repository else 'temporary', ocr='local-tesseract' if available() else 'unavailable', paypal='verified-sandbox' if verified else 'configured-unverified' if configured(request) else 'not-configured', paypal_verified=verified, configuration_issues=configuration_issues(request), merchant_id=store.merchant_id if store.repository else None, limitations=['Draft preparation only; no dispute submission.', 'Single backend process; no distributed worker.', 'No hosted model configured.'])

@router.post('/paypal/sync', response_model=SyncResult)
def sync(request: Request):
    if not configured(request): raise APIError(503,'PAYPAL_NOT_CONFIGURED','Configure authorized Sandbox credentials and the bound merchant on the backend.')
    store = get_store(request)
    rate_limit(request.app, ('paypal',store.merchant_id),count=2)
    with store.lock:
        if store.active_transactions: raise APIError(409,'ANALYSIS_ACTIVE','Wait for the active analysis before syncing.')
        client = request.app.state.paypal_clients.get(store.merchant_id)
        if client is None:
            client = SandboxClient(os.environ['PAYPAL_CLIENT_ID'],os.environ['PAYPAL_CLIENT_SECRET'])
            request.app.state.paypal_clients[store.merchant_id] = client
        records, skipped = client.sync()
        known = {t.paypal_transaction_id for t in store.transactions.values()}
        imported = 0
        for t in records:
            if t.paypal_transaction_id in known: skipped += 1; continue
            store.transactions[t.id] = t; store.origins[t.id] = 'sandbox'; known.add(t.paypal_transaction_id); imported += 1
        event(store,'paypal_sandbox_sync_verified',store.merchant_id,request.state.actor); save(store)
    return SyncResult(imported=imported,skipped=skipped)


class ConnectionResult(ContractModel):
    status: str
    environment: str
    reporting_access: bool

@router.post('/paypal/check', response_model=ConnectionResult)
def check_connection(request: Request):
    if not configured(request): raise APIError(503,'PAYPAL_NOT_CONFIGURED','Configure authorized Sandbox credentials and the bound merchant on the backend.')
    store = get_store(request)
    rate_limit(request.app, ('paypal-check',store.merchant_id),count=5)
    # A fresh token tests current credentials, not just a historical success flag.
    client = SandboxClient(os.environ['PAYPAL_CLIENT_ID'],os.environ['PAYPAL_CLIENT_SECRET'])
    return client.check()
