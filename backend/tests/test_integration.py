import json
import time
from io import BytesIO
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
from backend.app.main import create_app
from ai_engine import run_pipeline

BASE = '/api/v1/transactions/txn_demo_001'
SAMPLE = json.loads((Path(__file__).resolve().parents[2] / 'contracts/ai-engine/sample-input.json').read_text())

def pdf_bytes(text):
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})})
    stream = DecodedStreamObject()
    content = 'BT /F1 12 Tf 50 700 Td ' + ' 0 -16 Td '.join('(' + line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)') + ') Tj' for line in text.splitlines()) + ' ET'
    stream.set_data(content.encode('ascii', errors='replace'))
    page[NameObject('/Contents')] = stream
    output = BytesIO(); writer.write(output)
    return output.getvalue()

@pytest.fixture
def client():
    with TestClient(create_app()) as c:
        yield c

def upload(client, data, name='synthetic.pdf', mime='application/pdf', kind='invoice'):
    response = client.post(BASE + '/documents', files={'file': (name, data, mime)}, data={'document_type': kind})
    assert response.status_code == 201, response.text
    return response.json()

def analyze(client):
    response = client.post(BASE + '/analyze', json={})
    assert response.status_code == 202
    assert response.json()['status'] == 'queued'
    aid = response.json()['analysis_id']
    return client.get('/api/v1/analysis/' + aid).json(), client.get('/api/v1/analysis/' + aid + '/details').json()

def test_actual_pdf_pipeline_and_stable_sources(client):
    invoice = SAMPLE['documents'][0]['text'].replace('150.00', '151.00')
    document = upload(client, pdf_bytes(invoice), name='../../synthetic.pdf')
    assert document['filename'] == 'synthetic.pdf'
    assert document['processing_status'] == 'not_processed' and document['upload_status'] == 'stored'
    path = Path(client.app.state.store.storage.name) / document['id']
    assert path.exists() and path.stat().st_mode & 0o777 == 0o600
    job, details = analyze(client)
    assert job['status'] == 'completed' and details['engine'] == 'ai_engine_v1'
    assert details['result']['pages'] and details['result']['facts']
    assert {'missing_delivery_proof', 'amount_mismatch'} <= {f['issue_type'] for f in job['findings']}
    assert all(set(f['source_ids']) <= {document['id']} for f in job['findings'])
    mismatch = next(f for f in job['findings'] if f['issue_type'] == 'amount_mismatch')
    assert mismatch['source_ids'] == [document['id']]
    assert details['result']['finding_sources'][mismatch['id']][0]['quote'] == 'USD 151.00'
    metadata = client.get(BASE + '/documents/' + document['id']).json()
    assert metadata['processing_status'] == 'parsed' and metadata['facts']
    assert metadata['analysis_id'] == job['analysis_id']
    assert client.get(BASE).json()['evidence_count'] == 1
    demo = client.get(BASE + '/demo-analysis').json()
    assert demo['analysis_id'] == 'analysis_demo_001' and demo != job
    assert client.get('/api/v1/analysis/analysis_demo_001/details').status_code == 404
    assert client.get('/' + document['id']).status_code == 404

def test_complete_evidence_and_date_mismatch(client):
    for doc in SAMPLE['documents']:
        upload(client, pdf_bytes(doc['text']), kind=doc['document_type'])
    job, details = analyze(client)
    assert job['status'] == 'completed' and job['findings'] == []
    assert job['draft_response'] and job['merchant_approval_required']
    bad = SAMPLE['documents'][1]['text'].replace('2026-10-17', '2026-10-14')
    upload(client, pdf_bytes(bad), kind='delivery_record')
    job, _ = analyze(client)
    assert 'conflicting_dates' in {f['issue_type'] for f in job['findings']}

@pytest.mark.parametrize('data,mime,status,code', [(b'', 'application/pdf', 413, 'INVALID_FILE_SIZE'), (b'x' * (10*1024*1024+1), 'application/pdf', 413, 'INVALID_FILE_SIZE'), (b'no', 'application/pdf', 422, 'INVALID_FILE_SIGNATURE'), (b'hello', 'application/zip', 415, 'UNSUPPORTED_FILE_TYPE'), (b'\xff', 'text/plain', 422, 'INVALID_TEXT')])
def test_invalid_uploads(client, data, mime, status, code):
    response = client.post(BASE + '/documents', files={'file': ('test', data, mime)}, data={'document_type': 'invoice'})
    assert response.status_code == status
    assert response.json()['error']['code'] == code
    assert client.get(BASE + '/documents').json() == []

