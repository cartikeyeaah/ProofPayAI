from uuid import uuid4
from fastapi import APIRouter, Request, status
from .mock_data import DEMO_ANALYSIS
from .schemas import Analysis, AnalyzeRequest, Health, Identifier, Transaction
from .errors import APIError

router = APIRouter(prefix="/api/v1")

def transaction_or_404(request: Request, transaction_id: str) -> Transaction:
    transaction = request.app.state.store.transactions.get(transaction_id)
    if transaction is None:
        raise APIError(404, "TRANSACTION_NOT_FOUND", "The requested transaction was not found.")
    return transaction

@router.get("/health", response_model=Health)
def health():
    return Health(status="ok", mode="mock")

@router.get("/transactions", response_model=list[Transaction])
def transactions(request: Request):
    return list(request.app.state.store.transactions.values())

@router.get("/transactions/{transaction_id}", response_model=Transaction)
def transaction(request: Request, transaction_id: Identifier):
    return transaction_or_404(request, transaction_id)

@router.post("/transactions/{transaction_id}/analyze", response_model=Analysis, status_code=status.HTTP_202_ACCEPTED)
def analyze(request: Request, transaction_id: Identifier, payload: AnalyzeRequest):
    transaction_or_404(request, transaction_id)
    job = Analysis(analysis_id=f"analysis_{uuid4()}", transaction_id=transaction_id,
                   status="queued", findings=[], draft_response=None, merchant_approval_required=True)
    request.app.state.store.analyses[job.analysis_id] = job
    return job

@router.get("/analysis/{analysis_id}", response_model=Analysis)
def analysis(request: Request, analysis_id: Identifier):
    job = request.app.state.store.analyses.get(analysis_id)
    if job is None:
        raise APIError(404, "ANALYSIS_NOT_FOUND", "The requested analysis was not found.")
    return job

@router.get("/transactions/{transaction_id}/demo-analysis", response_model=Analysis,
            description="Static contract demonstration only; does not process evidence or complete a job.")
def demo_analysis(request: Request, transaction_id: Identifier):
    transaction_or_404(request, transaction_id)
    return DEMO_ANALYSIS.model_copy(update={"transaction_id": transaction_id}, deep=True)
