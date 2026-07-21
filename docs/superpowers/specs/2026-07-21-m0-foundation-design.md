# PCB-CDSO M0 Foundation Design

| 属性 | 值 |
|---|---|
| 状态 | approved |
| Milestone | M0 Repository Baseline |
| PRD 追踪 | P0_01；P0_14 基线 |
| 批准依据 | 已批准 PRD、M0 Milestone Spec，以及用户“开始 M0 阶段开发”指令 |

## 1. 目标与边界

M0 建立一套可重复启动、可测试、可迁移、可审查的应用骨架，并冻结 M1-M6 并行开发依赖的机器契约。M0 完成时，干净环境可启动 Web、API、MySQL、Redis 和 Worker；API 暴露健康检查与 OpenAPI；Web 显示双语登录壳；数据库迁移可重复执行；首个管理员有安全的一次性注入路径。

M0 不实现工程师账号管理、模板业务、项目业务、问答、计算、气象或结果中心。这些只保留契约扩展点，不展示假入口。

## 2. 方案比较与决策

| 方案 | 优点 | 代价 | 决策 |
|---|---|---|---|
| 模块化单体 API + 独立 Celery Worker + React SPA | 最少部署单元；事务清晰；两个全栈可按领域并行；未来可拆 Worker/计算域 | API 初期共享进程与数据库 | 采用 |
| FastAPI 同时托管构建后的 SPA | 单容器较简单 | 前后端开发和缓存策略耦合，降低多 Agent 并行效率 | 不采用 |
| 身份、项目、计算、气象微服务 | 边界最显式 | 1.5 周内产生大量网络、部署、契约和可观察性成本 | 不采用 |

系统采用 npm workspaces 管理 Web，Python service 使用 `pyproject.toml` 和锁文件。API 使用同步 SQLAlchemy Session；FastAPI 请求与 Celery 任务各自创建独立 Session，避免跨线程/任务共享。Redis 只承担 Celery broker/result 和短期协调数据，不保存业务事实。

## 3. 目录与组件边界

```text
apps/web/                     React/Vite 桌面 Web
services/api/                 FastAPI、领域模块、Alembic、Celery
contracts/openapi/            生成并提交的 OpenAPI 基线
contracts/schemas/            错误、任务、幂等、revision JSON Schema
infra/docker/                 容器入口与健康检查脚本
tests/contract/               契约解析与漂移测试
tests/integration/            MySQL/Redis/迁移/启动测试
tests/e2e/                    登录壳 smoke
```

API 内部保持 `core / db / http / tasks` 四个基础边界。M1 起按业务领域新增模块，不建立通用 `utils.py` 大杂烩。

## 4. 运行与数据流

```text
Browser -> Web dev/server -> FastAPI -> SQLAlchemy -> MySQL
                              |
                              +-> Celery producer -> Redis -> Worker -> MySQL
```

Compose 启动顺序由 healthcheck 控制：MySQL/Redis healthy 后运行一次性 `migrate`；迁移成功后 API 与 Worker 启动；Web 只依赖 API health。迁移失败必须使启动链明确失败，不允许 API 在未知 schema 上继续运行。

`GET /health/live` 只证明进程存活；`GET /health/ready` 检查数据库与 Redis，返回依赖明细和 `request_id`。OpenAPI 位于 `/openapi.json`。

## 5. 契约基线

统一错误体：

```json
{
  "code": "VALIDATION_FAILED",
  "message_key": "errors.validation_failed",
  "field_path": "factory.name",
  "details": {},
  "request_id": "01J..."
}
```

M0 冻结以下语义：

- 错误码至少包括 `FORBIDDEN`、`REVISION_CONFLICT`、`VALIDATION_FAILED`、`DEPENDENCY_UNAVAILABLE`、`INTERNAL_ERROR`。
- 写请求的 revision 字段统一命名为 `expectedInputRevision`；冲突返回 HTTP 409，不部分写入。
- 创建异步任务通过 `Idempotency-Key` 请求头去重；同一作用域与键返回同一 task id。
- 任务状态固定为 `QUEUED/RUNNING/SUCCEEDED/FAILED/CANCELLED`，并返回 `progress/stage/processed/total/error/retryable`。
- 请求关联 ID 使用 `X-Request-ID`；缺失时服务端生成，并在响应及结构化日志中返回。

## 6. 首个管理员安全设计

部署方首次启动时提供 `BOOTSTRAP_ADMIN_EMAIL` 与 `BOOTSTRAP_ADMIN_PASSWORD`。迁移后独立 bootstrap 命令在事务中执行：

1. 若管理员已存在，成功退出且不读取/记录密码。
2. 若不存在，校验邮箱和密码强度，使用成熟 Argon2 实现保存哈希。
3. 写入审计事件，只记录账号、时间和来源，不记录密码或哈希。
4. 部署方删除一次性密码变量后重启；系统仍可正常运行。

M0 只实现命令与数据路径；登录会话和账号后台在 M1 完成。

## 7. Web 登录壳

仅实现桌面端 1440×900 优先的登录壳，包括产品标识、语言切换、明暗主题切换、邮箱/密码字段以及 `loading/error` 状态。提交按钮在 M0 调用受控占位 API 或保持明确“身份模块将在 M1 启用”的非交互状态，不伪造登录成功。

所有文字进入 `zh-CN/en-US` 资源，不在组件内硬编码。主题通过 design tokens 实现，M1-M6 复用同一应用壳。

## 8. 失败处理与可观察性

- 依赖不可用：ready 返回 503 和 `DEPENDENCY_UNAVAILABLE`，live 仍可返回 200。
- 未处理异常：对外返回稳定错误体，不泄漏堆栈；日志包含 request ID 和异常。
- 日志为 JSON，禁止输出密码、Cookie、Authorization、数据库 URL 密码。
- Worker 任务在 M0 仅提供 smoke task；重试采用显式策略，未知异常不无限重试。
- 容器重启后迁移不会重复产生副作用。

## 9. 测试策略

| 层级 | M0 必测行为 |
|---|---|
| 治理 | PRD、Schema、验收和 PR 元数据检查 |
| Unit | 配置解析、错误体、request ID、bootstrap 幂等 |
| Contract | OpenAPI/JSON Schema 可解析，错误体与任务字段稳定 |
| Integration | 空 MySQL upgrade、重复 upgrade、API ready、Redis、Celery smoke |
| Web | i18n/theme 状态、登录壳 loading/error |
| E2E | Compose 启动后页面加载与 health/OpenAPI |
| Security | 仓库与日志不含 bootstrap 明文密码 |

测试顺序严格执行 RED → GREEN → REFACTOR。外部依赖的集成测试使用真实 Compose 服务，不以 mock 替代数据库迁移和队列连通性。

## 10. 完成判定

M0 只有在以下证据齐备时才能进入 GO：所有 ADR approved；锁文件提交；`docker compose up --build` 从空卷成功；迁移和重启通过；OpenAPI/Schema 解析；Web 登录壳 smoke 通过；统一 `make verify` 通过；M0 Test Plan、Acceptance Record 和 Candidate SHA 通过治理检查。

GitHub 分支保护因本机未安装 `gh` 无法自动读取，必须以仓库 Settings 截图或 GitHub API/CLI 输出作为 M0 验收证据，不能仅凭配置意图勾选完成。

