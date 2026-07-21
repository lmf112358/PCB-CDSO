from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "contracts" / "schemas"

# M0 已冻结的 schema 与其 required 字段。
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
    # idempotency.schema.json 的 required 在 M1 扩展后变更,见 M1_EXPECTED_REQUIRED。
}

# M1 新增/扩展的 schema 与其 required 字段。
M1_EXPECTED_REQUIRED = {
    "actor-context.schema.json": {"actor_id", "role", "locale", "theme"},
    "auth-session.schema.json": {
        "access_token",
        "refresh_token",
        "expires_in",
        "user",
        "locale",
        "theme",
    },
    "user.schema.json": {"id", "email", "role", "is_active"},
    "project.schema.json": {
        "id",
        "name",
        "owner_id",
        "template_version_id",
        "country_code",
        "admin_area",
        "city",
        "timezone",
        "status",
        "created_at",
    },
    "idempotency.schema.json": {
        "idempotencyKey",
        "scope",
        "actor_id",
        "canonical_request_hash",
        "status",
    },
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

    def test_m1_new_schemas_are_well_formed(self) -> None:
        for name, required_fields in M1_EXPECTED_REQUIRED.items():
            with self.subTest(schema=name):
                path = SCHEMA_DIR / name
                self.assertTrue(
                    path.is_file(), f"missing M1 schema: {path.relative_to(ROOT)}"
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

    def test_task_status_includes_m1_states_and_progress_is_bounded(self) -> None:
        schema = json.loads(
            (SCHEMA_DIR / "task.schema.json").read_text(encoding="utf-8")
        )
        # M1 Feature Spec 第 71-80 行要求的状态枚举。
        self.assertEqual(
            [
                "DISPATCH_PENDING",
                "QUEUED",
                "RUNNING",
                "SUCCEEDED",
                "FAILED",
                "CANCELLED",
                "STALE",
            ],
            schema["properties"]["status"]["enum"],
        )
        self.assertEqual(0, schema["properties"]["progress"]["minimum"])
        self.assertEqual(100, schema["properties"]["progress"]["maximum"])

    def test_error_code_enum_includes_m1_stable_codes(self) -> None:
        """M1 Feature Spec 第 86-99 行要求的稳定错误码必须在 enum 中。"""
        schema = json.loads(
            (SCHEMA_DIR / "error.schema.json").read_text(encoding="utf-8")
        )
        codes = schema["properties"]["code"]["enum"]
        required_m1_codes = {
            "UNAUTHENTICATED",
            "FORBIDDEN",
            "NOT_FOUND",
            "VALIDATION_FAILED",
            "IDEMPOTENCY_CONFLICT",
            "REVISION_CONFLICT",
            "TRANSACTION_FAILED",
            "COMMIT_OUTCOME_UNKNOWN",
            "DEPENDENCY_UNAVAILABLE",
            "INTERNAL_ERROR",
        }
        self.assertEqual(
            required_m1_codes,
            set(codes),
            f"error.schema.json code enum must equal M1 stable set; got {sorted(codes)}",
        )

    def test_idempotency_status_enum_is_closed(self) -> None:
        schema = json.loads(
            (SCHEMA_DIR / "idempotency.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            ["IN_PROGRESS", "SUCCEEDED"],
            schema["properties"]["status"]["enum"],
        )
        # canonical_request_hash 必须是 sha256 hex。
        pattern = schema["properties"]["canonical_request_hash"].get("pattern")
        self.assertIsNotNone(pattern)


if __name__ == "__main__":
    unittest.main()