def test_ocr_unavailable_and_parse_failure(client):
    # Valid one-pixel PNG; no OCR is configured.
    import base64
    png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')
    image = upload(client, png, name='test.png', mime='image/png')
    badpdf = upload(client, b'%PDF-broken')
    job, details = analyze(client)
    assert job['status'] == 'failed'
    docs = {d['id']: d for d in client.get(BASE + '/documents').json()}
    assert docs[image['id']]['processing_status'] == 'unsupported'
    assert docs[image['id']]['issue_codes'] == ['IMAGE_OCR_REQUIRED']
    assert docs[badpdf['id']]['processing_status'] == 'failed'
    assert not details['result']['facts']

def exploding(payload):
    raise RuntimeError('secret-value')

def malformed(payload):
    return {'secret': 'secret-value'}

def invalid_source(payload):
    result = run_pipeline(payload)
    result.analysis.findings[0].source_ids = ['doc_invented']
    return result

def slow(payload):
    time.sleep(5)
    return run_pipeline(payload)

@pytest.mark.parametrize('runner,code', [(exploding, 'PIPELINE_ERROR'), (malformed, 'INVALID_PIPELINE_OUTPUT'), (invalid_source, 'INVALID_PIPELINE_OUTPUT'), (slow, 'PIPELINE_TIMEOUT')])
def test_worker_failures(client, runner, code):
    client.app.state.pipeline_runner = runner
    if runner is slow:
        client.app.state.pipeline_timeout = 0.1
    job, details = analyze(client)
    assert job['status'] == 'failed' and job['findings'] == []
    assert details['failure_code'] == code and details['result'] is None
    assert 'secret-value' not in json.dumps(details)
    assert not client.app.state.store.active_transactions
    assert client.get('/api/v1/health').status_code == 200

def test_transaction_scope_and_lifecycle(client):
    doc = upload(client, b'Transaction ID: DEMO-1001', name='test.txt', mime='text/plain')
    transaction = client.app.state.store.transactions['txn_demo_001'].model_copy(update={'id': 'txn_other', 'evidence_count': 0})
    client.app.state.store.transactions['txn_other'] = transaction
    assert client.get('/api/v1/transactions/txn_other/documents').json() == []
    assert client.get('/api/v1/transactions/txn_other/documents/' + doc['id']).status_code == 404
    client.app.state.store.active_transactions.add('txn_demo_001')
    assert client.post(BASE + '/analyze', json={}).status_code == 409
    assert client.post(BASE + '/documents', files={'file': ('test.txt', b'test', 'text/plain')}, data={'document_type': 'invoice'}).status_code == 409

def test_private_files_removed_on_shutdown():
    app = create_app()
    with TestClient(app) as client:
        upload(client, b'synthetic', name='test.txt', mime='text/plain')
        folder = Path(app.state.store.storage.name)
        assert folder.exists()
    assert not folder.exists()

def test_processing_is_observable_and_does_not_block_health(client):
    from concurrent.futures import ThreadPoolExecutor
    client.app.state.pipeline_runner = slow
    client.app.state.pipeline_timeout = 0.5
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(client.post, BASE + '/analyze', json={})
        deadline = time.monotonic() + 3
        job = None
        while time.monotonic() < deadline:
            jobs = list(client.app.state.store.analyses.values())
            if jobs and jobs[0].status == 'processing':
                job = jobs[0]
                break
            time.sleep(0.01)
        assert job is not None
        assert client.get('/api/v1/analysis/' + job.analysis_id).json()['status'] == 'processing'
        assert client.get('/api/v1/health').status_code == 200
        assert client.post(BASE + '/analyze', json={}).status_code == 409
        assert future.result(timeout=5).status_code == 202
        assert client.get('/api/v1/analysis/' + job.analysis_id).json()['status'] == 'failed'

def test_scanned_pdf_reports_unsupported(client):
    writer = PdfWriter(); writer.add_blank_page(width=100, height=100)
    output = BytesIO(); writer.write(output)
    doc = upload(client, output.getvalue())
    job, _ = analyze(client)
    assert job['status'] == 'failed'
    metadata = client.get(BASE + '/documents/' + doc['id']).json()
    assert metadata['processing_status'] == 'unsupported'
    assert metadata['issue_codes'] == ['PDF_OCR_REQUIRED']

def test_document_limit_and_required_fields(client):
    assert client.post(BASE + '/documents', files={'file': ('test.txt', b'hello', 'text/plain')}).status_code == 422
    for _ in range(25):
        upload(client, b'synthetic', name='test.txt', mime='text/plain')
    response = client.post(BASE + '/documents', files={'file': ('test.txt', b'hello', 'text/plain')}, data={'document_type': 'invoice'})
    assert response.status_code == 409 and response.json()['error']['code'] == 'DOCUMENT_LIMIT'
