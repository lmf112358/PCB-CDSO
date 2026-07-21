# ADR-0002：认证与服务端可撤销会话

| 属性 | 值 |
|---|---|
| 状态 | approved |
| 日期 | 2026-07-21 |
| 决策人 | 技术负责人 / Orchestrator |
| 关联 Issue | 待 Orchestrator 派发 M1 契约任务时登记 |
| 替代 ADR | 无；扩展 ADR-0001 第 47 行“服务端会话在 M1 落地” |
| 适用范围 | M1 起全部需要认证的 API；M0 仅冻结可撤销会话接口形状 |
| 技术负责人批准 | 李名沨 2026-07-21（采纳本 ADR 全部决策；契约/迁移草案的待决策项见各自“已决策项”章节） |

## 上下文

PRD v0.6 第 3.1 章、第 11 章安全条款和 ADR-0001 第 47 行共同要求：

- 认证使用成熟密码哈希和服务端**可撤销会话**，不自造密码学。
- `POST /auth/login` 接收 username、password，返回 access token、refresh session、user、locale/theme。
- 访问令牌短期有效，刷新令牌可撤销；账号停用后**立即撤销所有活动会话**。
- `ENGINEER` 只能访问自有项目；`ADMIN` 可见全部并可在同一事务转交项目，旧 owner 立即失权。
- M1 Feature Spec `docs/specs/m1/project-weather-dispatch.md` 把 `actorId` 作为认证上下文注入的必填字段，并要求请求体中的同名值不得覆盖认证身份。

M0 已在 `services/api` 引入 `pwdlib[argon2]==0.3.0`（见 `pyproject.toml` 与 `bootstrap.py`），密码哈希方案无需重新选型。但 M0 尚未引入任何 token 签发、会话存储或依赖注入机制，需要 M1 在不并行引入两套等价方案的前提下冻结。

本 ADR 不改变 M0 已批准的代码；M0 仍保持“登录壳禁用登录”的现状。M1 实现时以契约测试先行更新 OpenAPI 与 Schema，再落地运行时。

## 决策

### 1. 密码哈希

- **不重新选型。** 沿用 M0 已锁定的 `pwdlib[argon2]==0.3.0` 与 `PasswordHash.recommended()`。
- 数据库永远不保存明文密码、不保存令牌；仅保存 `password_hash`。
- 哈希验证通过 `PasswordHash.recommended().verify(hash, password)`，不在应用代码中重新实现 Argon2 参数。

### 2. 令牌与会话模型

采用 **不透明 opaque access token + 服务端持久化 session**，不使用自包含 JWT：

| 维度 | 选择 | 原因 |
|---|---|---|
| Access token 形态 | 不透明随机字符串（`secrets.token_urlsafe(32)`），数据库索引 `token_hash` | 可即时撤销；不向客户端暴露任何业务字段；防止 token 被解析后绕过权限版本 |
| Access token 有效期 | 15 分钟（可由 `PCB_CDSO_ACCESS_TOKEN_TTL_SECONDS` 配置，默认 900） | 满足 PRD“短期有效”，且把权限版本检查交给服务端 |
| Refresh token 形态 | 不透明随机字符串，关联 `session_id`；只在 `POST /auth/refresh` 流程中接受 | 满足 PRD“刷新令牌可撤销” |
| Refresh token 有效期 | 14 天（`PCB_CDSO_REFRESH_TOKEN_TTL_SECONDS` 默认 1209600） | 试开发期合理，避免频繁重登 |
| 会话存储 | MySQL 表 `auth_sessions`（迁移 `0002` 中冻结） | 单机部署无需 Redis 作为会话源；Redis 留给 Celery broker |
| 撤销机制 | 令牌 lookup 命中 `revoked_at IS NOT NULL` 或 `user.is_active = false` 即判定无效 | 单一权威路径，账号停用与会话撤销同一语义 |

### 3. 数据模型（在迁移 `0002` 中具体落地）

