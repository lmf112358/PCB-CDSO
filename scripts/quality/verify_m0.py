from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REQUIRED_SERVICES = {"mysql", "redis", "migrate", "bootstrap-admin", "api", "worker", "web"}
PROBES = {
    "web": "http://localhost:3000/",
    "live": "http://localhost:8000/health/live",
    "ready": "http://localhost:8000/health/ready",
    "openapi": "http://localhost:8000/openapi.json",
}


def compose_config() -> dict[str, Any]:
    result = subprocess.run(
        ["docker", "compose", "config", "--format", "json"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "docker compose config failed")
    return json.loads(result.stdout)


def check_config(config: dict[str, Any]) -> None:
    services = set(config.get("services", {}))
    missing = REQUIRED_SERVICES - services
    if missing:
        raise RuntimeError(f"compose services missing: {', '.join(sorted(missing))}")
    for name in ("api", "worker", "migrate", "bootstrap-admin"):
        if config["services"][name].get("user") == "root":
            raise RuntimeError(f"{name} must not run as root")
    environment = config["services"]["api"].get("environment", {})
    if environment.get("PCB_CDSO_ENVIRONMENT") == "production" and "replace_me" in json.dumps(config):
        raise RuntimeError("placeholder credentials cannot be used in production")


def probe(name: str, url: str) -> None:
    with urllib.request.urlopen(url, timeout=5) as response:
        if response.status != 200:
            raise RuntimeError(f"{name} returned HTTP {response.status}")
        body = response.read()
    if name in {"live", "ready", "openapi"}:
        json.loads(body)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the M0 runtime foundation")
    parser.add_argument("--check-config-only", action="store_true")
    args = parser.parse_args()
    try:
        check_config(compose_config())
        print("PASS compose structure")
        if not args.check_config_only:
            for name, url in PROBES.items():
                probe(name, url)
                print(f"PASS {name}: {url}")
    except (RuntimeError, OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
