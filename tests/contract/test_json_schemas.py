from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "contracts" / "schemas"

EXPECTED_REQUIRED = {
    "error.schema.json": {
        "code",
        "message_key",
        "field_path",
        "details",
        "request_id",
    },
    "task.schema.json": {
        "task_id",
        "status",
        "progress",
        "stage",
        "processed",
        "total",
        "error",
        "retryable",
    },
    "revision.schema.json": {"expectedInputRevision"},
    "idempotency.schema.json": {"idempotencyKey", "scope"},
}


class ContractSchemaTest(unittest.TestCase):
    def test_all_required_contract_schemas_are_well_formed(self) -> None:
        for name, required_fields in EXPECTED_REQUIRED.items():
            with self.subTest(schema=name):
                path = SCHEMA_DIR / name
                self.assertTrue(
                    path.is_file(), f"missing schema: {path.relative_to(ROOT)}"
                )
                schema = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(
                    "https://json-schema.org/draft/2020-12/schema", schema["$schema"]
                )
                self.assertTrue(
                    schema["$id"].startswith("https://pcb-cdso.local/schemas/")
                )
                self.assertEqual("object", schema["type"])
                self.assertFalse(schema["additionalProperties"])
                self.assertEqual(required_fields, set(schema["required"]))
                self.assertTrue(required_fields.issubset(schema["properties"]))

    def test_task_status_is_closed_and_progress_is_bounded(self) -> None:
        schema = json.loads(
            (SCHEMA_DIR / "task.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            ["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"],
            schema["properties"]["status"]["enum"],
        )
        self.assertEqual(0, schema["properties"]["progress"]["minimum"])
        self.assertEqual(100, schema["properties"]["progress"]["maximum"])


if __name__ == "__main__":
    unittest.main()
