from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


class ErrorEnvelope(BaseModel):
    code: str
    message_key: str
    field_path: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str


class ApiError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message_key: str,
        field_path: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code
        self.message_key = message_key
        self.field_path = field_path
        self.details = details or {}


def error_payload(error: ApiError, request_id: str) -> dict[str, Any]:
    return {
        "code": error.code,
        "message_key": error.message_key,
        "field_path": error.field_path,
        "details": error.details,
        "request_id": request_id,
    }


async def api_error_handler(request: Request, error: ApiError) -> JSONResponse:
    request_id = request.state.request_id
    return JSONResponse(
        status_code=error.status_code,
        content=error_payload(error, request_id),
        headers={"X-Request-ID": request_id},
    )


async def unexpected_error_handler(request: Request, _error: Exception) -> JSONResponse:
    request_id = request.state.request_id
    error = ApiError(
        status_code=500,
        code="INTERNAL_ERROR",
        message_key="errors.internal",
    )
    return JSONResponse(
        status_code=500,
        content=error_payload(error, request_id),
        headers={"X-Request-ID": request_id},
    )
