import json
from pathlib import Path
from uuid import UUID
import pytest
import yaml
from fastapi.testclient import TestClient
from openapi_spec_validator import validate
from backend.app.main import create_app
from backend.app.schemas import Analysis, ErrorResponse, Transaction

ROOT = Path(__file__).resolve().parents[2]

@pytest.fixture
def client():
    with TestClient(create_app()) as c:
        yield c

def assert_error(response, code, status=404):
    assert response.status_code == status
    error = ErrorResponse.model_validate(response.json()).error
    assert error.code == code
    assert error.message
    assert error.request_id == response.headers['X-Request-ID']
    UUID(error.request_id.removeprefix('req_'))

def test_health_and_docs(client):
    assert client.get('/api/v1/health').json() == {'status': 'ok', 'mode': 'mock'}
    assert client.get('/api/v1/health').status_code == 200
    assert client.get('/docs').status_code == 200
    assert client.get('/openapi.json').status_code == 200

def test_transactions(client):
    fixture = json.loads((ROOT / 'contracts/sample-transaction.json').read_text())
    fixture['evidence_count'] = 0
    response = client.get('/api/v1/transactions')
    assert response.status_code == 200
    assert response.json() == [fixture]
    detail = client.get('/api/v1/transactions/txn_demo_001')
    assert detail.status_code == 200
    assert detail.json() == fixture
    assert Transaction.model_validate(detail.json()).amount == '150.00'

@pytest.mark.parametrize('suffix,method', [('', 'GET'), ('/analyze', 'POST'), ('/demo-analysis', 'GET')])
def test_unknown_transaction(client, suffix, method):
    response = client.request(method, '/api/v1/transactions/unknown' + suffix,
                              **({'json': {}} if method == 'POST' else {}))
    assert_error(response, 'TRANSACTION_NOT_FOUND')

def test_job_lifecycle(client):
    response = client.post('/api/v1/transactions/txn_demo_001/analyze', json={})
    assert response.status_code == 202
    job = Analysis.model_validate(response.json())
    UUID(job.analysis_id.removeprefix('analysis_'))
    assert job.status == 'queued'
    assert job.findings == [] and job.draft_response is None
    assert job.merchant_approval_required is True
    for _ in range(2):
        retrieved = client.get('/api/v1/analysis/' + job.analysis_id)
        assert retrieved.status_code == 200
        assert retrieved.json()['analysis_id'] == job.analysis_id
        assert retrieved.json()['status'] == 'completed'
    other = client.post('/api/v1/transactions/txn_demo_001/analyze', json={})
    assert other.json()['analysis_id'] != job.analysis_id
    with TestClient(create_app()) as fresh:
        assert_error(fresh.get('/api/v1/analysis/' + job.analysis_id), 'ANALYSIS_NOT_FOUND')

def test_unknown_analysis(client):
    assert_error(client.get('/api/v1/analysis/unknown'), 'ANALYSIS_NOT_FOUND')

def test_demo(client):
    fixture = json.loads((ROOT / 'contracts/sample-analysis.json').read_text())
    response = client.get('/api/v1/transactions/txn_demo_001/demo-analysis')
    assert response.status_code == 200
    assert response.json() == fixture
    assert Analysis.model_validate(response.json()).status == 'completed'
    assert_error(client.get('/api/v1/analysis/analysis_demo_001'), 'ANALYSIS_NOT_FOUND')

@pytest.mark.parametrize('body', [{'unexpected': True}, [], 'bad', None])
def test_invalid_body(client, body):
    assert_error(client.post('/api/v1/transactions/txn_demo_001/analyze', json=body), 'VALIDATION_ERROR', 422)

def test_malformed_json_and_path(client):
    assert_error(client.post('/api/v1/transactions/txn_demo_001/analyze', content='{', headers={'Content-Type': 'application/json'}), 'VALIDATION_ERROR', 422)
    assert_error(client.get('/api/v1/analysis/invalid.id'), 'VALIDATION_ERROR', 422)

def test_http_errors(client):
    assert_error(client.get('/missing'), 'HTTP_ERROR')
    assert_error(client.delete('/api/v1/health'), 'HTTP_ERROR', 405)

def test_unexpected_error():
    app = create_app()
    @app.get('/broken')
    def broken():
        raise RuntimeError('sensitive internals')
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get('/broken')
        assert_error(response, 'INTERNAL_ERROR', 500)
        assert 'sensitive' not in response.text

def test_cors(client):
    for origin in ('http://localhost:8501', 'http://127.0.0.1:8501'):
        response = client.options('/api/v1/transactions', headers={'Origin': origin, 'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'Content-Type'})
        assert response.status_code == 200
        assert response.headers['access-control-allow-origin'] == origin
    response = client.get('/api/v1/health', headers={'Origin': 'https://untrusted.example'})
    assert 'access-control-allow-origin' not in response.headers

def test_openapi_matches_runtime(client):
    spec = yaml.safe_load((ROOT / 'contracts/openapi.yaml').read_text())
    validate(spec)
    assert spec == client.get('/openapi.json').json()
    for path in spec['paths'].values():
        for operation in path.values():
            assert operation['responses']['422']['content']['application/json']['schema']['$ref'].endswith('/ErrorResponse')
