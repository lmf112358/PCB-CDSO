from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI

from pcb_cdso.core.config import Settings, get_settings
from pcb_cdso.http.errors import ApiError, api_error_handler, unexpected_error_handler
from pcb_cdso.http.health import build_health_router
from pcb_cdso.http.request_id import RequestIdMiddleware

Probe = Callable[[], bool]


def create_app(
    *,
    settings: Settings | None = None,
    db_probe: Probe | None = None,
    redis_probe: Probe | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    app = FastAPI(
        title="PCB-CDSO API",
        version=resolved_settings.version,
        openapi_version="3.1.0",
    )
    app.add_middleware(RequestIdMiddleware)
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unexpected_error_handler)
    app.include_router(
        build_health_router(
            resolved_settings,
            db_probe or (lambda: False),
            redis_probe or (lambda: False),
        )
    )
    return app


app = create_app()
