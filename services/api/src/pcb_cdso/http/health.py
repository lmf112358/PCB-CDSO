from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Request
from pydantic import BaseModel

from pcb_cdso.core.config import Settings
from pcb_cdso.http.errors import ApiError, ErrorEnvelope

Probe = Callable[[], bool]


class LiveHealth(BaseModel):
    status: str
    service: str
    version: str
    request_id: str


class ReadyHealth(BaseModel):
    status: str
    dependencies: dict[str, str]
    request_id: str


def dependency_status(probe: Probe) -> str:
    try:
        return "ready" if probe() else "unavailable"
    except Exception:
        return "unavailable"


def build_health_router(settings: Settings, db_probe: Probe, redis_probe: Probe) -> APIRouter:
    router = APIRouter(prefix="/health", tags=["health"])

    @router.get("/live", operation_id="health_live", response_model=LiveHealth)
    def live(request: Request) -> dict[str, str]:
        return {
            "status": "alive",
            "service": settings.service_name,
            "version": settings.version,
            "request_id": request.state.request_id,
        }

    @router.get(
        "/ready",
        operation_id="health_ready",
        response_model=ReadyHealth,
        responses={
            503: {"model": ErrorEnvelope, "description": "A required dependency is unavailable"}
        },
    )
    def ready(request: Request) -> dict[str, object]:
        dependencies = {
            "database": dependency_status(db_probe),
            "redis": dependency_status(redis_probe),
        }
        if "unavailable" in dependencies.values():
            raise ApiError(
                status_code=503,
                code="DEPENDENCY_UNAVAILABLE",
                message_key="errors.dependency_unavailable",
                details=dependencies,
            )
        return {
            "status": "ready",
            "dependencies": dependencies,
            "request_id": request.state.request_id,
        }

    return router
