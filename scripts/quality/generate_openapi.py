#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
API_SRC = ROOT / "services" / "api" / "src"
sys.path.insert(0, str(API_SRC))

from pcb_cdso.main import create_app  # noqa: E402


def main() -> int:
    target = ROOT / "contracts" / "openapi" / "openapi.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    schema = create_app(db_probe=lambda: True, redis_probe=lambda: True).openapi()
    target.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(target.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
