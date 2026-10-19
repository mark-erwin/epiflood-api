from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

def _body(request, error, detail):
    return {
        "error": error,
        "detail": detail,
        "request_id": getattr(request.state, "request_id", None),
    }

def register_error_handlers(app):
    @app.exception_handler(StarletteHTTPException)
    async def http_err(request: Request, exc):
        return JSONResponse(_body(request, "http_error", exc.detail), exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_err(request: Request, exc):
        return JSONResponse(_body(request, "validation_error", exc.errors()), 422)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc):
        return JSONResponse(
            _body(request, "internal_error", "Unexpected server error"), 500
        )
