from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI
from redis import Redis

from pcb_cdso.core.config import Settings, get_settings
from pcb_cdso.db.session import build_engine, build_session_factory, probe_database
from sqlalchemy.orm import Session, sessionmaker
from pcb_cdso.db.session import build_session_factory
from pcb_cdso.domain.projects import ProjectService
from pcb_cdso.http.auth import AuthService, build_auth_router, build_get_actor
from pcb_cdso.http.errors import ApiError, api_error_handler, unexpected_error_handler
from pcb_cdso.http.projects import build_projects_router
from pcb_cdso.http.tasks_m1 import build_tasks_m1_router
from pcb_cdso.http.health import build_health_router
from pcb_cdso.http.request_id import RequestIdMiddleware
from pcb_cdso.http.tasks import (
    IdempotencyStore,
    RedisIdempotencyStore,
    TaskDispatcher,
    build_task_router,
)
from pcb_cdso.tasks.smoke import smoke

Probe = Callable[[], bool]


def dispatch_smoke(task_id: str, request_id: str) -> None:
    smoke.apply_async(args=[request_id], task_id=task_id)


def create_app(
    *,
    settings: Settings | None = None,
    db_probe: Probe | None = None,
    redis_probe: Probe | None = None,
    idempotency_store: IdempotencyStore | None = None,
    task_dispatcher: TaskDispatcher | None = None,
    auth_service: AuthService | None = None,
    project_service: ProjectService | None = None,
    tasks_session_factory: sessionmaker[Session] | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    engine = build_engine(resolved_settings)
    redis_client = Redis.from_url(resolved_settings.redis_url)
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
            db_probe or (lambda: probe_database(engine)),
            redis_probe or (lambda: bool(redis_client.ping())),
        )
    )
    # Auth router is always enabled (ADR-0002). In tests, an in-memory
    # session_factory-backed AuthService can be injected; in production it
    # binds to the real MySQL session factory built from the engine.
    resolved_auth_service = auth_service or AuthService(
        build_session_factory(engine)
    )
    app.include_router(
        build_auth_router(
            resolved_auth_service,
            build_get_actor(resolved_auth_service),
        )
    )
    resolved_project_service = project_service or ProjectService(
        build_session_factory(engine)
    )
    app.include_router(
        build_projects_router(
            resolved_project_service,
            build_get_actor(resolved_auth_service),
        )
    )
    app.include_router(
        build_tasks_m1_router(
            tasks_session_factory or build_session_factory(engine),
            build_get_actor(resolved_auth_service),
        )
    )
    if resolved_settings.environment != "production":
        resolved_store = idempotency_store or RedisIdempotencyStore(
            redis_client
        )
        app.include_router(build_task_router(resolved_store, task_dispatcher or dispatch_smoke))
    return app


app = create_app()
