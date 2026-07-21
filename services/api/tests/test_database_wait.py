from __future__ import annotations

from pcb_cdso.db.wait import wait_until_ready


def test_wait_retries_transient_database_startup() -> None:
    outcomes = iter([False, False, True])
    sleeps: list[float] = []

    assert wait_until_ready(lambda: next(outcomes), attempts=3, delay=0.25, sleep=sleeps.append)
    assert sleeps == [0.25, 0.25]


def test_wait_returns_failure_after_budget_is_exhausted() -> None:
    sleeps: list[float] = []

    assert not wait_until_ready(lambda: False, attempts=2, delay=0.1, sleep=sleeps.append)
    assert sleeps == [0.1]
