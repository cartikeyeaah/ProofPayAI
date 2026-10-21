from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

class APIError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code, self.code, self.message = status_code, code, message

def error_response(request: Request, status_code: int, code: str, message: str):
    return JSONResponse(status_code=status_code, content={"error": {
        "code": code, "message": message, "request_id": request.state.request_id}},
        headers={"X-Request-ID": request.state.request_id})

async def api_error_handler(request: Request, exc: APIError):
    return error_response(request, exc.status_code, exc.code, exc.message)

async def validation_error_handler(request: Request, exc: RequestValidationError):
    return error_response(request, 422, "VALIDATION_ERROR", "Request validation failed. Check path parameters and JSON body against the API contract.")

async def http_error_handler(request: Request, exc: HTTPException):
    return error_response(request, exc.status_code, "HTTP_ERROR", str(exc.detail))

async def unexpected_error_handler(request: Request, exc: Exception):
    return error_response(request, 500, "INTERNAL_ERROR", "An unexpected server error occurred.")
