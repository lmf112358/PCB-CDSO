from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
API_SRC = ROOT / "services" / "api" / "src"
sys.path.insert(0, os.fspath(API_SRC))

from pcb_cdso.main import create_app  # noqa: E402


class OpenApiContractTest(unittest.TestCase):
    def test_committed_openapi_matches_application(self) -> None:
        contract_path = ROOT / "contracts" / "openapi" / "openapi.json"
        self.assertTrue(contract_path.is_file(), "missing generated OpenAPI contract")
        committed = json.loads(contract_path.read_text(encoding="utf-8"))
        generated = create_app(
            db_probe=lambda: True, redis_probe=lambda: True
        ).openapi()
        self.assertEqual(generated, committed)

    def test_health_operations_and_error_response_are_stable(self) -> None:
        schema = create_app(db_probe=lambda: True, redis_probe=lambda: True).openapi()
        self.assertEqual("3.1.0", schema["openapi"])
        self.assertEqual(
            "health_live", schema["paths"]["/health/live"]["get"]["operationId"]
        )
        ready = schema["paths"]["/health/ready"]["get"]
        self.assertEqual("health_ready", ready["operationId"])
        error_schema = ready["responses"]["503"]["content"]["application/json"][
            "schema"
        ]
        self.assertEqual("#/components/schemas/ErrorEnvelope", error_schema["$ref"])


if __name__ == "__main__":
    unittest.main()
