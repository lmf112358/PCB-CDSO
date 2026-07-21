# M1 项目创建与气象任务可靠派发 Feature Spec

| 属性 | 值 |
|---|---|
| 状态 | approved |
| 版本 | 1.0.0 |
| Owner | M1 Backend / Project Domain |
| Milestone | M1 |
| Issue | PRD v0.6 rebaseline Task 3 |
| PRD 追踪 | P0_02、P0_03；P0_07 的 M1 前置契约；6.3、7.5、验收剧本 7 |

## 用户结果

`ENGINEER` 或 `ADMIN` 首次确认产品模板与地理信息后，系统原子创建项目、不可变快照和一条可恢复的气象历史抓取任务；成功响应立即给出持久化的 `weatherTaskId`，不等待 dispatcher、Worker 或真实气象下载。

## 范围与非目标

### 包含

- `CreateProject` 命令和 `POST /projects` 的字段、权限、幂等、事务及响应契约。
- Project、不可变模板/会话快照、Task、OutboxEvent 的同一 MySQL 事务提交。
- fake dispatcher 对 Outbox 的至少一次派发、失败重试和 Worker 去重边界。
- 项目和任务的 owner、`ENGINEER`/`ADMIN` 可见性、审计、错误及并发边界。

### 不包含

- 连接真实气象 Provider，或执行定位、请求、下载、清洗、连续性校验、入库。
- 三年气象数据、CSV 兜底、current 批次发布、城市变更后的 revision 失效；这些由 M4 交付。
- 对话工具卡、右下角任务坞、Composer 和刷新/重登恢复 UI；这些由 M2 验证，最终跨里程碑验收再验证其与本规格持久化 task id 的一致性，不属于 M1 gate。
- 完整八阶段问答、静态计算、仿真和预测。

## 命令、领域词汇与不变量

`CreateProject` 的输入固定为：

| 字段 | 规则 |
|---|---|
| `name` | 必填，去除首尾空白后 1–120 个 Unicode 字符 |
| `templateVersionId` | 必填，必须指向已发布且当前 actor 可使用的模板版本 |
| `countryCode` | 必填，ISO 3166-1 alpha-2 大写代码 |
| `adminArea` | 必填，去除首尾空白后 1–120 个字符 |
| `city` | 必填，去除首尾空白后 1–120 个字符 |
| `timezone` | 必填，必须是服务端 tzdata 可识别的 IANA 时区；不得用 UTC 偏移替代 |
| `idempotencyKey` | 必填，客户端生成的 1–128 个可打印 ASCII 字符；仅在 actor 范围内唯一 |
| `actorId` | 必填，由认证上下文注入；请求体中的同名值不得覆盖认证身份 |

稳定术语和不变量：

- 新项目的 `inputRevision` 恒为 `1`。
- 不可变快照至少冻结所选 template version 的完整业务内容、版本标识以及首轮确认输入；创建后只能读，不能原地更新。
- Task 类型恒为 `WEATHER_HISTORY_FETCH`，初始状态恒为 `DISPATCH_PENDING`；Task 在事务内生成稳定 `taskId`。
- OutboxEvent 类型恒为 `WeatherFetchRequested`，payload 至少含 `eventId`、`taskId`、`projectId`、`inputRevision=1`、`taskType=WEATHER_HISTORY_FETCH`、标准化地理字段和 `occurredAt`。
- 命令去重键为 `actorId + idempotencyKey`；幂等记录冻结 `canonicalRequestHash`。canonical payload 只含规范化后的 `name`、`templateVersionId`、`countryCode`、`adminArea`、`city`、`timezone`：字符串按 Unicode NFC、去首尾空白，`countryCode` 大写，IANA timezone 使用服务端 canonical 标识；字段按上述固定顺序作 UTF-8 JSON 后计算 SHA-256，不含 `actorId` 和 `idempotencyKey`。Worker 业务去重键为 `projectId + inputRevision + WEATHER_HISTORY_FETCH`。两类键均由数据库唯一约束保证。
- 幂等记录状态为 `IN_PROGRESS|SUCCEEDED`，并与 Project、不可变快照、Task、OutboxEvent 在同一个 MySQL 事务中写入。唯一约束决定 winner；loser 等待 winner 的短事务结束后读取结果：相同 hash 返回原聚合，不同 hash 返回冲突。pre-commit 确定失败必须回滚幂等记录和四组业务记录，不留占坑。
- 成功命令必须在同一个 MySQL 事务中创建幂等记录及四个逻辑记录组：Project、不可变快照、Task、OutboxEvent。任一事务写入在 commit 前确定失败，所有记录均为零行。commit outcome unknown 不得断言零行或擅自重建，客户端必须使用同一键重放以解析最终结果。
- dispatcher 不得在事务提交前发布；Task 的存在不依赖 dispatcher 可用性。
- broker publish 是至少一次语义。publish 成功后，dispatcher 必须在另一个单一 MySQL 确认事务内同时写 Outbox 的 `dispatchedAt/attemptCount/lastAttemptAt` 元数据并将 Task 以 compare-and-set 从 `DISPATCH_PENDING` 转为 `QUEUED`；任一确认写或 commit 失败，两者均不得标记完成。
- reconciler 扫描“Outbox 未 dispatched 但 Task 已 QUEUED”或“Outbox 已 dispatched 但 Task 仍 DISPATCH_PENDING”等不一致，按 event/task id 对账；不能证明 broker 已确认时重发同一事件，依赖 Worker 持久化去重保证安全。

