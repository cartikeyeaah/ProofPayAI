"""Versioned engine boundary; reuse the existing public response models."""
import base64
import binascii
from typing import Annotated, Literal

from pydantic import Field, model_validator
from backend.app.schemas import Analysis, ContractModel, Identifier, Transaction

MAX_BYTES = 10 * 1024 * 1024
MAX_TEXT = 200_000


class EvidenceDocument(ContractModel):
    id: Identifier
    filename: Annotated[str, Field(min_length=1, max_length=255)]
    document_type: Literal["invoice", "order_confirmation", "delivery_record", "other"]
    media_type: Literal["text/plain", "application/pdf", "image/png", "image/jpeg"]
    text: Annotated[str, Field(max_length=MAX_TEXT)] | None = None
    content_base64: Annotated[str, Field(max_length=4 * ((MAX_BYTES + 2) // 3))] | None = None

    @model_validator(mode="after")
    def check_content(self):
        if self.media_type == "text/plain":
            if self.text is None or self.content_base64 is not None:
                raise ValueError("Text documents require text only")
        else:
            if self.text is not None or self.content_base64 is None:
                raise ValueError("Binary documents require content_base64 only")
            try:
                data = base64.b64decode(self.content_base64, validate=True)
            except (ValueError, binascii.Error) as exc:
                raise ValueError("Invalid base64 document") from exc
            if not data or len(data) > MAX_BYTES:
                raise ValueError("Binary document must contain 1 to 10 MiB")
        return self


class PipelineInput(ContractModel):
    contract_version: Literal["1.0"] = "1.0"
    analysis_id: Identifier
    transaction: Transaction
    documents: Annotated[list[EvidenceDocument], Field(max_length=25)]
    require_delivery: bool = True

    @model_validator(mode="after")
    def unique_documents(self):
        ids = [doc.id for doc in self.documents]
        if len(ids) != len(set(ids)):
            raise ValueError("Document IDs must be unique")
        return self


class ParsedPage(ContractModel):
    document_id: Identifier
    page: Annotated[int, Field(ge=1)]
    text: Annotated[str, Field(max_length=MAX_TEXT)]


class SourceReference(ContractModel):
    document_id: Identifier
    page: Annotated[int, Field(ge=1)]
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    quote: str


FactName = Literal["transaction_id", "amount", "currency", "invoice_date", "order_date", "delivery_date", "delivery_status", "tracking_id"]


class ExtractedFact(ContractModel):
    id: Identifier
    name: FactName
    value: str
    source: SourceReference


class DocumentMatch(ContractModel):
    document_id: Identifier
    status: Literal["matched", "unmatched", "ambiguous", "unreadable", "duplicate"]
    reason: str


class ProcessingIssue(ContractModel):
    code: str
    document_id: Identifier | None = None
    message: str


class DraftClaim(ContractModel):
    text: str
    fact_ids: list[Identifier]


class PipelineResult(ContractModel):
    contract_version: Literal["1.0"] = "1.0"
    analysis: Analysis
    pages: list[ParsedPage]
    facts: list[ExtractedFact]
    matches: list[DocumentMatch]
    finding_sources: dict[str, list[SourceReference]]
    draft_claims: list[DraftClaim]
    issues: list[ProcessingIssue]
