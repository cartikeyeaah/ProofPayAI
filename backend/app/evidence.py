import base64
from pathlib import Path
from typing import Literal
from uuid import uuid4
from fastapi import APIRouter, File, Form, Request, UploadFile
from ai_engine.schemas import EvidenceDocument, MAX_BYTES, MAX_TEXT, PipelineInput
from .errors import APIError
from backend.db.repository import get_store, save, event
from .integration_schemas import AnalysisDetails, Capabilities, EvidenceMetadata
from .routes import transaction_or_404
from .schemas import Identifier

router = APIRouter(prefix='/api/v1')
SIGNATURES = {'application/pdf': b'%PDF-', 'image/png': b'\x89PNG\r\n\x1a\n', 'image/jpeg': b'\xff\xd8\xff'}

@router.get('/capabilities', response_model=Capabilities)
def capabilities(request: Request):
    from .ocr import available
    return Capabilities(persistence='postgresql' if request.app.state.repository else 'temporary', ocr='local' if available() else 'unavailable')

@router.post('/transactions/{transaction_id}/documents', response_model=EvidenceMetadata, status_code=201)
def upload(request: Request, transaction_id: Identifier,
           document_type: Literal['invoice', 'order_confirmation', 'delivery_record', 'other'] = Form(...),
           file: UploadFile = File(...)):
    transaction_or_404(request, transaction_id)
    try:
        data = file.file.read(MAX_BYTES + 1)
    finally:
        file.file.close()
    if not data or len(data) > MAX_BYTES:
        raise APIError(413, 'INVALID_FILE_SIZE', 'Supply a nonempty file of at most 10 MiB.')
    media_type = file.content_type
    if media_type not in (*SIGNATURES, 'text/plain'):
        raise APIError(415, 'UNSUPPORTED_FILE_TYPE', 'Supported types: PDF, PNG, JPEG and UTF-8 plain text.')
    if media_type in SIGNATURES and not data.startswith(SIGNATURES[media_type]):
        raise APIError(422, 'INVALID_FILE_SIGNATURE', 'The file signature does not match its media type.')
    if media_type == 'text/plain':
        try:
            text = data.decode('utf-8')
        except UnicodeDecodeError:
            raise APIError(422, 'INVALID_TEXT', 'Text evidence must use UTF-8.')
        if len(text) > MAX_TEXT:
            raise APIError(413, 'INVALID_FILE_SIZE', 'Text evidence exceeds the character limit.')
    store = get_store(request)
    with store.lock:
        if transaction_id in store.active_transactions:
            raise APIError(409, 'ANALYSIS_ACTIVE', 'Wait for the current analysis before adding evidence.')
        if sum(d.transaction_id == transaction_id for d in store.documents.values()) >= 25:
            raise APIError(409, 'DOCUMENT_LIMIT', 'At most 25 documents are allowed per transaction.')
        doc_id = f'doc_{uuid4()}'
        filename = Path((file.filename or 'evidence').replace('\\', '/')).name[:255]
        metadata = EvidenceMetadata(id=doc_id, transaction_id=transaction_id, filename=filename,
                                    document_type=document_type, media_type=media_type, size_bytes=len(data))
        path = Path(store.storage.name) / doc_id
        with path.open('xb') as destination:
            path.chmod(0o600)
            destination.write(data)
        store.documents[doc_id] = metadata
        store.transactions[transaction_id].evidence_count += 1
        event(store, 'evidence_uploaded', doc_id, request.state.actor)
        save(store)
        return metadata.model_copy(deep=True)

@router.get('/transactions/{transaction_id}/documents', response_model=list[EvidenceMetadata])
def documents(request: Request, transaction_id: Identifier):
    transaction_or_404(request, transaction_id)
    with get_store(request).lock:
        return [d.model_copy(deep=True) for d in get_store(request).documents.values() if d.transaction_id == transaction_id]

@router.get('/transactions/{transaction_id}/documents/{document_id}', response_model=EvidenceMetadata)
def document(request: Request, transaction_id: Identifier, document_id: Identifier):
    transaction_or_404(request, transaction_id)
    with get_store(request).lock:
        value = get_store(request).documents.get(document_id)
        if value is None or value.transaction_id != transaction_id:
            raise APIError(404, 'DOCUMENT_NOT_FOUND', 'The requested document was not found.')
        return value.model_copy(deep=True)

@router.get('/analysis/{analysis_id}/details', response_model=AnalysisDetails)
def details(request: Request, analysis_id: Identifier):
    value = get_store(request).details.get(analysis_id)
    if value is None:
        raise APIError(404, 'ANALYSIS_NOT_FOUND', 'The requested analysis was not found.')
    return value

def snapshot(store, transaction, analysis_id):
    evidence = []
    for metadata in store.documents.values():
        if metadata.transaction_id != transaction.id:
            continue
        data = (Path(store.storage.name) / metadata.id).read_bytes()
        content = {'text': data.decode('utf-8')} if metadata.media_type == 'text/plain' else {'content_base64': base64.b64encode(data).decode('ascii')}
        evidence.append(EvidenceDocument(id=metadata.id, filename=metadata.filename, document_type=metadata.document_type,
                                        media_type=metadata.media_type, **content))
    return PipelineInput(analysis_id=analysis_id, transaction=transaction.model_copy(deep=True), documents=evidence)
