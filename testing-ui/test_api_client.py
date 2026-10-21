import pytest
import requests
from api_client import APIClient, valid_url

class Response:
    status_code = 500
    headers = {'X-Request-ID': 'req_12345678-1234-1234-1234-123456789abc'}
    def json(self):
        return {'error': {'code': 'INTERNAL_ERROR', 'message': 'secret-token-123'}, 'password': 'secret-token-123'}

def test_sanitized_error(monkeypatch):
    monkeypatch.setattr(requests.Session, 'request', lambda *a, **k: Response())
    result = APIClient('http://localhost:8000').call('GET', '/api/v1/health', 'Health')
    assert result.status == 500 and result.code == 'INTERNAL_ERROR'
    assert result.elapsed_ms >= 0 and result.request_id
    assert 'secret-token-123' not in repr(result)

@pytest.mark.parametrize('error', [requests.Timeout('secret-token-123'), requests.ConnectionError('secret-token-123')])
def test_transport_errors(monkeypatch, error):
    def fail(*a, **kw):
        raise error
    monkeypatch.setattr(requests.Session, 'request', fail)
    result = APIClient('http://localhost:8000').call('GET', '/api/v1/health', 'Health')
    assert result.error and result.data is None and result.status is None
    assert 'secret-token-123' not in repr(result)

@pytest.mark.parametrize('payload', [None, [], {'status': 'ok'}, {'status': 'ok', 'mode': 'mock', 'token': 'secret-token-123'}])
def test_invalid_success_body(monkeypatch, payload):
    response = Response()
    response.status_code = 200
    response.json = lambda: payload
    monkeypatch.setattr(requests.Session, 'request', lambda *a, **k: response)
    result = APIClient('http://localhost:8000').call('GET', '/api/v1/health', 'Health')
    assert result.data is None and 'contract' in result.error
    assert 'secret-token-123' not in repr(result)

def test_non_json_and_redirect(monkeypatch):
    response = Response()
    def bad_json():
        raise ValueError('secret-token-123')
    response.json = bad_json
    def request(session, *a, **kw):
        assert kw['allow_redirects'] is False
        assert session.trust_env is False
        return response
    monkeypatch.setattr(requests.Session, 'request', request)
    client = APIClient('http://localhost:8000')
    assert 'non-JSON' in client.call('GET', '/api/v1/health', 'Health').error
    response.status_code = 302
    response.json = lambda: {'location': 'secret-token-123'}
    result = client.call('GET', '/api/v1/health', 'Health')
    assert result.error and result.data is None and 'secret-token-123' not in repr(result)

@pytest.mark.parametrize('url', ['http://user:secret@localhost', 'http://localhost?token=secret', 'file:///tmp/foo', 'http://localhost:bad', 'http://localhost#secret'])
def test_unsafe_url_not_requested(monkeypatch, url):
    def fail(*a, **kw):
        pytest.fail('Unsafe URL must not be requested')
    monkeypatch.setattr(requests.Session, 'request', fail)
    assert not valid_url(url)
    assert APIClient(url).call('GET', '/api/v1/health', 'Health').error
