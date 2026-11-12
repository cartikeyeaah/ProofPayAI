from copy import deepcopy
from typing import Literal
from uuid import uuid4
from pathlib import Path
from fastapi import APIRouter, Request, Query
from fastapi.responses import FileResponse
from pydantic import Field
from backend.db.repository import get_store, save, event, now
from .schemas import ContractModel, Identifier, Transaction, Analysis
from .errors import APIError
from .auth import rate_limit

router = APIRouter(prefix='/api/v1')
class Draft(ContractModel):
    analysis_id: Identifier
    text: str
    version: int
    status: Literal['draft', 'approved']
    warnings: list[str]
    approved_by: str | None
    approved_at: str | None
class EditDraft(ContractModel):
    text: str = Field(max_length=30000)
    version: int = Field(ge=1)
class ApproveDraft(ContractModel):
    version: int = Field(ge=1)
    acknowledge_warnings: bool = False
class Page(ContractModel):
    items: list[Transaction]
    total: int
    page: int
    page_size: int
    origins: dict[str, str]
class Overview(ContractModel):
    total_transactions: int
    analyzed_transactions: int
    open_cases: int
    awaiting_review: int
    evidence_issues: int
    analyses: list[Analysis]
    activity: list[dict]
    mode: Literal['demo', 'persistent']
class EventList(ContractModel):
    events: list[dict]
    revisions: list[Draft]
class Ready(ContractModel):
    status: str
    storage: str
    database: str

def initialize_draft(store, analysis):
    if analysis.draft_response is None: return
    warnings = ['evidence_issues_require_review'] if analysis.findings else []
    draft = Draft(analysis_id=analysis.analysis_id, text=analysis.draft_response, version=1, status='draft', warnings=warnings, approved_by=None, approved_at=None).model_dump()
    store.drafts[analysis.analysis_id] = draft
    store.revisions.append(deepcopy(draft))

def own_analysis(request, aid):
    store = get_store(request)
    if aid not in store.analyses: raise APIError(404, 'ANALYSIS_NOT_FOUND', 'The requested analysis was not found.')
    return store

@router.get('/ready', response_model=Ready)
def ready(request: Request):
    from sqlalchemy import text
    repo = request.app.state.repository
    try:
        if repo:
            with repo.engine.connect() as conn:
                conn.execute(text('SELECT id FROM proofpay.merchants LIMIT 1'))
        folder = Path(repo.root if repo else request.app.state.store.storage.name)
        probe = folder / ('.readiness-' + str(uuid4()))
        probe.write_bytes(b''); probe.unlink()
    except Exception:
        raise APIError(503, 'NOT_READY', 'Application storage is unavailable.')
    return Ready(status='ready', storage='private-local' if repo else 'temporary', database='postgresql' if repo else 'not-configured')

@router.get('/transaction-page', response_model=Page)
def transaction_page(request: Request, q: str = Query('', max_length=100), page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100), sort: Literal['date','amount','id'] = 'date', direction: Literal['asc','desc'] = 'desc', analyzed: Literal['all','yes','no'] = 'all'):
    from decimal import Decimal
    store = get_store(request)
    done = {a.transaction_id for a in store.analyses.values() if a.status == 'completed'}
    items = [t for t in store.transactions.values() if q.lower() in (t.id+' '+t.paypal_transaction_id).lower() and (analyzed == 'all' or (t.id in done) == (analyzed == 'yes'))]
    items.sort(key=lambda t: Decimal(t.amount) if sort == 'amount' else t.id if sort == 'id' else t.transaction_date, reverse=direction == 'desc')
    return Page(items=items[(page-1)*page_size:page*page_size], total=len(items), page=page, page_size=page_size, origins=store.origins)

@router.get('/overview', response_model=Overview)
def overview(request: Request):
    store = get_store(request)
    analyses = list(store.analyses.values())
    latest = {}
    for a in analyses: latest[a.transaction_id] = a
    return Overview(total_transactions=len(store.transactions), analyzed_transactions=len({a.transaction_id for a in analyses if a.status=='completed'}), open_cases=sum(a.status != 'completed' or bool(a.findings) for a in latest.values()), awaiting_review=sum(d['status']=='draft' for d in store.drafts.values()), evidence_issues=sum(len(a.findings) for a in latest.values()), analyses=analyses[::-1], activity=store.events[-20:][::-1], mode='persistent' if store.repository else 'demo')

@router.get('/transactions/{transaction_id}/analyses', response_model=list[Analysis])
def history(request: Request, transaction_id: Identifier):
    store = get_store(request)
    if transaction_id not in store.transactions: raise APIError(404, 'TRANSACTION_NOT_FOUND', 'The requested transaction was not found.')
    return [a for a in reversed(list(store.analyses.values())) if a.transaction_id==transaction_id]

