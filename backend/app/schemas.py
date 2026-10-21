from typing import Annotated, Literal
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

Identifier = Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")]

class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class Transaction(ContractModel):
    id: Identifier
    paypal_transaction_id: str
    amount: Annotated[str, Field(pattern=r"^-?[0-9]{1,10}\.[0-9]{2}$", description="Exact decimal amount serialized as a string")]
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
    status: Literal["COMPLETED"]
    transaction_date: AwareDatetime
    evidence_count: Annotated[int, Field(ge=0)]

class Finding(ContractModel):
    id: Identifier
    issue_type: str
    severity: Literal["low", "medium", "high"]
    explanation: str
    source_ids: list[Identifier]
    recommendation: str

class Analysis(ContractModel):
    analysis_id: Identifier
    transaction_id: Identifier
    status: Literal["queued", "processing", "completed", "failed"]
    findings: list[Finding]
    draft_response: str | None
    merchant_approval_required: Literal[True]

class AnalyzeRequest(ContractModel):
    """Reserved integration boundary: only an empty JSON object is accepted."""

class Health(ContractModel):
    status: Literal["ok"]
    mode: Literal["mock"]

class ErrorDetail(ContractModel):
    code: str
    message: str
    request_id: str

class ErrorResponse(ContractModel):
    error: ErrorDetail
