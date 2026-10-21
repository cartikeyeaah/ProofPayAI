import pytest
from fastapi.testclient import TestClient
from backend.app.main import create_app


def test_production_cannot_fall_back_to_demo(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.delenv('DATABASE_URL', raising=False)
    with pytest.raises(RuntimeError, match='Production requires PostgreSQL'):
        with TestClient(create_app()): pass


def test_production_requires_https_origins(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('FRONTEND_ORIGINS', 'http://localhost:3000')
    with pytest.raises(RuntimeError, match='HTTPS'):
        with TestClient(create_app('postgresql+psycopg://unused')): pass


def test_streamed_request_size_limit():
    with TestClient(create_app()) as client:
        response = client.post('/api/v1/auth/login', content=iter([b'x'*140000, b'y'*140000]), headers={'Content-Type':'application/json'})
        assert response.status_code == 413
        assert response.json()['error']['code'] == 'REQUEST_TOO_LARGE'
