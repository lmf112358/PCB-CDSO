from __future__ import annotations

import logging
import time
from collections.abc import Callable

from pcb_cdso.core.config import get_settings
from pcb_cdso.db.session import build_engine, probe_database

LOGGER = logging.getLogger("pcb_cdso.db.wait")
Probe = Callable[[], bool]
Sleeper = Callable[[float], None]


def wait_until_ready(
    probe: Probe,
    *,
    attempts: int = 30,
    delay: float = 2.0,
    sleep: Sleeper = time.sleep,
) -> bool:
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    for attempt in range(1, attempts + 1):
        try:
            if probe():
                return True
        except Exception:  # dependency startup may fail in several driver-specific ways
            LOGGER.info("database not ready", extra={"attempt": attempt, "attempts": attempts})
        if attempt < attempts:
            sleep(delay)
    return False


def main() -> int:
    engine = build_engine(get_settings())
    if wait_until_ready(lambda: probe_database(engine)):
        LOGGER.info("database ready")
        return 0
    LOGGER.error("database did not become ready before timeout")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
