# M1 实现计划：项目创建与气象任务可靠派发

| 属性 | 值 |
|---|---|
| 状态 | draft |
| 适用 Milestone | M1（当前子任务范围 = `docs/specs/m1/project-weather-dispatch.md` v1.0.0）|
| 适用测试计划 | `docs/testing/plans/M1-test-plan.md`（approved）|
| 关联 ADR | ADR-0001、ADR-0002（draft）|
| 关联设计草案 | `docs/architecture/m1-contract-expansion-design.md`、`docs/architecture/m1-migration-0002-design.md` |
| 用途 | Orchestrator 派发 M1 任务包的顺序与文件租约依据；Implementer 不在本计划之外扩范围 |

本计划严格遵守 AGENTS.md 第 4 条“任务目标只能包含一个主要结果”与“接口变更先合并契约 PR，再分别建立消费者任务”。M1 实现按 **DoR 补齐 → 契约任务 → 消费者任务** 三波次串行派发；同一文件同一时间只有一个写入 Agent。

## 0. 前置阻塞（必须在 Wave 1 之前完成）

| 编号 | 阻塞项 | 责任人 | 完成判定 |
|---|---|---|---|
| B-1 | M0 升 `verified` | Product Owner（独立 Acceptance Agent）| `docs/testing/acceptance/M0-acceptance.md` 状态 `GO` + Product Sign-off 非 pending；`python scripts/quality/check_governance.py --acceptance-ready M0` 退出 0；`docs/milestones/M0-repository-baseline.md` 状态 `verified` |
| B-2 | ADR-0002 从 `draft` 升 `approved` | 技术负责人 | ✅ 已完成：李名沨 2026-07-21 签字，状态 `approved`，决策项采纳默认 |
| B-3 | 契约设计草案与迁移设计草案评审 | 技术负责人 + Orchestrator | ✅ 已完成：各草案“已决策项”章节冻结，技术负责人 2026-07-21 采纳默认 |

**B-1 不完成，Wave 1 不得开始**（M1 milestone DoR 第 1 项硬前置）。

## Wave 1：DoR 工件补齐（Spec / Contract 角色，spec/ 分支）

按 AGENTS.md 第 4 条，每个工件是独立任务包、独立分支、独立 PR，避免单 PR 混合多意图。

### Task 1.1：扩展 OpenAPI 与 JSON Schema（Contract Agent）

**Goal:** 冻结 `/auth/login`、`/auth/refresh`、`/auth/logout`、`/auth/me`、`POST /projects`、`GET /tasks`、`GET /tasks/{id}` 的机器契约，并修复 `error.schema.json` / `task.schema.json` / `idempotency.schema.json` 的 enum 与字段缺口。

**Source:** `docs/architecture/m1-contract-expansion-design.md`、ADR-0002、M1 Feature Spec。

**Base SHA:** 待 Wave 1 派发时记录（必须 = 派发时 `origin/main` HEAD）。

**Allowed Paths:**
- `contracts/openapi/openapi.json`
- `contracts/schemas/error.schema.json`
- `contracts/schemas/task.schema.json`
- `contracts/schemas/idempotency.schema.json`
- `contracts/schemas/actor-context.schema.json`（新建）
- `contracts/schemas/auth-session.schema.json`（新建）
- `contracts/schemas/user.schema.json`（新建）
- `contracts/schemas/project.schema.json`（新建）
- `tests/contract/test_openapi.py`
- `tests/contract/test_json_schemas.py`

**Forbidden:** `services/api/src/**`、`services/api/alembic/**`、`apps/web/**`。