## 正常流程

1. API 从认证会话取得 `actorId`，验证 `ENGINEER`/`ADMIN` 角色、字段格式、模板发布状态和模板可见性，并计算 canonical request hash。
2. 服务端以 `actorId + idempotencyKey` 竞争幂等记录。winner 在业务事务中创建记录；loser 等待后读取：同 hash 且 `SUCCEEDED` 返回原始结果，不同 hash 返回 `409`。
3. 在一个 MySQL 事务内创建幂等记录、Project（`ownerId=actorId`，`ADMIN` 代建时仍显式记录 owner）、不可变快照、`DISPATCH_PENDING` Task 和 `WeatherFetchRequested` OutboxEvent，并将幂等记录置为 `SUCCEEDED` 且保存结果引用。
4. 提交成功后返回 `201`；响应包含完整项目摘要、`inputRevision: 1`、不可变快照标识和 `weatherTaskId`。重复同键响应可为 `200`，响应实体的三个标识必须与首次调用一致。
5. fake dispatcher 只读取已提交且未确认派发的 OutboxEvent。broker publish 成功后，用单一确认事务原子更新 Outbox 派发/attempt 元数据和 Task `DISPATCH_PENDING -> QUEUED`；确认失败则回滚两者，由 dispatcher/reconciler 重发或对账。
6. fake Worker 按 Worker 业务去重键消费，并以真实 MySQL probe 验证可恢复执行协议；不得访问真实 Provider、下载或伪造气象数据。

## 状态清单

| 状态 | 进入条件 | 允许操作 | 退出条件 |
|---|---|---|---|
| `DISPATCH_PENDING` | 项目事务提交 | 查询、dispatcher 重试 | fake dispatcher 确认发布后进入 `QUEUED` |
| `QUEUED` | Outbox 已发布且 Task 条件更新成功 | 查询、重复消息去重 | fake Worker 认领后进入 `RUNNING` |
| `RUNNING` | fake Worker 取得可过期 lease；不得预写 `SUCCEEDED`/`DONE` | 查询、lease 到期后重领 | probe effect、execution `SUCCEEDED` 与 Task CAS `RUNNING -> SUCCEEDED` 三项原子提交，或模拟失败 |
| `SUCCEEDED` | probe effect、execution 完成状态和 Task CAS 已在同一事务提交 | 查询、幂等重投复用 | 终态；重投不得倒退状态 |
| `FAILED` | fake Worker 遇到不可恢复的模拟错误 | 查询、按策略重试 | 新一次合法重试后进入 `QUEUED` |
| `CANCELLED` | 授权操作取消尚未完成任务 | 查询 | 终态 |
| `STALE` | 后续里程碑判定 revision 已过期 | 查询 | 终态，不得发布 current 数据 |

允许的 M1 主路径是 `DISPATCH_PENDING -> QUEUED -> RUNNING -> SUCCEEDED|FAILED`。状态更新必须使用当前状态条件或版本列做 compare-and-set；重复 dispatcher/Worker 消息不得倒退状态或产生第二条业务 Task。

## 失败与恢复

