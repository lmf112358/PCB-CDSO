# M1 契约扩展设计草案（OpenAPI / JSON Schema）

| 属性 | 值 |
|---|---|
| 状态 | draft |
| 适用 ADR | ADR-0002（认证与会话）|
| 适用 Feature Spec | `docs/specs/m1/project-weather-dispatch.md` v1.0.0 |
| 关联测试计划 | `docs/testing/plans/M1-test-plan.md` |
| 用途 | 为 Contract Agent 任务包提供冻结前的设计意图；不直接修改已冻结的 `contracts/`。Contract Agent 必须通过“先改契约测试、再改契约、再跑测试”的 TDD 顺序落地 |

本文档**不是契约**。已冻结的契约仍是 `contracts/openapi/openapi.json` 与 `contracts/schemas/*.schema.json`。Contract Agent 落地时以本文档为设计输入，最终机器契约以 PR 合并后的 `contracts/` 为准；二者冲突时以合并后的契约为权威，并按 AGENTS.md 第 2 条回报冲突。

## 1. 现状对齐缺口（Contract Agent 必须先修复）

阅读 `contracts/schemas/error.schema.json` 与 `contracts/schemas/task.schema.json` 后，发现以下与 M1 Feature Spec 不一致，必须在契约 PR 中对齐：

### 1.1 `error.schema.json` 的 `code` enum 缺失

M1 Feature Spec 第 86–99 行要求以下稳定错误码，但现有 enum 仅含 5 个：

| 现有 | M1 要求新增 | 来源行 |
|---|---|---|
| `FORBIDDEN` ✅ | — | — |
| `REVISION_CONFLICT` ✅ | — | — |
| `VALIDATION_FAILED` ✅ | — | — |
| `DEPENDENCY_UNAVAILABLE` ✅ | — | — |
| `INTERNAL_ERROR` ✅ | — | — |
| — | `UNAUTHENTICATED` | 第 88 行（401） |
| — | `NOT_FOUND` | 第 103 行（跨 owner 与随机不存在均不可区分） |
| — | `IDEMPOTENCY_CONFLICT` | 第 91 行（409） |
| — | `TRANSACTION_FAILED` | 第 94 行（503） |
| — | `COMMIT_OUTCOME_UNKNOWN` | 第 95 行（503） |

### 1.2 `task.schema.json` 的 `status` enum 缺失

M1 Feature Spec 第 71–80 行要求 7 个状态，现有 enum 仅 5 个：

| 现有 | M1 要求新增 | 来源行 |
|---|---|---|
| `QUEUED, RUNNING, SUCCEEDED, FAILED, CANCELLED` ✅ | — | — |
| — | `DISPATCH_PENDING` | 第 71 行（Task 初态） |
| — | `STALE` | 第 79 行（revision 过期终态） |

### 1.3 `idempotency.schema.json` 未表达 `canonicalRequestHash` 与 `status`

M1 Feature Spec 第 53–55 行要求幂等记录冻结 `canonicalRequestHash` 与 `status`（`IN_PROGRESS|SUCCEEDED`）。现有 schema 只有 `idempotencyKey` 和 `scope`，不足以作为持久化记录契约。

## 2. OpenAPI 扩展（新增路径）

所有新路径遵循现有 OpenAPI 的风格：组件化 schema、稳定 `code`、`request_id` 全程透传、`TaskEnvelope` 复用。

### 2.1 `POST /auth/login`

```
POST /auth/login
Content-Type: application/json
Body: LoginRequest { email: string<email>, password: string<min 1> }
Responses:
  200: AuthResponse { access_token, refresh_token, expires_in, user: User, locale, theme }
  401: ErrorEnvelope { code: "UNAUTHENTICATED", message_key: "auth.login.invalid_credentials" }
  422: ErrorEnvelope { code: "VALIDATION_FAILED", field_path, message_key }
```

- 登录失败**不得**区分“用户不存在”与“密码错误”，统一 `UNAUTHENTICATED`。
- `password` 字段最小长度仅做格式校验（≥1），哈希参数由服务端控制。
- `expires_in` 为 access token TTL（秒），与 ADR-0002 默认 900 一致。

### 2.2 `POST /auth/refresh`

```
POST /auth/refresh
Body: RefreshRequest { refresh_token: string }
Responses:
  200: AuthResponse（同 login，token 全部轮换；旧 access/refresh 立即失效）
  401: UNAUTHENTICATED（refresh 过期、已撤销或用户停用）
```

### 2.3 `POST /auth/logout`

```
POST /auth/logout
Authorization: Bearer <access_token>
Responses:
  204: （撤销当前 session）
  401: UNAUTHENTICATED
```