**TDD 顺序：**
- [ ] 在 `tests/contract/test_openapi.py` 写失败断言（新路径存在、`CreateProjectRequest` 不含 `actorId`、新错误码在 enum）。
- [ ] 在 `tests/contract/test_json_schemas.py` 写失败断言（新 schema 文件加载、扩展 enum 校验通过、反例失败）。
- [ ] 跑 `python -m pytest tests/contract -q`，确认失败原因正确。
- [ ] 修改 `contracts/`。
- [ ] 跑 `python -m pytest tests/contract -q`，全绿。
- [ ] 跑 `python scripts/quality/check_governance.py`，valid。
- [ ] PR：`contracts(m1): freeze auth, project and task interfaces`。

**Acceptance：** 契约 PR 合并后 `main` 含新路径与新 schema；治理 valid。

### Task 1.2：迁移 0002（Contract Agent）

**依赖：** Task 1.1 合并（迁移列引用契约字段，虽不直接依赖，但为避免契约与迁移漂移，串行）。

**Goal:** 落地 `0002_m1_project_weather_dispatch.py`，覆盖 9 张表/列变更（见 `docs/architecture/m1-migration-0002-design.md`）。

**Allowed Paths:**
- `services/api/alembic/versions/0002_m1_project_weather_dispatch.py`
- `services/api/src/pcb_cdso/db/models.py`（扩展 ORM 模型，仅新增不修改 `User`/`AuditEvent` 既有字段）
- `services/api/tests/test_migration_0002.py`（新建）

**Forbidden:** `contracts/**`、其他 `services/api/src/pcb_cdso/http/**`、`apps/web/**`。

**TDD 顺序：**
- [ ] 写失败测试：从空库 `alembic upgrade head` 后用 `SHOW CREATE TABLE` 断言每张表存在、唯一约束/索引命名固定、CHECK 约束存在；`alembic downgrade base` 后所有新表消失。
- [ ] 跑测试，确认失败（迁移文件不存在）。
- [ ] 写迁移 + ORM 模型。
- [ ] 跑 `alembic upgrade head` && `alembic downgrade base` && `alembic upgrade head` 在干净测试库，全绿。
- [ ] 跑 `cd services/api && python -m pytest -q`，全绿（既有 14 测试不破坏）。
- [ ] PR：`feat(api): add migration 0002 for project weather dispatch`。

**Acceptance：** 迁移可前向与反向；治理 valid；既有测试全绿。

### Task 1.3：Fixture 数据集（Test Agent）

**Goal:** 产出 M1 测试计划“Fixture”章节定义的 3 个数据集文件，状态 `SOFTWARE_VERIFIED`（producer 与 verifier 不同身份）。

**依赖：** Task 1.2 合并（fixture 引用迁移后的表）。

**Allowed Paths:**
- `fixtures/acceptance/M1/project-weather-dispatch/1.0.0/**`
- `fixtures/acceptance/M1/transaction-faults/1.0.0/**`
- `fixtures/acceptance/M1/dispatch-recovery/1.0.0/**`
- 各自 `manifest.json` + 校验记录。

**TDD 顺序：**
- [ ] 写 fixture manifest（满足 `contracts/fixtures/fixture-manifest.schema.json`）。
- [ ] producer 生成文件 + checksum；独立 verifier 校验并写 verification record。
- [ ] 跑 `python scripts/quality/check_governance.py`，fixture 字段通过。
- [ ] PR：`test(m1): add project-weather-dispatch fixtures`。

**Acceptance：** fixture 状态从 `PLANNED / NOT_VERIFIED` 升 `SOFTWARE_VERIFIED`；治理 valid。

> **注意：** Task 1.3 与 Task 2.x 可部分并行——fixture 文件租约与实现代码文件租约不相交。但为简化试开发期租约管理，本计划建议串行。

## Wave 2：实现（Implementer 角色，feat/ 分支）

按 M1 测试计划的 17 个测试用例从低风险到高风险串行实现。每个 Task 一个 PR，每个 PR 内严格 TDD。

### Task 2.1：认证与会话端点（Implementer）

**依赖：** Wave 1 全部合并。

