"""Exception handlers: every error leaves the API in the same JSON shape.

    { "error": "...", "detail": ..., "request_id": "..." }
"""

import logging

import duckdb
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("epiflood")


def _body(request: Request, error: str, detail) -> dict:
    return {"error": error, "detail": detail, "request_id": getattr(request.state, "request_id", None)}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        return JSONResponse(_body(request, "http_error", exc.detail), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # jsonable_encoder: pydantic error contexts can hold objects (e.g. exceptions) that plain JSON cannot
        return JSONResponse(_body(request, "validation_error", jsonable_encoder(exc.errors())), status_code=422)

    @app.exception_handler(duckdb.Error)
    async def database_error(request: Request, exc: duckdb.Error):
        # the real message goes to the log with the request id; the client only gets a generic one
        log.error("Database error [%s]: %s", getattr(request.state, "request_id", None), exc)
        return JSONResponse(_body(request, "database_error", "The query could not be completed"), status_code=500)

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception):
        log.exception("Unhandled error [%s]", getattr(request.state, "request_id", None))
        return JSONResponse(_body(request, "internal_error", "Unexpected server error"), status_code=500)
