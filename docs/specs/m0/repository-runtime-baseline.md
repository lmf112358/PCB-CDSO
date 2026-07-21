# M0 Repository Runtime Baseline Feature Spec

| 属性 | 值 |
|---|---|
| 状态 | approved |
| 版本 | 1.0.0 |
| Owner | Platform / Orchestrator |
| Milestone | M0 |
| Task | M0 foundation vertical slice |
| PRD 追踪 | P0_01；P0_14 基线；PRD 6.1-6.5 |

## 用户结果

开发者可以从空数据库通过一组确定命令启动 PCB-CDSO 基础系统，并在浏览器看到双语、明暗主题登录壳；运维者可区分进程存活与 MySQL/Redis 就绪状态，所有接口具有稳定 OpenAPI 和关联 ID。

## 范围与非目标

### 包含

- React/Vite 桌面 Web 登录壳、`zh-CN/en-US` 与 `light/dark`。
- FastAPI live/ready、统一错误体、request ID 中间件和 OpenAPI。
- MySQL 初始迁移与幂等 bootstrap 管理员命令。
- Redis/Celery smoke task 和 Worker health 基线。
- Docker Compose、环境变量样例、统一验证命令和 CI build 门禁。
- error/task/revision/idempotency 机器契约。

### 不包含

- 实际登录会话、工程师账号后台、项目与模板业务。
- 问答状态机、计算、气象、结果图表和 CSV。
- Kubernetes、SSO、前馈控制或移动端。

## 不变量

- MySQL 是业务事实源，Redis 不保存长期业务结果。
- API、Worker 和迁移使用同一数据库模型，但各自创建 Session。
- `/health/live` 不访问外部依赖；`/health/ready` 必须真实探测 MySQL 与 Redis。
- 所有响应返回 `X-Request-ID`；错误体中的 `request_id` 与响应头一致。
- bootstrap 密码不进入日志、审计明文或数据库明文字段。
- 登录壳不得模拟成功登录或显示 M1-M6 的假入口。

## 正常流程

1. 部署方复制 `.env.example` 并设置本地非生产密码。
2. Compose 启动 MySQL 和 Redis并等待健康检查。
3. `migrate` 将空库升级到 Alembic head。
4. `bootstrap-admin` 在管理员不存在时创建一条 Argon2 哈希账号记录；已存在时幂等退出。
5. API、Worker 和 Web 启动。
6. 浏览器加载登录壳；语言和主题选择立即生效并本地保存。
7. 健康接口和 OpenAPI 可访问；Celery smoke task 返回稳定结果。

## 失败与恢复

| 触发 | 错误码/状态 | 用户/运维提示 | 是否写入 | 恢复动作 |
|---|---|---|---|---|
| MySQL 不可用 | 503 `DEPENDENCY_UNAVAILABLE` | database unavailable | 否 | 恢复 MySQL 后重试 ready |
| Redis 不可用 | 503 `DEPENDENCY_UNAVAILABLE` | redis unavailable | 否 | 恢复 Redis 后重试 ready |
| 迁移失败 | Compose `migrate` 非零退出 | migration failed | 事务内回滚 | 修复迁移后重新运行 |
| bootstrap 配置缺失 | 命令非零退出 | required bootstrap variable missing | 否 | 补齐环境变量后重试 |
| bootstrap 管理员已存在 | 命令零退出 | administrator already exists | 否 | 删除一次性密码变量并继续 |
| 未处理 API 异常 | 500 `INTERNAL_ERROR` | errors.internal | 否 | 使用 request ID 查结构化日志 |

## 状态清单

| 对象 | 状态 | 进入条件 | 允许操作 | 退出条件 |
|---|---|---|---|---|
| API readiness | `ready` | DB 与 Redis 均探测成功 | 接收请求 | 任一依赖失败 |
| API readiness | `degraded` | DB 或 Redis 失败 | live、ready、诊断 | 依赖恢复 |
| Task | `QUEUED/RUNNING/SUCCEEDED/FAILED/CANCELLED` | 由 Celery 生命周期驱动 | 查询状态 | 进入终态 |
| Login shell | `idle/loading/error/disabled` | UI 事件或 API 响应 | 切换语言/主题、提交 | 状态变化 |

## API、数据与版本

- `GET /health/live` → 200，返回 `status/service/version/request_id`。
- `GET /health/ready` → 200 或 503，返回 `status/dependencies/request_id`。
- `POST /internal/tasks/smoke` 仅在开发/测试配置可用，接收幂等键并返回 task envelope。
- OpenAPI `3.1.x` 文件生成到 `contracts/openapi/openapi.json`，CI 比较生成结果与提交文件。
- 初始迁移建立 `users` 和 `audit_events`；用户角色约束为 `ADMIN/ENGINEER`，M0 只创建 ADMIN。
- 公共 JSON Schema 位于 `contracts/schemas/`，schema version 为 `1.0.0`。

## 可观察性

日志字段至少为 `timestamp/level/service/event/request_id`。HTTP 日志可包含 method、path、status、duration_ms，但禁止密码、Authorization、Cookie 和完整数据库 URL。bootstrap 审计事件为 `admin.bootstrap.created`，只记录 user id 与 email。

## 验收场景

1. Given 空卷和有效 `.env`，When 运行 Compose，Then migration、bootstrap、API、Worker、Web 全部成功且 ready 为 200。
2. Given 已创建管理员，When 再运行 bootstrap，Then 返回成功、用户数不变且不产生第二个 created 审计。
3. Given Redis 停止，When 请求 ready，Then 返回 503、live 仍为 200、错误含同一 request ID。
4. Given 浏览器首次加载，When 切换英文和暗色，Then文字、主题和持久化值同步变化，无假登录成功。
5. Given 当前代码，When 重新生成 OpenAPI，Then 与提交契约无差异。
6. Given 仓库和容器日志，When 扫描 bootstrap 密码，Then 无匹配结果。

## 测试映射

| 验收条件 | 测试层级 | 测试文件/fixture | 门禁 |
|---|---|---|---|
| health 与 request ID | unit/contract | `services/api/tests/test_health.py`、`tests/contract/test_openapi.py` | required |
| migration/bootstrap 幂等 | integration | `services/api/tests/integration/test_bootstrap.py` | required |
| Redis/Celery smoke | integration | `services/api/tests/integration/test_tasks.py` | required |
| 登录壳双语主题 | unit/e2e | `apps/web/src/App.test.tsx`、`tests/e2e/login-shell.spec.ts` | required |
| 空库 Compose | integration/e2e | `scripts/quality/verify_m0.py` | required |
| 无密钥泄漏 | security | `scripts/quality/verify_m0.py` | required |

## 阻断审批的问题

无。基础镜像精确 digest 在首次成功构建时记录到 M0 Acceptance Record；这不改变架构或接口语义。

