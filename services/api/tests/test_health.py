from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from pcb_cdso.main import create_app

Probe = Callable[[], bool]


class CountingProbe:
    def __init__(self, result: bool) -> None:
        self.result = result
        self.calls = 0

    def __call__(self) -> bool:
        self.calls += 1
        return self.result


def make_client(db_probe: Probe, redis_probe: Probe) -> TestClient:
    return TestClient(create_app(db_probe=db_probe, redis_probe=redis_probe))


def test_live_does_not_touch_dependencies() -> None:
    db_probe = CountingProbe(False)
    redis_probe = CountingProbe(False)
    client = make_client(db_probe, redis_probe)

    response = client.get("/health/live", headers={"X-Request-ID": "req-live-00000001"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-live-00000001"
    assert response.json() == {
        "status": "alive",
        "service": "pcb-cdso-api",
        "version": "0.6.0",
        "request_id": "req-live-00000001",
    }
    assert db_probe.calls == 0
    assert redis_probe.calls == 0


def test_ready_reports_each_dependency() -> None:
    client = make_client(CountingProbe(True), CountingProbe(True))

    response = client.get("/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["dependencies"] == {"database": "ready", "redis": "ready"}
    assert body["request_id"] == response.headers["X-Request-ID"]
    assert 16 <= len(body["request_id"]) <= 64


def test_ready_returns_stable_error_when_redis_is_down() -> None:
    client = make_client(CountingProbe(True), CountingProbe(False))

    response = client.get("/health/ready", headers={"X-Request-ID": "req-ready-000001"})

    assert response.status_code == 503
    assert response.headers["X-Request-ID"] == "req-ready-000001"
    assert response.json() == {
        "code": "DEPENDENCY_UNAVAILABLE",
        "message_key": "errors.dependency_unavailable",
        "field_path": None,
        "details": {"database": "ready", "redis": "unavailable"},
        "request_id": "req-ready-000001",
    }


def test_unhandled_exception_uses_stable_error_and_request_id() -> None:
    def broken_probe() -> bool:
        raise RuntimeError("database password must never be returned")

    client = make_client(broken_probe, CountingProbe(True))

    response = client.get(
        "/health/ready",
        headers={"X-Request-ID": "req-error-000001"},
    )

    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "DEPENDENCY_UNAVAILABLE"
    assert body["request_id"] == "req-error-000001"
    assert "password" not in response.text.lower()