**Goal:** 实现 `POST /auth/login`、`POST /auth/refresh`、`POST /auth/logout`、`GET /auth/me` 与 `get_actor` 依赖（ADR-0002）。

**Allowed Paths:**
- `services/api/src/pcb_cdso/http/auth.py`（新建）
- `services/api/src/pcb_cdso/http/deps.py`（新建，`get_actor`）
- `services/api/src/pcb_cdso/db/models.py`（仅扩展 `User` 列，已在 1.2 写入则只读引用）
- `services/api/tests/test_auth_*.py`

**测试映射：** 不在 M1 测试计划 17 用例内（那些聚焦 project-weather-dispatch），但认证是 `POST /projects` 的前置。Contract Agent 应在 Task 1.1 的契约测试中已覆盖 auth schema；本任务补集成测试。

**TDD 顺序：**
- [ ] 写失败测试：登录成功返回 token、停用即撤销、refresh 轮换、logout 撤销、伪造 actorId 忽略。
- [ ] 实现端点与依赖。
- [ ] 全绿后重构。
- [ ] PR：`feat(api): add auth endpoints and actor dependency`。

### Task 2.2：项目创建核心（Implementer）

**依赖：** Task 2.1 合并。

**Goal:** 实现 `POST /projects` 正常路径（M1-C-001、M1-I-002、M1-I-003、M1-I-005）—— 单事务写幂等记录 + Project + 不可变快照 + DISPATCH_PENDING Task + OutboxEvent。

**Allowed Paths:**
- `services/api/src/pcb_cdso/domain/projects.py`（新建，CreateProject 命令）
- `services/api/src/pcb_cdso/http/projects.py`（新建）
- `services/api/src/pcb_cdso/tasks/dispatcher.py`（新建，fake dispatcher 读 Outbox）
- `services/api/tests/integration/test_project_weather_transaction.py`（对应 M1-I-001/011）
- `services/api/tests/integration/test_project_weather_idempotency.py`（对应 M1-I-002/003/004/005/012/013）
- `services/api/tests/contracts/test_create_project_contract.py`（对应 M1-C-001/002）

**测试映射：** M1-C-001、M1-C-002、M1-I-002、M1-I-003、M1-I-005、M1-I-012、M1-I-013。

**TDD 顺序（按测试用例编号）：**
- [ ] M1-C-001：契约层，合法创建返回 201 + weatherTaskId + DISPATCH_PENDING。
- [ ] M1-C-002：契约层，字段校验矩阵。
- [ ] M1-I-002：串行重放 200。
- [ ] M1-I-003：并发同 hash 20/20。
- [ ] M1-I-012：并发不同 hash loser 409。
- [ ] M1-I-005：actor scope。
- [ ] M1-I-013：pre-commit 失败后同键重试。
- [ ] 每个用例红→绿→重构→提交。
- [ ] PR：`feat(api): create project with atomic weather task dispatch`。

### Task 2.3：事务原子性与故障注入（Implementer）

**依赖：** Task 2.2 合并。

**Goal:** 实现 M1-I-001（pre-commit 故障零行）与 M1-I-011（commit outcome unknown 同键重放）。

**Allowed Paths:** 同 Task 2.2，扩展故障注入点。

**关键设计：** 应用层提供可注入的 hook（如 `before_project_commit` callback），测试用 monkeypatch 注入异常；commit outcome unknown 用事务 commit 后 socket 断开模拟。

**TDD 顺序：**
- [ ] M1-I-001：5 个写点（幂等记录、Project、快照、Task、Outbox）+ pre-commit 分别失败，断言零行。
- [ ] M1-I-011：commit 后断连，同键重放收敛。
- [ ] PR：`test(api): assert atomic rollback and commit-unknown replay`。

### Task 2.4：Outbox 派发与 reconciler（Implementer）

**依赖：** Task 2.2 合并。

**Goal:** 实现 fake dispatcher 与 reconciler，覆盖 M1-I-006/007/008A/008B/008C/010/014。