### 2.4 `GET /auth/me`

```
GET /auth/me
Authorization: Bearer <access_token>
Responses:
  200: ActorContext { actor_id, role: "ADMIN"|"ENGINEER", locale, theme }
  401: UNAUTHENTICATED
```

`ActorContext` 是所有业务端点注入认证身份的来源。

### 2.5 `POST /projects`（M1 核心）

```
POST /projects
Authorization: Bearer <access_token>
Idempotency-Key: <client key, 1–128 printable ASCII>
Body: CreateProjectRequest {
  name: string<1–120 Unicode, trimmed>,
  templateVersionId: string,
  countryCode: string<ISO 3166-1 alpha-2 upper>,
  adminArea: string<1–120 trimmed>,
  city: string<1–120 trimmed>,
  timezone: string<IANA, server-resolvable>
}
Responses:
  201: CreateProjectResponse {
    project: ProjectSummary,
    inputRevision: 1,
    snapshotIds: string[],
    weatherTaskId: string
  }
  200: 同上 schema（幂等重放）
  401: UNAUTHENTICATED
  403: FORBIDDEN（角色非 ENGINEER/ADMIN）
  404: NOT_FOUND（templateVersionId 不存在或不可见；统一防枚举语义）
  409: IDEMPOTENCY_CONFLICT（同 key 不同 canonical hash）
  422: VALIDATION_FAILED（字段格式、时区、模板未发布）
  503: TRANSACTION_FAILED / COMMIT_OUTCOME_UNKNOWN
```

关键约束（必须在 OpenAPI description 中写明，并由契约测试覆盖）：

- 请求体**不得**接受 `actorId`；若客户端传入，服务端忽略并写入审计。认证身份来自 `Authorization`。
- `Idempotency-Key` 用 HTTP header 而非 body，避免与 canonical hash 计算混淆（canonical payload 只含 6 个业务字段）。
- 响应始终返回 `weatherTaskId`，其状态由 `GET /tasks/{id}` 查询。

### 2.6 `GET /tasks/{taskId}` 与 `GET /tasks`

```
GET /tasks/{taskId}
GET /tasks?projectId=&activeOnly=true
Authorization: Bearer <access_token>
Responses:
  200: TaskEnvelope | TaskList { items: TaskEnvelope[] }
  401: UNAUTHENTICATED
  403: FORBIDDEN（跨 owner 且非 ADMIN）
  404: NOT_FOUND（不可见或随机不存在，不可区分）
```

- `TaskEnvelope` 复用现有 schema，但 `status` enum 必须扩展为含 `DISPATCH_PENDING` 与 `STALE`（见 1.2）。
- M2 的工具卡与任务坞必须消费这里的同一 `weatherTaskId`，是跨里程碑契约边界。

## 3. 新增 JSON Schema 文件

Contract Agent 在 `contracts/schemas/` 新增以下文件，并在 `tests/contract/test_json_schemas.py` 增加用例：

### 3.1 `actor-context.schema.json`

```jsonc
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://pcb-cdso.local/schemas/actor-context.schema.json",
  "title": "PCB-CDSO Actor Context",
  "type": "object",
  "additionalProperties": false,
  "required": ["actor_id", "role", "locale", "theme"],
  "properties": {
    "actor_id": {"type": "string", "minLength": 1, "maxLength": 36},
    "role": {"type": "string", "enum": ["ADMIN", "ENGINEER"]},
    "locale": {"type": "string", "enum": ["zh-CN", "en-US"]},
    "theme": {"type": "string", "enum": ["light", "dark"]}
  }
}
```

### 3.2 `auth-session.schema.json`

```jsonc
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://pcb-cdso.local/schemas/auth-session.schema.json",
  "title": "PCB-CDSO Auth Session",
  "type": "object",
  "additionalProperties": false,
  "required": ["access_token", "refresh_token", "expires_in", "user", "locale", "theme"],
  "properties": {
    "access_token": {"type": "string", "minLength": 16},
    "refresh_token": {"type": "string", "minLength": 16},
    "expires_in": {"type": "integer", "minimum": 1, "maximum": 86400},
    "user": {"$ref": "user.schema.json"},
    "locale": {"type": "string", "enum": ["zh-CN", "en-US"]},
    "theme": {"type": "string", "enum": ["light", "dark"]}
  }
}
```

### 3.3 `user.schema.json`（新建；`User` 是 `users` 表的对外形状）

