# M1 迁移 0002 设计草案（认证、项目、气象任务、Outbox、幂等、Probe）

| 属性 | 值 |
|---|---|
| 状态 | draft |
| 目标迁移文件 | `services/api/alembic/versions/0002_m1_project_weather_dispatch.py` |
| down_revision | `0001_users_audit` |
| 适用 Feature Spec | `docs/specs/m1/project-weather-dispatch.md` v1.0.0 |
| 适用 ADR | ADR-0001（应用栈）、ADR-0002（认证与会话）|
| 用途 | 为 Contract Agent 迁移任务包提供设计意图；不是已合并迁移 |

本文档**不是迁移**。已冻结的迁移是 `services/api/alembic/versions/0001_users_audit.py`。Contract Agent 落地时以本文档为输入，最终迁移以 PR 合并后的文件为准，并配 forward + downgrade 与兼容窗口说明（AGENTS.md 第 6 条）。

## 1. 设计原则

- 单一迁移 `0002` 覆盖 M1 全部新表与列，避免多个半成品迁移在 M1 期内互相依赖。
- 所有表使用 `String(36)` UUID 主键，与 `0001` 的 `users.id` 一致。
- 所有时间列使用 `DateTime(timezone=True)` + `server_default=func.now()`，与 `0001` 一致。
- 状态列用 `CheckConstraint` 而非 native enum（与 `0001` 的 `ck_users_role` 一致），避免 MySQL enum 升级痛点。
- 唯一约束和索引命名固定，供 reconciler、性能测试和治理脚本引用。
- 所有外键显式声明，业务表 owner 引用 `users.id`，且 `ondelete` 策略明确。

## 2. 表清单与不变量

### 2.1 扩展 `users`（ADD COLUMN）

```
ALTER TABLE users
  ADD COLUMN locale VARCHAR(8) NOT NULL DEFAULT 'zh-CN',
  ADD COLUMN theme VARCHAR(8) NOT NULL DEFAULT 'light',
  ADD COLUMN password_changed_at DATETIME(0) NULL,
  ADD CONSTRAINT ck_users_locale CHECK (locale IN ('zh-CN','en-US')),
  ADD CONSTRAINT ck_users_theme CHECK (theme IN ('light','dark'));
```

- 默认值保证存量行（M0 bootstrap admin）非空，兼容窗口无需回填脚本。
- `password_changed_at` 初始 NULL；首次密码变更后写入，用于后续 token 失效策略（M1 暂不强制）。

### 2.2 `auth_sessions`（ADR-0002）

