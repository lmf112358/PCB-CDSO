from __future__ import annotations

from typing import TypeGuard
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


def valid_request_id(value: str | None) -> TypeGuard[str]:
    return value is not None and 16 <= len(value) <= 64 and value.isascii()


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        supplied = request.headers.get("X-Request-ID")
        request_id = supplied if valid_request_id(supplied) else uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