- `users` 表已存在（迁移 `0001`）；新增 `locale`、`theme`、`password_changed_at` 列以支持 PRD“主题/语言保存到账号”和密码重置审计。
- 新增 `auth_sessions(id, user_id FK, token_hash UNIQUE, refresh_token_hash UNIQUE, issued_at, last_seen_at, expires_at, revoked_at, created_at)`。
- 新增 `access_tokens` 视为 `auth_sessions` 的活跃记录派生；为简化试开发，不在单独表中保存短期 access token，而是用同一 session 行的 `token_hash` 字段表达当前 access token，刷新时**轮换 token_hash**（旧 token 立即失效）。
  - 备选：分离 `access_tokens` 与 `refresh_tokens` 两表。未采用原因：M1 无需检测 token 重用攻击的复杂场景，轮换模型更简单且同样满足“可撤销”。

### 4. 依赖注入与 actorId 来源

- 实现一个 FastAPI 依赖 `get_actor()`：从 `Authorization: Bearer <opaque>` 解析 token，查 `auth_sessions` + `users`，校验 `is_active` 与 `expires_at`，构造 `ActorContext(actor_id, role, locale, theme)`。
- `ActorContext` 是唯一被业务代码消费的认证抽象。`actorId` 字段一律由 `ActorContext.actor_id` 注入，请求体中的 `actorId` 字段必须被**忽略且记入审计**（M1 Feature Spec 第 45 行要求“请求体中的同名值不得覆盖认证身份”）。
- 403 与 404 的区分严格遵循 M1 Feature Spec 第 103 行：先以 `owner_id + resource_id` 同 scope 查找；scope 内不存在与其他 owner 已存在均返回不可区分的 `404 NOT_FOUND`；已定位但角色写权限不足才返回 `403 FORBIDDEN`。

### 5. 账号停用与会话撤销

- `ADMIN` 停用 `ENGINEER`（或反向）时，在同一事务把 `users.is_active = false` 并把该用户所有 `auth_sessions.revoked_at` 置为 now。
- `get_actor()` 每次请求都重新读取 `is_active`，停用立即生效，无需等 token 过期。
- 登出（`POST /auth/logout`）撤销当前 session；`POST /auth/logout-all` 撤销当前用户全部 session（M1 可只实现前者，后者留 M5/M6）。

### 6. 审计

- 登录成功/失败、刷新、登出、停用/恢复、密码重置各产生一条 `audit_events`。
- 失败登录不得在 payload 中区分“用户不存在”与“密码错误”；只记 `outcome=FAILED` 与脱敏原因。
- 审计 payload 不保存 token、密码或完整 refresh token，只保存 token 的不可逆摘要。

## 备选方案

| 方案 | 优点 | 缺点 | 未采用原因 |
|---|---|---|---|
| JWT（自包含 access token） | 无状态、可水平扩展；生态成熟 | 撤销困难，需要黑名单或短 TTL + refresh；权限版本变更后旧 token 仍可能被解析 | 单机部署无扩展收益；PRD 强调“可撤销”，opaque token 更直接；引入 JWT 库与 PRD“不并行两套方案”冲突 |
| Redis 存 session | 读写更快 | M0 已把 Redis 作为 Celery broker；会话作为权威源放在 cache 违反“Redis result backend 不作为长期事实源”（ADR-0001 结果章节） | MySQL 单机已足够 |
| 分离 access_tokens/refresh_tokens 两表 | 可独立过期、独立撤销 | M1 无 token 重用攻击需求；多一张表增加迁移和测试复杂度 | 轮换 token_hash 的单表模型已满足 PRD |
| 服务端 Session Cookie（无 bearer） | 浏览器天然支持 | PRD 第 966 行明确 `/auth` 返回 access token；前端要支持跨 Tab、SSE/轮询，bearer 更一致；CSRF 防护成本反而更高 | 与 PRD API 形态不符 |

## 后果