```
CREATE TABLE auth_sessions (
  id                   VARCHAR(36) NOT NULL,
  user_id              VARCHAR(36) NOT NULL,
  token_hash           VARCHAR(128) NOT NULL,        -- sha256(token) hex
  refresh_token_hash   VARCHAR(128) NOT NULL,
  issued_at            DATETIME(0) NOT NULL,
  last_seen_at         DATETIME(0) NOT NULL,
  expires_at           DATETIME(0) NOT NULL,         -- refresh token 过期时间
  revoked_at           DATETIME(0) NULL,
  created_at           DATETIME(0) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_auth_sessions_token_hash (token_hash),
  UNIQUE KEY uq_auth_sessions_refresh_token_hash (refresh_token_hash),
  KEY ix_auth_sessions_user_id_expires_at (user_id, expires_at),
  CONSTRAINT fk_auth_sessions_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

不变量：

- `token_hash` 与 `refresh_token_hash` 是 sha256 hex，不存原 token。
- 账号停用同一事务把 `users.is_active=false` 并 `UPDATE auth_sessions SET revoked_at=NOW() WHERE user_id=? AND revoked_at IS NULL`。
- 撤销语义：`revoked_at IS NOT NULL` 或 `users.is_active=false` 或 `NOW() > expires_at` 任一为真即 token 无效。
- 轮换模型：refresh 成功时在同一事务 `UPDATE` 当前行 `token_hash`/`refresh_token_hash`/`last_seen_at`/`issued_at`，旧 token 立即失效。

### 2.3 `templates` 与 `template_versions`（最小骨架，仅满足 M1 project-weather-dispatch）

> 注意：完整的模板生命周期（草稿/发布/归档、双语、工序、规则、系数）由 `docs/specs/m1/template-lifecycle.md`（未来 Feature Spec，P0_03）冻结。M1 project-weather-dispatch 只需“已发布模板版本可被引用”的最小骨架，Contract Agent 不应在本迁移中提前实现完整模板领域。

```
CREATE TABLE templates (
  id            VARCHAR(36) NOT NULL,
  slug          VARCHAR(64) NOT NULL,          -- 'hdi' | 'multilayer' | 'ic-substrate'
  display_name  VARCHAR(120) NOT NULL,         -- 双语在 template_versions.payload
  created_at    DATETIME(0) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_templates_slug (slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE template_versions (
  id                VARCHAR(36) NOT NULL,
  template_id       VARCHAR(36) NOT NULL,
  version_label     VARCHAR(32) NOT NULL,       -- 'v1.0.0'
  status            VARCHAR(16) NOT NULL,        -- 'DRAFT' | 'PUBLISHED' | 'ARCHIVED'
  payload           JSON NOT NULL,               -- 完整业务内容快照
  published_at      DATETIME(0) NULL,
  created_at        DATETIME(0) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_template_versions_template_version (template_id, version_label),
  KEY ix_template_versions_status (status),
  CONSTRAINT ck_template_versions_status CHECK (status IN ('DRAFT','PUBLISHED','ARCHIVED')),
  CONSTRAINT fk_template_versions_template FOREIGN KEY (template_id) REFERENCES templates(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

- M1 只用 `status='PUBLISHED'` 的 version；Contract Agent 落地 seed 时只发布 HDI v1.0.0 一条（其他模板由 P0_03 spec 后续补）。
- `payload` 是不可变业务内容；M1 不校验其内部结构（留给 P0_03 spec 与 P0_13 demo seeds）。

### 2.4 `projects`

```
CREATE TABLE projects (
  id                  VARCHAR(36) NOT NULL,
  name                VARCHAR(120) NOT NULL,        -- 规范化后存储
  owner_id            VARCHAR(36) NOT NULL,
  template_version_id VARCHAR(36) NOT NULL,
  country_code        CHAR(2) NOT NULL,
  admin_area          VARCHAR(120) NOT NULL,
  city                VARCHAR(120) NOT NULL,
  timezone            VARCHAR(64) NOT NULL,         -- IANA canonical
  status              VARCHAR(16) NOT NULL,         -- 'ACTIVE' | 'ARCHIVED' | 'SOFT_DELETED'
  input_revision      INT NOT NULL,                 -- M1 新建恒为 1
  ownership_version   INT NOT NULL DEFAULT 1,       -- 转交递增
  created_at          DATETIME(0) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at          DATETIME(0) NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  archived_at         DATETIME(0) NULL,
  PRIMARY KEY (id),
  KEY ix_projects_owner_status (owner_id, status),
  KEY ix_projects_template_version (template_version_id),
  CONSTRAINT ck_projects_country_code CHECK (country_code REGEXP '^[A-Z]{2}$'),
  CONSTRAINT ck_projects_status CHECK (status IN ('ACTIVE','ARCHIVED','SOFT_DELETED')),
  CONSTRAINT ck_projects_input_revision CHECK (input_revision > 0),
  CONSTRAINT fk_projects_owner FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE RESTRICT,
  CONSTRAINT fk_projects_template_version FOREIGN KEY (template_version_id) REFERENCES template_versions(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

不变量：

- `name`/`admin_area`/`city` 存储规范化后字符串（NFC、trimmed），原始字符串只在审计。
- `input_revision` M1 恒为 1；M4 城市变更时递增并使旧 task 失效。
- 软删除与归档是两个独立状态：归档可恢复，软删除 30 天窗口恢复（M1 仅冻结列，恢复逻辑由 P0_02/P0_03 spec）。

### 2.5 `idempotency_records`

```
CREATE TABLE idempotency_records (
  id                      VARCHAR(36) NOT NULL,
  actor_id                VARCHAR(36) NOT NULL,
  idempotency_key         VARCHAR(128) NOT NULL,
  scope                   VARCHAR(128) NOT NULL,         -- 'create_project'
  canonical_request_hash  CHAR(64) NOT NULL,             -- sha256 hex
  status                  VARCHAR(16) NOT NULL,          -- 'IN_PROGRESS' | 'SUCCEEDED'
  result_project_id       VARCHAR(36) NULL,
  result_weather_task_id  VARCHAR(36) NULL,
  result_snapshot_ids     JSON NULL,                     -- array of string
  created_at              DATETIME(0) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at            DATETIME(0) NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_idempotency_actor_key (actor_id, idempotency_key, scope),
  UNIQUE KEY uq_idempotency_actor_key_hash (actor_id, idempotency_key, scope, canonical_request_hash),
  KEY ix_idempotency_status_created (status, created_at),
  CONSTRAINT ck_idempotency_status CHECK (status IN ('IN_PROGRESS','SUCCEEDED')),
  CONSTRAINT fk_idempotency_actor FOREIGN KEY (actor_id) REFERENCES users(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

不变量（M1 Feature Spec 第 53–55 行）：

- `(actor_id, idempotency_key, scope)` 是命令去重键，唯一约束保证 winner 唯一。
- 同键不同 hash：靠应用层在拿到唯一键锁后比较 `canonical_request_hash`，冲突返回 `409`。
- `IN_PROGRESS` 是短暂中间态，pre-commit 失败必须回滚不留占坑（M1 测试 M1-I-001、M1-I-013 覆盖）。
- `result_*` 字段在 `SUCCEEDED` 后填充，供 loser 重放读取。

> 关于双重唯一约束：`(actor_id, key, scope)` 与 `(actor_id, key, scope, hash)` 在同 hash 时等价，但前者保证“键唯一”，后者允许应用层用 `INSERT ... ON DUPLICATE KEY` 检测 hash 变化。Contract Agent 实现时二选一，避免冗余索引；本草案列出两者是为了在评审中显式讨论。建议**只保留 `(actor_id, key, scope)`**，hash 比较由应用在事务内 `SELECT ... FOR UPDATE` 完成。

### 2.6 `tasks`（通用任务表，M1 存气象任务）

```
CREATE TABLE tasks (
  id               VARCHAR(36) NOT NULL,
  project_id       VARCHAR(36) NOT NULL,
  task_type        VARCHAR(64) NOT NULL,          -- 'WEATHER_HISTORY_FETCH'
  input_revision   INT NOT NULL,
  status           VARCHAR(24) NOT NULL,           -- 含 DISPATCH_PENDING/QUEUED/...
  status_version   INT NOT NULL DEFAULT 1,         -- CAS 用
  stage            VARCHAR(64) NULL,               -- 'LOCATE'/'REQUEST'/...（M4 细化）
  progress         INT NOT NULL DEFAULT 0,
  processed        INT NOT NULL DEFAULT 0,
  total            INT NOT NULL DEFAULT 0,
  error_payload    JSON NULL,
  retryable        BOOLEAN NOT NULL DEFAULT FALSE,
  lease_owner      VARCHAR(128) NULL,
  lease_expires_at DATETIME(0) NULL,
  created_at       DATETIME(0) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at       DATETIME(0) NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_tasks_worker_dedup (project_id, input_revision, task_type),
  KEY ix_tasks_status_updated (status, updated_at),
  KEY ix_tasks_project (project_id),
  CONSTRAINT ck_tasks_status CHECK (status IN (
    'DISPATCH_PENDING','QUEUED','RUNNING','SUCCEEDED','FAILED','CANCELLED','STALE'
  )),
  CONSTRAINT ck_tasks_task_type CHECK (task_type IN ('WEATHER_HISTORY_FETCH')),  -- M4 扩展
  CONSTRAINT fk_tasks_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

不变量：

- `(project_id, input_revision, task_type)` 是 Worker 业务去重键（M1 Feature Spec 第 53 行），保证重复投递不产生第二条 Task。
- `status_version` 用于 compare-and-set：`UPDATE ... WHERE id=? AND status_version=?`，更新时 `status_version=status_version+1`。
- 状态机转换严格按 M1 Feature Spec 第 71–80 行；非法转换由应用层 + `ck_tasks_status` 共同保护。
- M1 `stage`/`progress` 可留空或 0；六阶段进度由 M4 实现，M1 仅在 DISPATCH_PENDING 阶段停留。

### 2.7 `outbox_events`

```
CREATE TABLE outbox_events (
  id               VARCHAR(36) NOT NULL,
  event_type       VARCHAR(64) NOT NULL,           -- 'WeatherFetchRequested'
  task_id          VARCHAR(36) NOT NULL,
  project_id       VARCHAR(36) NOT NULL,
  input_revision   INT NOT NULL,
  payload          JSON NOT NULL,                  -- 含 eventId/taskId/projectId/inputRevision/geo/occurredAt
  dispatched_at    DATETIME(0) NULL,
  attempt_count    INT NOT NULL DEFAULT 0,
  last_attempt_at  DATETIME(0) NULL,
  created_at       DATETIME(0) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY ix_outbox_undispatched (dispatched_at, created_at),   -- reconciler 扫描
  KEY ix_outbox_task (task_id),
  CONSTRAINT ck_outbox_event_type CHECK (event_type IN ('WeatherFetchRequested')),
  CONSTRAINT fk_outbox_task FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE RESTRICT,
  CONSTRAINT fk_outbox_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

不变量（M1 Feature Spec 第 52、57–58 行）：

- `event_type='WeatherFetchRequested'`、`payload` 至少含 `eventId`、`taskId`、`projectId`、`inputRevision=1`、`taskType`、规范化地理字段、`occurredAt`。
- `dispatched_at IS NULL` 是未派发；reconciler 扫描此条件。
- 确认事务原子写 `dispatched_at`/`attempt_count`/`last_attempt_at` 并 CAS Task `DISPATCH_PENDING->QUEUED`。
- 不存 actor payload 中的敏感字段；actor 只在 `audit_events`。

### 2.8 `weather_dispatch_probe`（M1 fake Worker effect）

```
CREATE TABLE weather_dispatch_probe (
  effect_key      VARCHAR(160) NOT NULL,         -- projectId + '|' + inputRevision + '|' + taskType
  project_id      VARCHAR(36) NOT NULL,
  input_revision  INT NOT NULL,
  task_type       VARCHAR(64) NOT NULL,
  created_at      DATETIME(0) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (effect_key),
  KEY ix_weather_dispatch_probe_project (project_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

不变量（M1 Feature Spec 第 116–122 行）：

- `effect_key` 是 Worker 业务去重键的字符串化形式。
- `PRIMARY KEY(effect_key)` 保证 probe 恰有一行（M1 测试 M1-I-015A/B）。
- 该表**仅**证明 M1 fake dispatch 数据库内幂等执行；M4 真实 Provider 必须定义自身请求键，不复用本表语义。

### 2.9 `weather_task_executions`（Worker execution record，M1-I-015 需要）

```
CREATE TABLE weather_task_executions (
  id              VARCHAR(36) NOT NULL,
  task_id         VARCHAR(36) NOT NULL,
  attempt         INT NOT NULL,
  status          VARCHAR(16) NOT NULL,           -- 'IN_PROGRESS' | 'SUCCEEDED' | 'FAILED'
  started_at      DATETIME(0) NOT NULL,
  finished_at     DATETIME(0) NULL,
  error_payload   JSON NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_weather_exec_task_attempt (task_id, attempt),
  KEY ix_weather_exec_status (status),
  CONSTRAINT ck_weather_exec_status CHECK (status IN ('IN_PROGRESS','SUCCEEDED','FAILED')),
  CONSTRAINT fk_weather_exec_task FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

不变量：

- 与 `weather_dispatch_probe` 一起在 Worker effect 事务中原子提交（M1 Feature Spec 第 119 行）。
- `IN_PROGRESS` 不允许预写 `SUCCEEDED`（同上第 118 行）。
- 重投通过 `(task_id, attempt)` 唯一键复用既有 execution。

## 3. 索引与 reconciler 查询模式

reconciler 必须高效扫描的两类不一致（M1 Feature Spec 第 58、98 行）：

```sql
-- Outbox 未 dispatched 但 Task 已 QUEUED
SELECT oe.id FROM outbox_events oe
JOIN tasks t ON t.id = oe.task_id
WHERE oe.dispatched_at IS NULL AND t.status = 'QUEUED';

-- Outbox 已 dispatched 但 Task 仍 DISPATCH_PENDING
SELECT oe.id FROM outbox_events oe
JOIN tasks t ON t.id = oe.task_id
WHERE oe.dispatched_at IS NOT NULL AND t.status = 'DISPATCH_PENDING';
```

`ix_outbox_undispatched (dispatched_at, created_at)` 与 `ix_tasks_status_updated (status, updated_at)` 支持这两类扫描。

## 4. 兼容窗口与回滚

- **前向兼容：** `users` 新增列有 DEFAULT，存量行无需回填；新表对 M0 代码无影响（M0 不引用）。
- **downgrade：** `0002` 必须提供完整 `downgrade()`，按依赖反向 `DROP TABLE` 与 `DROP COLUMN`。`auth_sessions`/`projects` 等表 drop 时不应触发 `users` 数据丢失（外键 `ON DELETE CASCADE` 只在 `users` 删除时生效，反向 drop 子表不波及）。
- **不可逆部分：** 一旦 M1 实现写入 `auth_sessions`、`projects`、`tasks`，downgrade 会丢失业务数据。Acceptance Agent 在干净环境验证 downgrade 仅在空库场景下进行；生产回滚需先备份（M6 部署收口冻结备份/恢复脚本）。

## 5. 命名与治理

- 所有约束命名固定（`uq_*`、`ck_*`、`fk_*`、`ix_*`），供治理脚本与契约测试引用。
- `task_type` 与 `event_type` 的 CHECK 约束在 M1 只允许各自唯一值；M4 扩展时通过新迁移 `ALTER TABLE ... MODIFY CHECK`（MySQL 实际是 drop+recreate constraint），不允许 Agent 直接改 `0002`。
- 字符集统一 `utf8mb4`，与 M0 compose 一致。

## 6. 非目标

- 不实现模板生命周期完整领域（草稿编辑、双语、工序、规则、系数），由 P0_03 Feature Spec 后续迁移 `0003+` 处理。
- 不实现 M2 八阶段问答相关表（buildings/floors/zones/process_bindings/cooling_inputs/revisions）。
- 不实现 M3 静态计算结果表、M4 气象批次表、M5 analytics 物化视图、M6 导出任务表。
- 不引入 Redis 作为业务事实源（ADR-0001 结果章节）。

## 7. 已决策项（技术负责人 2026-07-21 采纳默认）

| 决策项 | 采纳结论 |
|---|---|
| `idempotency_records` 双重唯一约束 | 只保留 `(actor_id, idempotency_key, scope)`；移除 `(actor_id, key, scope, hash)` 冗余约束；hash 比较由应用层 `SELECT ... FOR UPDATE` 完成 |
| `weather_task_executions` 合并进 `tasks.stage` | 不合并；execution 与 task 是 1:N（多次重试）关系，独立表 |
| `projects.ownership_version` 在 M1 使用 | 保留列提前冻结避免后续 ALTER；M1 不写入（M1 不实现转交，P0_02 spec 后续） |
| `templates`/`template_versions` 最小骨架时机 | M1 迁移 0002 内落地最小骨架，否则 `projects.template_version_id` 无引用目标 |

Contract Agent 落地迁移 0002 时按上述结论执行；与第 1-6 节冲突时停下回报（AGENTS.md 第 2 条）。
