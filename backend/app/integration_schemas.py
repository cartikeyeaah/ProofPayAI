from typing import Literal
from pydantic import Field
from .schemas import ContractModel, Identifier
from ai_engine.schemas import ExtractedFact, PipelineResult

class Capabilities(ContractModel):
    analysis_engine: Literal['ai_engine_v1'] = 'ai_engine_v1'
    data_mode: Literal['synthetic'] = 'synthetic'
    persistence: Literal['temporary', 'postgresql'] = 'temporary'
    ocr: Literal['unavailable', 'local'] = 'unavailable'
    uploads: Literal[True] = True

class EvidenceMetadata(ContractModel):
    id: Identifier
    transaction_id: Identifier
    filename: str
    document_type: Literal['invoice', 'order_confirmation', 'delivery_record', 'other']
    media_type: str
    size_bytes: int
    upload_status: Literal['stored'] = 'stored'
    processing_status: Literal['not_processed', 'processing', 'parsed', 'unsupported', 'failed', 'duplicate'] = 'not_processed'
    analysis_id: str | None = None
    issue_codes: list[str] = Field(default_factory=list)
    facts: list[ExtractedFact] = Field(default_factory=list)

class AnalysisDetails(ContractModel):
    analysis_id: Identifier
    engine: Literal['ai_engine_v1'] = 'ai_engine_v1'
    failure_code: Literal['PIPELINE_TIMEOUT', 'PIPELINE_ERROR', 'INVALID_PIPELINE_OUTPUT'] | None = None
    result: PipelineResult | None = None