| 触发 | HTTP/业务状态 | 用户可见语义 | 写入 | 恢复动作 |
|---|---|---|---|---|
| 字段格式、时区或模板无效 | `422 VALIDATION_FAILED` | 指明字段和稳定错误码 | 零行 | 修正输入后用新键重试；未提交请求可复用原键 |
| 未认证 | `401 UNAUTHENTICATED` | 需要登录 | 零行 | 重新认证 |
| 角色不是 `ENGINEER`/`ADMIN` | `403 FORBIDDEN` | 无权执行 | 零行 | 使用有权账号 |
| 同一 actor、同一键、相同规范化输入 | `200` 幂等重放 | 返回原项目和原 task id | 无新增行 | 无需恢复 |
| 同一 actor、同一键、不同规范化输入 | `409 IDEMPOTENCY_CONFLICT` | 该键已绑定其他请求 | 无新增行 | 使用新键提交 |
| 并发相同 hash | winner `201`，loser 等待后 `200` | 全部观察同一结果 | 仅一个幂等记录和一套四组记录 | loser 读取 winner 结果 |
| 并发不同 hash | winner `201`，loser 等待后 `409` | 键已绑定 winner 请求 | 仅 winner 聚合 | loser 使用新键 |
| 事务在 commit 前确定失败 | `503 TRANSACTION_FAILED` | 创建未完成，可安全重试 | 幂等记录及四组均零行 | 保持原键重试；不得返回资源 id |
| commit 响应断连、结果未知 | `503 COMMIT_OUTCOME_UNKNOWN` | 结果待解析 | 可能零行或完整一套，禁止假定 | 同一 actor/key/hash 重放或查询；最终只能观察一个聚合 |
| dispatcher 不可用、超时或发布失败 | Task 保持 `DISPATCH_PENDING` | 等待任务调度 | 已提交四组记录保留 | 指数退避重试同一 OutboxEvent；不新建 Task |
| publish 成功但确认事务任一写/commit 失败 | Outbox 未完成且 Task 保持 `DISPATCH_PENDING` | 可恢复等待调度 | 确认事务两项均回滚 | 重发同一事件；reconciler 对账，不新建 Task |
| 历史缺陷造成 Outbox/Task 状态不一致 | 持久化现状 | 等待系统对账 | 不新增业务记录 | reconciler 按 event/task id 修复或重发 |
| 状态 compare-and-set 冲突 | 当前持久化状态 | 返回/记录已胜出的状态 | 不覆盖 | 重新读取；不得状态倒退 |

## 权限、审计与并发规则

- `ENGINEER` 只能创建归属自己的项目，并查询自己的 Project/Task；`ADMIN` 可创建、查询和治理任意项目。列表在数据库层按 owner 过滤并返回 `200`。`ENGINEER` 单项查询必须以 `owner_id + resource_id` 同 scope 查找；无论该 id 属于其他 owner 还是随机不存在，均返回 `404 NOT_FOUND`。`ADMIN` 查询或 owner scope 内确实不存在也返回同一 `404`。
- 所有 `404` 使用相同 error envelope、message 与 timing class；不得先按全局 resource id 查出存在性再做授权。应用日志和审计不得记录被拒资源的 payload、地理字段、task 状态、真实 owner 或完整幂等键；跨 owner 已存在 id 与随机 id 的外部响应及调用者可见日志必须不可区分。内部只可记录 requestId、actorId 和请求 id 的不可逆摘要。
- 审计至少记录 `PROJECT_CREATE_REQUESTED`、`PROJECT_CREATED`、`PROJECT_CREATE_REPLAYED`、`PROJECT_CREATE_FAILED`、`WEATHER_DISPATCH_ATTEMPTED`、`WEATHER_DISPATCH_SUCCEEDED`、`WEATHER_DISPATCH_FAILED` 和 `TASK_STATE_CHANGED`。每条含 `requestId`、`actorId`、`projectId/taskId`（存在时）、幂等键的不可逆摘要、前后状态、时间和结果；不得记录认证密钥或完整 idempotencyKey。
- 唯一约束冲突是正常并发控制路径，不得转化为第二个 Project、Task 或 OutboxEvent。除 commit outcome unknown 外，事务隔离与重试保证完整提交或零行；unknown 必须由同键重放解析。
- Outbox claim 必须支持多 dispatcher 竞争；租约/行锁过期后可再次认领。重复投递是允许的，重复业务执行和重复 Task 不允许。

## API、数据与版本

- `POST /projects` 是 `CreateProject` 的 HTTP 映射。首次创建返回 `201`；幂等重放返回 `200`；二者响应 schema 相同。
- 响应最小结构为 `{ project, inputRevision: 1, snapshotIds, weatherTaskId }`，其中 `project.id`、`snapshotIds`、`weatherTaskId` 均来自已提交记录。
- `GET /tasks/{taskId}` 和 `GET /tasks?projectId=&activeOnly=` 返回持久化状态；M2 必须用这里的同一 `weatherTaskId` 呈现工具卡与任务坞。
- 数据库迁移须为命令去重键、Worker key 和 Worker execution record 建立持久化唯一约束，为未派发/不一致 Outbox 扫描建立索引，并保留 Task 状态版本/更新时间。

M1 fake Worker 的可验证 effect 固定为 MySQL 表 `weather_dispatch_probe(effect_key UNIQUE, project_id, input_revision, task_type, created_at)`；`effect_key` 是 `projectId + inputRevision + WEATHER_HISTORY_FETCH`。执行协议如下：

