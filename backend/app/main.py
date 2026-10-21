from uuid import uuid4
import os
from threading import RLock
from backend.db.repository import Repository
from .auth import router as auth_router, authorize, hash_password
from .workspace import router as workspace_router
from .limits import BodyLimitMiddleware
from .ocr import configured_pipeline
from .integrations import router as integrations_router
from starlette.concurrency import run_in_threadpool
from contextlib import asynccontextmanager
from .evidence import router as evidence_router
from .worker import run_pipeline
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException
from .errors import APIError, api_error_handler, validation_error_handler, http_error_handler, unexpected_error_handler
from .mock_data import MockStore
from .routes import router
from .schemas import ErrorResponse

def create_app(database_url=None, storage_root=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        if app.state.secure_cookies:
            if not (database_url or os.getenv('DATABASE_URL')):
                raise RuntimeError('Production requires PostgreSQL; demo mode is local development only.')
            if not app.state.origins or any(not origin.startswith('https://') for origin in app.state.origins):
                raise RuntimeError('Production requires explicit HTTPS FRONTEND_ORIGINS.')
        if database_url or os.getenv('DATABASE_URL'):
            app.state.repository = Repository(database_url or os.environ['DATABASE_URL'], storage_root or os.getenv('STORAGE_ROOT', '.local/private-evidence'))
        try:
            yield
        finally:
            app.state.store.storage.cleanup()
            if app.state.repository: app.state.repository.close()

    app = FastAPI(title="ProofPay AI Synthetic Integration API", version="0.3.0", lifespan=lifespan,
                  description="Synthetic transactions with the deterministic AI engine. Demo or PostgreSQL persistence, cookie sessions, optional local OCR.")
    app.state.store = MockStore()
    app.state.pipeline_runner = configured_pipeline
    app.state.pipeline_timeout = 30.0
    app.state.repository = None
    app.state.paypal_clients = {}
    app.state.secure_cookies = os.getenv('APP_ENV', 'development') == 'production'
    app.state.rate_lock = RLock()
    app.state.rate_attempts = {}
    app.state.dummy_password_hash = hash_password('unusable-dummy-password')
    app.state.origins = [s.strip() for s in os.getenv('FRONTEND_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',') if s.strip()]
    app.add_middleware(CORSMiddleware,
        allow_origins=app.state.origins + ([] if app.state.secure_cookies else ["http://localhost:8501", "http://127.0.0.1:8501"]),
        allow_credentials=True, allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Content-Type", "X-CSRF-Token", "Idempotency-Key"], expose_headers=["X-Request-ID"])

    app.add_middleware(BodyLimitMiddleware)

    @app.middleware("http")
    async def request_id(request: Request, call_next):
        request.state.request_id = f"req_{uuid4()}"
        try:
            await run_in_threadpool(authorize, request)
        except APIError as exc:
            from .errors import error_response
            return error_response(request, exc.status_code, exc.code, exc.message)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
    responses = {
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        429: {"model": ErrorResponse, "description": "Rate limited"},
        503: {"model": ErrorResponse, "description": "Unavailable"},
        404: {"model": ErrorResponse, "description": "Resource not found"},
        405: {"model": ErrorResponse, "description": "Method not allowed"},
        422: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Unexpected server error"},
        409: {"model": ErrorResponse, "description": "Active analysis or document limit"},
        413: {"model": ErrorResponse, "description": "File too large or empty"},
        415: {"model": ErrorResponse, "description": "Unsupported media type"},
    }
    app.include_router(router, responses=responses)
    app.include_router(evidence_router, responses=responses)
    app.include_router(auth_router, responses=responses)
    app.include_router(workspace_router, responses=responses)
    app.include_router(integrations_router, responses=responses)
    return app

app = create_app()