**Allowed Paths:**
- `services/api/src/pcb_cdso/tasks/dispatcher.py`
- `services/api/src/pcb_cdso/tasks/reconciler.py`（新建）
- `services/api/tests/integration/test_weather_outbox_dispatch.py`

**TDD 顺序：** 按测试编号逐个红→绿。
- [ ] PR：`feat(api): add weather outbox dispatcher and reconciler`。

### Task 2.5：Worker effect 与崩溃恢复（Implementer）

**依赖：** Task 2.4 合并。

**Goal:** 实现 fake Worker effect 事务，覆盖 M1-I-015A/015B（真实 MySQL probe 恰一行、Task 不倒退）。

**Allowed Paths:**
- `services/api/src/pcb_cdso/tasks/weather_worker.py`（新建）
- `services/api/tests/integration/test_weather_outbox_dispatch.py`（扩展）

**关键设计：** effect 事务严格按 M1 Feature Spec 第 119–122 行：lease → upsert probe + execution SUCCEEDED + Task CAS，三项原子。

**TDD 顺序：**
- [ ] M1-I-015A：effect 前崩溃重投。
- [ ] M1-I-015B：effect 后 ack 前崩溃重投复用。
- [ ] PR：`feat(api): add weather worker effect with crash recovery`。

### Task 2.6：权限与审计（Implementer）

**依赖：** Task 2.2 合并。

**Goal:** 覆盖 M1-I-009（跨 owner 404 不可区分、列表 200 filtered、ADMIN 可见、敏感字段不记日志）。

**Allowed Paths:**
- `services/api/src/pcb_cdso/http/projects.py`（扩展 GET）
- `services/api/src/pcb_cdso/http/tasks.py`（新建 GET）
- `services/api/src/pcb_cdso/services/authorization.py`（新建，scoped lookup）
- `services/api/tests/integration/test_project_task_authorization.py`

**TDD 顺序：** 严格按 M1 Feature Spec 第 103–105 行防枚举规则。
- [ ] PR：`feat(api): enforce scoped project task authorization`。

### Task 2.7：2 秒性能契约（Implementer）

**依赖：** Task 2.2 + 2.6 合并。

**Goal:** 覆盖 M1-P-001（POST /projects 响应后 2 秒内 GET /tasks/{id} 与列表均返回同一 task id）。

**Allowed Paths:**
- `services/api/tests/performance/test_initial_weather_task_visibility.py`（新建）

**关键设计：** 性能测试不依赖 dispatcher/Worker 完成，只验证持久化 task id 的可见性。记录 OS/CPU/内存/镜像摘要/单调时钟（M1 测试计划“环境”章节）。

**TDD 顺序：**
- [ ] M1-P-001：多次运行均 ≤2.0s。
- [ ] PR：`test(api): assert 2s weather task visibility contract`。

## Wave 3：验收（Acceptance Agent 角色，干净环境）

### Task 3.1：M1 验收签认

**责任人：** 独立 Acceptance Agent（不得是 Wave 2 任一 Implementer，AGENTS.md 第 3 条）。

**步骤：**
- [ ] 在干净环境（`docker compose down --volumes && docker compose up --build --wait`）执行 M1 测试计划“执行顺序与门禁”全部命令，退出码 0。
- [ ] 收集每个 Test ID 证据到 `artifacts/acceptance/M1/M1-*.txt`。
- [ ] 生成 `artifacts/acceptance/M1/index.json`（SHA、环境、命令、退出码、时间、checksum）。
- [ ] 填写 `docs/testing/acceptance/M1-acceptance.md`，状态 `GO`，Product Sign-off 由产品负责人签。
- [ ] `docs/milestones/M1-identity-template-project.md` 状态升 `verified`。
- [ ] `python scripts/quality/check_governance.py --acceptance-ready M1` 退出 0。