1. 领取只写可过期 lease/`RUNNING`，不得预先提交会阻断重试的 `DONE` 或 `SUCCEEDED` execution。
2. Worker 开启 MySQL 事务，以 `effect_key` 幂等 upsert probe 行、把对应 execution 更新为 `SUCCEEDED`，并以 compare-and-set 将 Task 从 `RUNNING` 更新为 `SUCCEEDED`；三项一起 commit 或一起回滚。CAS 只接受 `RUNNING`，若 Task 已为 `SUCCEEDED` 则验证同一 effect/execution 后幂等复用；任何重投不得把 Task 倒退到 `RUNNING` 或其他状态。
3. effect 前崩溃时没有 probe 行，lease 到期后的重投必须重新执行并提交一行 effect。
4. effect 事务提交后、broker ack 前崩溃时，重投通过唯一 `effect_key` 读到/复用原 probe、`SUCCEEDED` execution 和 `SUCCEEDED` Task；probe 始终只有一行，Task 不执行倒退转换。
5. 该 probe 仅证明 M1 fake dispatch 的数据库内幂等执行。M4 真实外部 Provider 必须定义自身的请求键、回执与补偿协议；本规格不承诺任意外部副作用恰好一次。
- 当前重基线不提前修改 OpenAPI 或运行时代码；M1 实现时必须先以契约测试更新 OpenAPI 和 Schema。

## 可观察性

- 指标至少包含创建成功/失败/重放数、事务耗时、`DISPATCH_PENDING` 数量与最老等待时长、派发尝试/成功/失败数、重复消息数和非法状态转换数。
- 日志以 `requestId`、`eventId`、`projectId`、`taskId` 关联 API、事务、dispatcher 和 Worker；错误保存稳定 `errorCode`、可重试标志及脱敏原因。
- 告警边界：持续增长的最老 `DISPATCH_PENDING` 时长或派发失败率触发运维告警，但不得删除、失败化或重建原 Task。

## 验收场景

1. **成功：** Given `ENGINEER` 有已发布模板，When 提交合法命令，Then 幂等记录与四组业务记录原子提交，响应为 `inputRevision=1` 且 `weatherTaskId` 对应 `DISPATCH_PENDING` Task。
2. **原子回滚：** Given 分别注入业务写点和 commit 前确定故障，When 创建项目，Then 幂等记录与四组记录均为零行；Given commit 回包断连，Then 不断言零行，以同键重放解析为原结果或一次安全新建。
3. **幂等与并发：** Given 同一 actor/key，When 相同或不同 hash 并发，Then winner 唯一，相同 hash loser `200`，不同 hash loser `409`；确定失败后同键可重试且无占坑。
4. **作用域：** Given 两个 `ENGINEER` 使用相同 key，When 各自创建，Then 因 actorId 不同可分别成功且互不可见；`ADMIN` 可见两者。
5. **派发恢复：** Given dispatcher 不可用，When 项目已提交，Then Task 保持 `DISPATCH_PENDING` 且查询可见；恢复后复用原 task id 进入 `QUEUED`。
6. **确认原子性：** Given publish 已成功，When Outbox 元数据写或 Task 转态写失败，Then 确认事务两项均回滚并可重发；不一致数据由 reconciler 对账。
7. **Worker 重投：** Given effect 前崩溃或三项完成事务提交后/ack 前崩溃，When 再次消费，Then 真实 MySQL 的 `weather_dispatch_probe` 按唯一 effect key 恰有一行、execution 与 Task 均为 `SUCCEEDED`；前者重做，后者复用且 Task 不倒退。
8. **2 秒契约：** Given API 请求开始时间，When 创建成功，Then 2 秒内 `GET /tasks/{taskId}` 或过滤列表可返回与响应完全相同的持久化 task id；该 M1 gate 不涉及 UI、dispatcher、Worker 或下载完成。
9. **权限：** Given `ENGINEER` B，When 列表查询、显式查询 A 的已存在资源及随机不存在 id，Then 列表为 `200` 且过滤，两种单项请求均为不可区分的 `404`；`ADMIN` 可见授权资源，owner/`ADMIN` 查询不存在资源仍返回相同 `404`。

## 测试映射

| 验收条件 | 测试层级 | 测试文件/fixture | 门禁 |
|---|---|---|---|
| 事务四组原子性 | integration | `tests/integration/test_project_weather_transaction.py` | required |
| 幂等、并发与唯一约束 | integration | `tests/integration/test_project_weather_idempotency.py` | required |
| HTTP 输入、响应和错误码 | contract | `tests/contracts/test_create_project_contract.py` | required |
| dispatcher 失败与重复投递 | integration | `tests/integration/test_weather_outbox_dispatch.py` | required |
| `ENGINEER`/`ADMIN` 过滤和审计 | integration | `tests/integration/test_project_task_authorization.py` | required |
| 2 秒 API/GET tasks 同 task id 可见 | API/performance | `tests/performance/test_initial_weather_task_visibility.py` | required |

## 阻断审批的问题

无。正式 Provider、凭据、限额和许可不影响 M1 fake dispatcher 契约，由 M4 规格冻结。