- 正面影响：撤销语义单一权威；账号停用立即生效；权限版本可由服务端每次请求重新评估；无需引入 JWT 库，依赖面更窄；与 M1 Feature Spec 的 actorId 注入要求天然吻合。
- 负面影响与成本：每次请求一次数据库 lookup（可通过 `auth_sessions` 索引 + 单机 MySQL 缓解）；access token 轮换要求前端在 401 时主动 refresh（M1 只需冻结接口，前端 M2 落地）；撤销的 session 仍在表内，需要后续清理任务（M6 部署收口时增加保留窗口）。
- 新增风险：opaque token 一旦泄露在 TTL 内有效；缓解为短 TTL（15 min）+ HTTPS + `HttpOnly`/`Secure` cookie 仅在需要时使用、bearer 由前端内存持有。

## 迁移与回滚

- **采用步骤：**
  1. 本 ADR approved。
  2. 契约任务包扩展 OpenAPI（`/auth/login`、`/auth/refresh`、`/auth/logout`、`/auth/me`）和 JSON Schema。
  3. 迁移 `0002` 新增 `auth_sessions` 表并扩展 `users` 列。
  4. 实现任务包按 TDD 落地 `get_actor` 依赖与四个端点。
- **兼容窗口：** M0 登录壳仍禁用登录；本 ADR 不破坏 M0 运行时。M1 验收前前端登录按钮保持禁用样式。
- **回滚条件：** 若 opaque token 在 30 区域并发下成为瓶颈，且证据表明 MySQL 是瓶颈（而非查询缺失索引），才考虑引入 Redis session 或 JWT。回滚必须通过新 ADR，不在 M1 期内临时切换。
- **不可逆部分：** `users` 表新增列一旦合并并在 bootstrap 写入，向后兼容由 Alembic downgrade 保证；opaque token 字段语义变更需新迁移。

## 受影响契约

- `contracts/openapi/openapi.json`：新增 `/auth/login`、`/auth/refresh`、`/auth/logout`、`/auth/me` 路径与 `ActorContext`、`AuthSession` schema。
- `contracts/schemas/`：新增 `actor-context.schema.json`、`auth-session.schema.json`；扩展 `error.schema.json` 的 `UNAUTHENTICATED`、`FORBIDDEN` 稳定错误码。
- `services/api/alembic/versions/0002_*.py`：新增 `auth_sessions`、扩展 `users` 列。
- `services/api/src/pcb_cdso/http/auth.py`（新文件）：`get_actor` 依赖与端点。
- `services/api/tests/`：契约测试、集成测试（停用即撤销、404/403 区分、伪造 actorId 忽略）。
- `docs/specs/m1/identity-and-ownership.md`（未来 Feature Spec，追踪 P0_02）：引用本 ADR 作为会话/撤销权威。
- `docs/testing/plans/M1-test-plan.md`：增加 auth 相关测试用例（M1 当前计划聚焦 project-weather-dispatch，auth 测试待 identity spec 批准后补充）。

## 验证证据

本 ADR 于 2026-07-21 由技术负责人批准为 `approved`，依据：

1. opaque token 模型与 M5 SSE/轮询选型无冲突——SSE/轮询与认证 token 形态正交，bearer token 在两种通道下均工作；若 M5 落地时发现冲突，通过新 ADR 处理。
2. `pwdlib[argon2]==0.3.0` 已在 M0 `services/api/src/pcb_cdso/bootstrap.py` 成功用于首个 ADMIN 哈希（M0 acceptance `integration.txt` 证据 `ADMIN=1`）。
3. `auth_sessions` 表索引方案在 `docs/architecture/m1-migration-0002-design.md` 第 3 节冻结；30 并发基准在 M1 Task 2.7 性能测试中产出，若超门限通过新 ADR 处理（见“迁移与回滚”）。

`approved` 状态允许 Contract Agent 与 Implementer 引用本 ADR 作为运行时编码依据；任何与“决策”章节冲突的实现必须停下回报（AGENTS.md 第 2 条）。
