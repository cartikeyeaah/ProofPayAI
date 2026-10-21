from uuid import uuid4
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException
from .errors import APIError, api_error_handler, validation_error_handler, http_error_handler, unexpected_error_handler
from .mock_data import MockStore
from .routes import router
from .schemas import ErrorResponse

def create_app() -> FastAPI:
    app = FastAPI(title="ProofPay AI Day 1 Mock API", version="0.1.0",
                  description="Synthetic data only. Jobs remain queued. No persistence, authentication, or AI pipeline.")
    app.state.store = MockStore()
    app.add_middleware(CORSMiddleware,
        allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
        allow_credentials=False, allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"], expose_headers=["X-Request-ID"])

    @app.middleware("http")
    async def request_id(request: Request, call_next):
        request.state.request_id = f"req_{uuid4()}"
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
    app.include_router(router, responses={
        404: {"model": ErrorResponse, "description": "Resource not found"},
        405: {"model": ErrorResponse, "description": "Method not allowed"},
        422: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Unexpected server error"},
    })
    return app

app = create_app()