```jsonc
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://pcb-cdso.local/schemas/user.schema.json",
  "title": "PCB-CDSO User",
  "type": "object",
  "additionalProperties": false,
  "required": ["id", "email", "role", "is_active"],
  "properties": {
    "id": {"type": "string", "maxLength": 36},
    "email": {"type": "string", "format": "email", "maxLength": 320},
    "role": {"type": "string", "enum": ["ADMIN", "ENGINEER"]},
    "is_active": {"type": "boolean"}
  }
}
```

### 3.4 `project.schema.json`（新建）

```jsonc
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://pcb-cdso.local/schemas/project.schema.json",
  "title": "PCB-CDSO Project Summary",
  "type": "object",
  "additionalProperties": false,
  "required": ["id", "name", "owner_id", "template_version_id", "country_code", "admin_area", "city", "timezone", "status", "created_at"],
  "properties": {
    "id": {"type": "string", "maxLength": 36},
    "name": {"type": "string", "minLength": 1, "maxLength": 120},
    "owner_id": {"type": "string", "maxLength": 36},
    "template_version_id": {"type": "string", "minLength": 1},
    "country_code": {"type": "string", "pattern": "^[A-Z]{2}$"},
    "admin_area": {"type": "string", "minLength": 1, "maxLength": 120},
    "city": {"type": "string", "minLength": 1, "maxLength": 120},
    "timezone": {"type": "string", "minLength": 1},
    "status": {"type": "string", "enum": ["ACTIVE", "ARCHIVED", "SOFT_DELETED"]},
    "created_at": {"type": "string", "format": "date-time"}
  }
}
```

### 3.5 扩展 `error.schema.json` 与 `task.schema.json`

按第 1 节对齐缺口表，扩展 enum：

- `error.schema.json.code` 增加：`UNAUTHENTICATED`, `NOT_FOUND`, `IDEMPOTENCY_CONFLICT`, `TRANSACTION_FAILED`, `COMMIT_OUTCOME_UNKNOWN`。
- `task.schema.json.status` 增加：`DISPATCH_PENDING`, `STALE`。

### 3.6 扩展 `idempotency.schema.json`

新增字段表达持久化幂等记录：

```jsonc
{
  "required": ["idempotencyKey", "scope", "actor_id", "canonical_request_hash", "status"],
  "properties": {
    "idempotencyKey": {"type": "string", "minLength": 1, "maxLength": 128},
    "scope": {"type": "string", "minLength": 1, "maxLength": 128},
    "actor_id": {"type": "string", "maxLength": 36},
    "canonical_request_hash": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
    "status": {"type": "string", "enum": ["IN_PROGRESS", "SUCCEEDED"]}
  }
}
```

## 4. Contract Agent 落地顺序（TDD）

1. **先写失败契约测试**：在 `tests/contract/test_openapi.py` 与 `tests/contract/test_json_schemas.py` 中新增断言（新路径存在、新 enum 成员存在、新 schema 文件加载通过、`actorId` 不在 `CreateProjectRequest` properties 中）。
2. **跑测试确认失败**，失败原因必须只与契约缺失相关，不能是导入错误。
3. **修改 `contracts/`**：扩展 OpenAPI、新增/扩展 schema 文件。
4. **跑 `python scripts/quality/generate_openapi.py`**（若存在生成器；否则手改 `openapi.json`）确认 OpenAPI 与 FastAPI 实现不漂移——M0 阶段 FastAPI 尚无这些端点，生成器会失败是预期的，契约测试只校验 `contracts/openapi/openapi.json` 静态文件。
5. **跑治理**：`python scripts/quality/check_governance.py` 必须仍 valid。
6. **PR**：标题 `contracts(m1): freeze auth and project dispatch interfaces`，链接本设计草案与 ADR-0002。

## 5. 非目标

- 不在本文档冻结 `template-lifecycle`、`identity-and-ownership`、`template-demo-seeds` 的 OpenAPI（这些由后续 M1 子任务的 Feature Spec 与本设计草案同模式产出）。
- 不修改 M0 已批准的 `/health/*` 与 `/internal/tasks/smoke` 路径。
- 不引入 JWT、OAuth、SSO（PRD 明确排除）。

## 6. 已决策项（技术负责人 2026-07-21 采纳默认）

| 决策项 | 采纳结论 |
|---|---|
| `Idempotency-Key` 位置 | HTTP header（`Idempotency-Key`），不进 request body，不参与 canonical hash 计算 |
| `User.created_at` 对外暴露 | 不暴露；`User` schema 只含 `id/email/role/is_active` |
| access token TTL 文档归属 | 仅写入 ADR-0002（默认 900 秒），不进 PRD |

Contract Agent 落地时按上述结论执行；与本草案第 1-5 节冲突时停下回报（AGENTS.md 第 2 条）。
