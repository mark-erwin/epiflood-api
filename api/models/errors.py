"""The one error shape every failure uses (see core/errors.py)."""

from typing import Any

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    error: str                     # http_error | validation_error | database_error | internal_error
    detail: Any                    # a message, or a list of field errors for validation_error
    request_id: str | None = None


# Pass as `responses=ERROR_RESPONSES` so /docs documents the error shape.
ERROR_RESPONSES = {
    404: {"model": ErrorResponse, "description": "Resource not found"},
    422: {"model": ErrorResponse, "description": "Invalid parameters"},
    500: {"model": ErrorResponse, "description": "Server or database error"},
}
