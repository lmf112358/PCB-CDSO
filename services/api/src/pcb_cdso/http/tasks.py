from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol
from uuid import uuid4

from fastapi import APIRouter, Header, Request, status
from pydantic import BaseModel
from redis import Redis


class IdempotencyStore(Protocol):
    def reserve(self, scope: str, key: str, proposed_task_id: str) -> str: ...


TaskDispatcher = Callable[[str, str], None]


class TaskEnvelope(BaseModel):
    task_id: str
    status: str
    progress: int
    stage: str
    processed: int
    total: int
    error: dict[str, Any] | None
    retryable: bool


class RedisIdempotencyStore:
    def __init__(self, client: Redis, *, ttl_seconds: int = 86_400) -> None:
        self.client = client
        self.ttl_seconds = ttl_seconds

    def reserve(self, scope: str, key: str, proposed_task_id: str) -> str:
        redis_key = f"pcb-cdso:idempotency:{scope}:{key}"
        reserved = self.client.set(redis_key, proposed_task_id, nx=True, ex=self.ttl_seconds)
        if reserved:
            return proposed_task_id
        existing = self.client.get(redis_key)
        if existing is None:
            raise RuntimeError("idempotency reservation disappeared")
        return existing.decode() if isinstance(existing, bytes) else str(existing)


def build_task_router(
    idempotency_store: IdempotencyStore,
    task_dispatcher: TaskDispatcher,
) -> APIRouter:
    router = APIRouter(prefix="/internal/tasks", tags=["internal"])

    @router.post(
        "/smoke",
        operation_id="task_smoke_create",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=TaskEnvelope,
    )
    def create_smoke_task(
        request: Request,
        idempotency_key: str = Header(min_length=8, max_length=128, alias="Idempotency-Key"),
    ) -> TaskEnvelope:
        proposed_task_id = str(uuid4())
        task_id = idempotency_store.reserve("internal.smoke", idempotency_key, proposed_task_id)
        if task_id == proposed_task_id:
            task_dispatcher(task_id, request.state.request_id)
        return TaskEnvelope(
            task_id=task_id,
            status="QUEUED",
            progress=0,
            stage="queued",
            processed=0,
            total=1,
            error=None,
            retryable=False,
        )

    return router
