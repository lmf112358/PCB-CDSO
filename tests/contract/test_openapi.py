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


def _load_committed_openapi() -> dict:
    contract_path = ROOT / "contracts" / "openapi" / "openapi.json"
    assert contract_path.is_file(), "missing generated OpenAPI contract"
    return json.loads(contract_path.read_text(encoding="utf-8"))


def _generated_openapi() -> dict:
    return create_app(db_probe=lambda: True, redis_probe=lambda: True).openapi()


class OpenApiContractTest(unittest.TestCase):
    def test_committed_openapi_covers_application_paths(self) -> None:
        """FastAPI application paths must be a subset of the committed contract.

        契约先行模型:openapi.json 允许包含尚未实现的 PLANNED 路径(M1+),
        但 FastAPI 已实现的路径必须全部被 openapi.json 覆盖,防止实现漂移。
        这取代了 M0 阶段的"逐字节相等"断言(AGENTS.md 第 4 条契约先行)。
        """
        committed = _load_committed_openapi()
        generated = _generated_openapi()
        committed_paths = set(committed.get("paths", {}).keys())
        generated_paths = set(generated.get("paths", {}).keys())
        missing = generated_paths - committed_paths
        self.assertFalse(
            missing,
            f"application exposes paths absent from committed OpenAPI: {sorted(missing)}",
        )

    def test_committed_openapi_components_cover_application_schemas(self) -> None:
        """已实现的 FastAPI schema 必须被 committed OpenAPI 覆盖。"""
        committed = _load_committed_openapi()
        generated = _generated_openapi()
        committed_schemas = set(committed.get("components", {}).get("schemas", {}).keys())
        generated_schemas = set(generated.get("components", {}).get("schemas", {}).keys())
        missing = generated_schemas - committed_schemas
        self.assertFalse(
            missing,
            f"application schemas absent from committed OpenAPI: {sorted(missing)}",
        )

    def test_health_operations_and_error_response_are_stable(self) -> None:
        schema = _generated_openapi()
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

    def test_committed_openapi_declares_m1_planned_paths(self) -> None:
        """M1 计划路径必须在契约中声明(契约先行,允许尚未实现)。"""
        committed = _load_committed_openapi()
        paths = committed.get("paths", {})
        required_m1_paths = {
            "/auth/login",
            "/auth/refresh",
            "/auth/logout",
            "/auth/me",
            "/projects",
            "/tasks",
            "/tasks/{task_id}",
        }
        missing = required_m1_paths - set(paths.keys())
        self.assertFalse(
            missing,
            f"committed OpenAPI missing M1 planned paths: {sorted(missing)}",
        )

    def test_committed_openapi_declares_m1_schemas(self) -> None:
        """M1 计划 schema 必须在契约中声明。"""
        committed = _load_committed_openapi()
        schemas = committed.get("components", {}).get("schemas", {})
        required_m1_schemas = {
            "ActorContext",
            "AuthSession",
            "User",
            "ProjectSummary",
            "CreateProjectRequest",
            "CreateProjectResponse",
        }
        missing = required_m1_schemas - set(schemas.keys())
        self.assertFalse(
            missing,
            f"committed OpenAPI missing M1 schemas: {sorted(missing)}",
        )

    def test_create_project_request_excludes_actor_id(self) -> None:
        """CreateProjectRequest 不得接受 actorId;认证身份由 Authorization 注入。

        参考 docs/specs/m1/project-weather-dispatch.md 第 45 行:
        '请求体中的同名值不得覆盖认证身份'。
        """
        committed = _load_committed_openapi()
        schemas = committed.get("components", {}).get("schemas", {})
        self.assertIn("CreateProjectRequest", schemas)
        props = schemas["CreateProjectRequest"].get("properties", {})
        self.assertNotIn(
            "actorId",
            props,
            "CreateProjectRequest must not accept actorId; auth identity comes from Authorization header",
        )
        required = schemas["CreateProjectRequest"].get("required", [])
        self.assertNotIn("actorId", required)

    def test_create_project_uses_idempotency_key_header(self) -> None:
        """CreateProject 通过 Idempotency-Key header 接收幂等键,不进 body。

        参考 docs/architecture/m1-contract-expansion-design.md 第 6 节已决策项。
        canonical hash 只含 6 个业务字段,name/templateVersionId/countryCode/
        adminArea/city/timezone。
        """
        committed = _load_committed_openapi()
        post_op = committed["paths"]["/projects"]["post"]
        params = post_op.get("parameters", [])
        header_names = {
            p.get("name")
            for p in params
            if p.get("in") == "header"
        }
        self.assertIn("Idempotency-Key", header_names)
        body_ref = post_op.get("requestBody", {}).get("content", {}).get(
            "application/json", {}
        ).get("schema", {})
        body_schema = body_ref.get("$ref") if "$ref" in body_ref else body_ref
        if isinstance(body_schema, dict):
            body_props = body_schema.get("properties", {})
        else:
            # $ref form; ensure body schema (CreateProjectRequest) excludes idempotencyKey
            body_props = committed["components"]["schemas"][
                "CreateProjectRequest"
            ].get("properties", {})
        self.assertNotIn(
            "idempotencyKey",
            body_props,
            "idempotencyKey must be a header, not a body field",
        )


if __name__ == "__main__":
    unittest.main()