@router.get('/transactions/{transaction_id}/documents/{document_id}/content', response_class=FileResponse, responses={200: {'description': 'Private evidence bytes', 'content': {media: {'schema': {'type':'string','format':'binary'}} for media in ('application/pdf','image/png','image/jpeg','text/plain')}}})
def content(request: Request, transaction_id: Identifier, document_id: Identifier):
    store = get_store(request)
    doc = store.documents.get(document_id)
    if doc is None or doc.transaction_id != transaction_id: raise APIError(404, 'DOCUMENT_NOT_FOUND', 'The requested document was not found.')
    path = Path(store.storage.name) / doc.id
    if not path.is_file(): raise APIError(404, 'DOCUMENT_NOT_FOUND', 'Stored evidence is unavailable.')
    return FileResponse(path, media_type=doc.media_type, filename=doc.filename, content_disposition_type='inline', headers={'Cache-Control':'private, no-store', 'X-Content-Type-Options':'nosniff', 'Content-Security-Policy':"sandbox; default-src 'none'"})

@router.get('/analysis/{analysis_id}/draft', response_model=Draft)
def get_draft(request: Request, analysis_id: Identifier):
    store = own_analysis(request, analysis_id)
    if analysis_id not in store.drafts: raise APIError(404, 'DRAFT_NOT_FOUND', 'No supported draft is available for this analysis.')
    return store.drafts[analysis_id]

@router.put('/analysis/{analysis_id}/draft', response_model=Draft)
def edit_draft(request: Request, analysis_id: Identifier, payload: EditDraft):
    store = own_analysis(request, analysis_id)
    with store.lock:
        old = get_draft(request, analysis_id)
        if old['version'] != payload.version: raise APIError(409, 'VERSION_CONFLICT', 'The draft changed. Reload before editing.')
        warnings = ['evidence_issues_require_review'] if store.analyses[analysis_id].findings else []
        if payload.text != store.analyses[analysis_id].draft_response: warnings.append('manual_edits_not_source_validated')
        updated = Draft(analysis_id=analysis_id, text=payload.text, version=payload.version+1, status='draft', warnings=warnings, approved_by=None, approved_at=None).model_dump()
        store.drafts[analysis_id] = updated
        store.revisions.append(deepcopy(updated))
        event(store,'draft_edited',analysis_id,request.state.actor); save(store)
        return updated

@router.post('/analysis/{analysis_id}/draft/approve', response_model=Draft)
def approve(request: Request, analysis_id: Identifier, payload: ApproveDraft):
    store = own_analysis(request, analysis_id)
    with store.lock:
        draft = deepcopy(get_draft(request, analysis_id))
        if draft['version'] != payload.version: raise APIError(409, 'VERSION_CONFLICT', 'The draft changed. Reload before approval.')
        if not draft['text'].strip(): raise APIError(422,'EMPTY_DRAFT','An empty draft cannot be approved.')
        if draft['warnings'] and not payload.acknowledge_warnings: raise APIError(422, 'REVIEW_REQUIRED', 'Acknowledge the validation warnings before approval.')
        if draft['status'] == 'approved': return draft
        draft.update(status='approved', version=draft['version']+1, approved_by=request.state.actor, approved_at=now().isoformat())
        store.drafts[analysis_id] = draft
        store.revisions.append(deepcopy(draft))
        event(store,'draft_approved_not_submitted',analysis_id,request.state.actor); save(store)
        return draft

@router.get('/analysis/{analysis_id}/audit', response_model=EventList)
def audit(request: Request, analysis_id: Identifier):
    store = own_analysis(request, analysis_id)
    return EventList(events=[e for e in store.events if e['resource_id']==analysis_id], revisions=[d for d in store.revisions if d['analysis_id']==analysis_id])


@router.post('/transactions/synthetic', response_model=Transaction)
def synthetic_transaction(request: Request):
    """Create/reuse one explicitly synthetic upload workspace per merchant."""
    from .mock_data import TRANSACTION
    store = get_store(request)
    rate_limit(request.app, ('synthetic',store.merchant_id),count=10)
    with store.lock:
        for transaction in store.transactions.values():
            if store.origins.get(transaction.id)=='synthetic':
                return transaction
        tid='txn_'+str(uuid4())
        transaction=TRANSACTION.model_copy(update={'id':tid,'paypal_transaction_id':'PROOFPAY-TEST-'+str(uuid4())[:8].upper(),'transaction_date':now(),'evidence_count':0},deep=True)
        store.transactions[tid]=transaction
        store.origins[tid]='synthetic'
        event(store,'synthetic_transaction_created',tid,request.state.actor)
        save(store)
        return transaction
