from __future__ import annotations

from fastapi.testclient import TestClient

from pcb_cdso.main import create_app
from pcb_cdso.tasks.smoke import smoke


class MemoryIdempotencyStore:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def reserve(self, scope: str, key: str, proposed_task_id: str) -> str:
        compound_key = f"{scope}:{key}"
        return self.values.setdefault(compound_key, proposed_task_id)


class RecordingDispatcher:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def __call__(self, task_id: str, request_id: str) -> None:
        self.calls.append((task_id, request_id))


def test_smoke_task_returns_request_correlation() -> None:
    result = smoke.apply(args=["req-task-000001"])

    assert result.successful()
    assert result.result == {
        "status": "ok",
        "request_id": "req-task-000001",
    }


def test_duplicate_idempotency_key_dispatches_only_once() -> None:
    store = MemoryIdempotencyStore()
    dispatcher = RecordingDispatcher()
    client = TestClient(
        create_app(
            db_probe=lambda: True,
            redis_probe=lambda: True,
            idempotency_store=store,
            task_dispatcher=dispatcher,
        )
    )
    headers = {
        "Idempotency-Key": "smoke-key-0001",
        "X-Request-ID": "req-dispatch-0001",
    }

    first = client.post("/internal/tasks/smoke", headers=headers)
    second = client.post("/internal/tasks/smoke", headers=headers)

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json() == second.json()
    assert first.json()["status"] == "QUEUED"
    assert first.json()["progress"] == 0
    assert len(dispatcher.calls) == 1
    assert dispatcher.calls[0] == (first.json()["task_id"], "req-dispatch-0001")


def test_smoke_endpoint_requires_idempotency_key() -> None:
    client = TestClient(
        create_app(
            db_probe=lambda: True,
            redis_probe=lambda: True,
            idempotency_store=MemoryIdempotencyStore(),
            task_dispatcher=RecordingDispatcher(),
        )
    )

    response = client.post("/internal/tasks/smoke")

    assert response.status_code == 422
