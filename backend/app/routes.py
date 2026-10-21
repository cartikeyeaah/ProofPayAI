from uuid import uuid4
from fastapi import APIRouter, BackgroundTasks, Header, Request, status
from .mock_data import DEMO_ANALYSIS
from .schemas import Analysis, AnalyzeRequest, Health, Identifier, Transaction
from .errors import APIError
from backend.db.repository import get_store, save, event
from .auth import rate_limit

router = APIRouter(prefix="/api/v1")

def transaction_or_404(request: Request, transaction_id: str) -> Transaction:
    transaction = get_store(request).transactions.get(transaction_id)
    if transaction is None:
        raise APIError(404, "TRANSACTION_NOT_FOUND", "The requested transaction was not found.")
    return transaction

@router.get("/health", response_model=Health)
def health():
    return Health(status="ok", mode="mock")

@router.get("/transactions", response_model=list[Transaction])
def transactions(request: Request):
    return list(get_store(request).transactions.values())

@router.get("/transactions/{transaction_id}", response_model=Transaction)
def transaction(request: Request, transaction_id: Identifier):
    return transaction_or_404(request, transaction_id)

@router.post("/transactions/{transaction_id}/analyze", response_model=Analysis, status_code=status.HTTP_202_ACCEPTED)
def analyze(request: Request, transaction_id: Identifier, payload: AnalyzeRequest, background_tasks: BackgroundTasks, idempotency_key: str | None = Header(None, min_length=1, max_length=100)):
    from .evidence import snapshot
    from .integration_schemas import AnalysisDetails
    from .worker import execute_job
    transaction = transaction_or_404(request, transaction_id)
    store = get_store(request)
    with store.lock:
        if idempotency_key and idempotency_key in store.idempotency:
            previous = store.analyses[store.idempotency[idempotency_key]]
            if previous.transaction_id != transaction_id:
                raise APIError(409, 'IDEMPOTENCY_CONFLICT', 'This request key belongs to another transaction.')
            return previous
        if store.repository:
            rate_limit(request.app, ('analysis', store.merchant_id), count=10)
        if store.active_transactions:
            raise APIError(409, "ANALYSIS_ACTIVE", "A local analysis is active. Retry when it finishes.")
        job = Analysis(analysis_id=f"analysis_{uuid4()}", transaction_id=transaction_id,
                       status="queued", findings=[], draft_response=None, merchant_approval_required=True)
        pipeline_input = snapshot(store, transaction, job.analysis_id)
        store.analyses[job.analysis_id] = job
        store.details[job.analysis_id] = AnalysisDetails(analysis_id=job.analysis_id)
        store.active_transactions.add(transaction_id)
        if idempotency_key:
            store.idempotency[idempotency_key] = job.analysis_id
        event(store, 'analysis_queued', job.analysis_id, request.state.actor)
        save(store)
        background_tasks.add_task(execute_job, request.app, pipeline_input, store)
        return job.model_copy(deep=True)

@router.get("/analysis/{analysis_id}", response_model=Analysis)
def analysis(request: Request, analysis_id: Identifier):
    job = get_store(request).analyses.get(analysis_id)
    if job is None:
        raise APIError(404, "ANALYSIS_NOT_FOUND", "The requested analysis was not found.")
    return job

@router.get("/transactions/{transaction_id}/demo-analysis", response_model=Analysis,
            description="Static contract demonstration only; does not process evidence or complete a job.")
def demo_analysis(request: Request, transaction_id: Identifier):
    transaction_or_404(request, transaction_id)
    return DEMO_ANALYSIS.model_copy(update={"transaction_id": transaction_id}, deep=True)