**停止条件：** 任一 Wave 2 测试用例失败、Provider 调用数 > 0、跨 owner 404 可区分、性能 > 2.0s、或 probe 行数 ≠ 1 → NO-GO，返回 Implementer。

## 文件租约登记（Orchestrator 在 Issue 中维护）

派发时 Orchestrator 必须在每个 Issue 顶部记录 Active file lease，遵循 AGENTS.md 第 5 条。本计划预登记的租约边界（实际以 Issue 为准）：

| Wave | Task | 主要租约路径 | Expires |
|---|---|---|---|
| 1 | 1.1 | `contracts/**`、`tests/contract/**` | 派发后 1 天 |
| 1 | 1.2 | `services/api/alembic/versions/0002_*`、`services/api/src/pcb_cdso/db/models.py`、`services/api/tests/test_migration_0002.py` | 派发后 1 天 |
| 1 | 1.3 | `fixtures/acceptance/M1/**` | 派发后 1 天 |
| 2 | 2.1 | `services/api/src/pcb_cdso/http/auth.py`、`deps.py`、`tests/test_auth_*` | 派发后 0.5 天 |
| 2 | 2.2 | `services/api/src/pcb_cdso/domain/projects.py`、`http/projects.py`、`tasks/dispatcher.py`、对应 tests | 派发后 1 天 |
| 2 | 2.3–2.7 | 同 2.2 扩展 + 各自新文件 | 派发后 1 天 |

**相交路径预警：** Task 2.2–2.7 共享 `http/projects.py` 与 `tasks/dispatcher.py`，**不得并行派发**，必须串行（2.2 → 2.3 → 2.4 → 2.5 → 2.6 → 2.7）。Orchestrator 在前一任务 PR 合并并释放租约后再派发下一任务。

## Completion verification

M1 整体验收前，仓库根目录依次执行，每条退出码必须为 0：

```bash
python scripts/quality/check_governance.py
python scripts/quality/check_secrets.py
cd services/api && python -m pytest -q && cd ..
python -m unittest discover -s tests -p "test_*.py" -v
python -m pytest tests/contracts tests/integration tests/performance -q   # 路径按 M1 测试计划
git diff --check
git status --short
python scripts/quality/check_governance.py --acceptance-ready M1
```

任何一项非 0 即 NO-GO。

## 非目标

- 本计划**不**覆盖 P0_02（身份与归属完整）、P0_03（模板生命周期）、P0_13（模板 demo seeds）的完整实现；这些由后续 M1 子任务的独立 Feature Spec 与计划处理。本计划只在 `templates`/`template_versions` 落最小骨架使 `projects.template_version_id` 有引用目标。
- 不实现 M2 八阶段问答、M3 静态计算、M4 真实 Provider、M5 结果中心、M6 导出。
- 不引入 JWT、SSO、邮件邀请、组织架构（PRD 明确排除）。
- 不在本计划内修改 M0 已批准代码（迁移 0001、bootstrap、health、errors、request_id、tasks smoke）。

## 已决策项（技术负责人 2026-07-21 采纳默认，Wave 1 可派发）

| 决策项 | 采纳结论 |
|---|---|
| ADR-0002 决策项 | ADR 已 `approved`，详见 ADR“验证证据”章节 |
| 契约草案 3 项 | Idempotency-Key 用 header；User 不暴露 created_at；TTL 仅在 ADR-0002 |
| 迁移草案 4 项 | 单一 idempotency 唯一约束；execution 独立表；ownership_version 保留列不写入；templates 最小骨架在 0002 内 |
| Wave 2 并行策略 | 串行（Task 2.1 → 2.7）；试开发期保守，不并行 |
| Fixture producer/verifier 身份 | 不同 Agent 或不同会话承担；治理脚本强制 |

Wave 1 Task 1.1 派发前置已全部满足（B-2、B-3 完成）；B-1（M0 verified）待 PR1 合并后即满足。
