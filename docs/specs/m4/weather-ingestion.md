# M4 三年气象摄取与 current 安全发布 Feature Spec

| 属性 | 值 |
|---|---|
| 状态 | approved |
| 版本 | 1.0.0 |
| Owner | M4 Data / Calculation / API |
| Milestone | M4 |
| Issue | PRD v0.6 rebaseline Task 5 |
| PRD 追踪 | P0_07、P0_09；3.4、3.6、6.4、10 |

## 用户结果

工程师确认或修改项目城市后，系统可恢复地取得该 revision 对应的过去三年逐时气象，明确展示六阶段进度；只有质量通过且依赖仍为当前版本的批次才会原子发布为 `current`，三年历史仿真不会消费过期、缺时或旧城市数据。

## 范围与非目标

### 包含

- 真实气象 Provider 的定位、请求、下载、清洗、连续性校验和标准批次入库。
- Provider 失败的结构化错误、重试和使用同一标准 schema 的 CSV 恢复。
- 三年 UTC 窗口、实际小时数、UTC 整点唯一键、缺失/重复/越界质量门禁。
- Task 持久化单调进度、取消、重试、Worker 重投和容器重启恢复。
- 城市变更的 `inputRevision`、旧任务失效、新任务创建及旧结果防覆盖。
- 带完整依赖指纹的 `current` 原子发布，以及三年历史仿真只消费质量通过的 current 批次。
- Owner/`ADMIN` 权限、脱敏审计、错误恢复和运行可观察性。

### 不包含

- 气象准确度 SLA、真实生产数据校准、前馈控制或水蓄冷计算。
- 对外部 Provider 请求、计费或回执承诺 exactly-once；M4 只保证本地任务执行、标准行入库和 current 发布幂等。
- 移动端、任务坞组件实现、静态计算或结果中心；M2 负责用同一 Task 镜像进度，M5 负责结果展示。
- OpenAPI、Schema、迁移或运行时代码的提前实现；实现阶段必须遵循契约优先流程。

## 领域词汇与不变量

- Task 类型恒为 `WEATHER_HISTORY_FETCH`，业务执行键为 `projectId + inputRevision + taskType`；一次重试创建独立 attempt，但不得创建第二个同 revision Business Task。Business Task 保存单调递增的 `retryEpoch` 和指向当前 attempt 的 `currentAttemptId`，并将该 attempt 的 status/stage/stageProcessed/stageTotal/overallPercent/error 镜像给 API/UI；历史 attempt 状态保持不可变可查询。
- Provider attempt 严格执行 `LOCATE -> REQUEST -> DOWNLOAD -> CLEAN -> VALIDATE -> STORE`；CSV attempt 从 `CLEAN -> VALIDATE -> STORE` 开始，必须为 `LOCATE/REQUEST/DOWNLOAD` 写入 `SKIPPED` 审计原因，但不得伪造这三个阶段的活动进度。成功只允许在 STORE transaction 已确认、随后 publish transaction 完成后进入 `SUCCEEDED`。status/stage/stageProcessed/stageTotal/overallPercent 的单调性以同一 `attemptId + retryEpoch` 为边界：阶段 rank、阶段内 `stageProcessed`、派生 `overallPercent` 和 attempt `version` 单调，乱序、重复或较旧更新只能成为 no-op；换 stage 仅 `stageProcessed` 可重置，新 epoch 可显式重置全部进度镜像。
- 三年窗口为半开 UTC 区间 `[windowStartUtc, windowEndUtc)`：`windowEndUtc` 是任务创建时冻结的最近完整 UTC 整点，`windowStartUtc = subtractCalendarYears(windowEndUtc, 3)`。减年保留 UTC 时、分、秒；目标年不存在同月同日时，将日 clamp 为目标月份最后有效日，因此 2 月 29 日减到普通年为 2 月 28 日。预期行数是两个 UTC instant 的整小时差，不写死为 `3 * 365 * 24`。

语言和数据库无关的冻结算法如下：

```text
subtractCalendarYears(endUtc, years):
  require endUtc is UTC and minute=0 and second=0 and subsecond=0
  targetYear = year(endUtc) - years
  targetMonth = month(endUtc)
  targetDay = min(day(endUtc), daysInMonth(targetYear, targetMonth))
  return utc(targetYear, targetMonth, targetDay, hour(endUtc), 0, 0)

windowStartUtc = subtractCalendarYears(windowEndUtc, 3)
expectedRows = integerHoursBetween(windowStartUtc, windowEndUtc)
```
- 标准气象行至少含 `timestampUtc`、规范化的气象观测字段、单位和质量标志；存储和计算单位使用 SI。批次内唯一键是 `batchId + timestampUtc`，每个 UTC 整点必须恰有一行。
- 项目 timezone 只用于展示和 Provider 边界转换。DST 重复本地小时映射为两个不同 UTC 整点，跳失本地小时不补点；唯一性和连续性只按 UTC 判定。
- `CLEAN` 可以规范化单位、字段名和已声明的 Provider 缺测标志，但禁止生成不存在的小时观测。`VALIDATE` 遇到缺小时、重复 UTC、非整点、窗口外行、非法数值或 schema 不符必须失败，不得静默插值、前向填充或补零。
- Provider 下载和 CSV 上传必须进入同一 canonical weather schema、运行同一 `CLEAN/VALIDATE/STORE` 管线和相同质量阈值。CSV 不是绕过质量门禁的旁路。
- Weather batch 是不可变归档；质量状态至少为 `PENDING|PASSED|FAILED`。失败批次和未完成批次永远不能成为 current。
- STORE 前的 staging 行/对象必须以 `taskId + attemptId + retryEpoch + batchId` 完整隔离；任何查询、删除、重放或 GC 都必须带完整键，禁止仅按 taskId/batchId 操作。处理固定为两个事务，禁止合并：
  1. **STORE transaction：** 以四元 staging key 和 store idempotency key 读取候选，在一个事务中幂等提升为不可变 `PASSED` formal batch，包含标准行、checksum、quality report、dependency fingerprint 与 source lineage；只写 formal batch/store receipt，不写 current pointer、archive pointer 或 `SUCCEEDED`。
  2. **Publish transaction：** 只读取已提交 `PASSED` formal batch，重新验证 current eligibility 与当前 attempt/epoch，在一个事务中切换 current pointer、归档 previous pointer，并将 attempt 与 Business Task 镜像置为 `SUCCEEDED`；不得修改 formal batch 内容，也不得依赖 staging 才能完成。
- STORE commit outcome unknown 时，先以四元 key、formal batch checksum/quality 和 store receipt 对账：已提交则复用 formal batch 并进入 publish；明确 aborted 才可重放 STORE。Publish commit outcome unknown 时，先对账 current pointer、previous archive、attempt/Task CAS 与 publish receipt：已提交则幂等返回胜出结果，明确 aborted 才可重放 publish。任何 unknown 未解析前禁止 GC。
- publish outcome 已解析后才可处理 staging：成功时可异步清除对应可再生 staging；失败、取消、过期或旧 attempt staging 只可在配置化安全 TTL 到期、lease 失效、无 STORE/publish reconciliation 引用且 formal batch/current/archive 引用安全时 GC。formal batch 若为 current 或 archive 永不随 staging GC 删除；清理旧 attempt 永远不得触碰 current formal batch或新 attempt staging。
- Project 的 `currentDependencyFingerprint` 是 canonical JSON 的 SHA-256，只覆盖 `projectId`、`inputRevision`、`taskType`、规范化 country/adminArea/city/timezone、冻结的三年请求窗口，以及影响数据适用性的必要模板/清洗/质量规则版本；不得包含 Provider 名称、Provider 请求 id、CSV checksum、上传者或其他 source identity。Business Task 创建时固定该 `dependencyFingerprint`，同一 Task 的所有 attempt 均不得迁移它。
- 每个 attempt 独立保存 `sourceLineage`：Provider attempt 至少含 provider name/version、request window、稳定 request key/回执；CSV attempt 至少含文件 checksum、canonical schema version、uploaderId 和 uploadedAt。Batch 同时保存 Task 的 `dependencyFingerprint` 与产生它的 `sourceLineage`；两者用途分离，lineage 不参与项目 revision 或 current 适用性比较。
- 只有 `task.projectId`、`task.inputRevision`、`task.taskType`、`batch.projectId`、`batch.inputRevision`、`batch.taskType` 均相等，Project `currentDependencyFingerprint == Task.dependencyFingerprint == Batch.dependencyFingerprint`，且 batch quality 为 `PASSED` 时才允许发布 current；发布守卫不比较 source lineage，也不在 Provider→CSV 恢复时改变 dependency fingerprint。

## 正常流程

1. Worker 认领 M1 创建的 Business Task 当前 attempt，取得可过期 lease，从该 attempt 持久化的最后完成阶段恢复；同一 epoch 内认领不得清零进度或把终态倒退为 `RUNNING`。所有领取、进度、失败、完成和 broker ack 写入必须携带 `taskId + attemptId + retryEpoch`，并以这三个值及预期 version 做 CAS。
2. `LOCATE` 将冻结的地理字段解析为 Provider location，保存脱敏 location identity；`REQUEST` 使用稳定 provider request key 发起或查询请求；`DOWNLOAD` 将响应写入按 checksum 标识的原始对象。
3. CSV attempt 不执行 Provider 网络阶段，为 `LOCATE/REQUEST/DOWNLOAD` 记录 `SKIPPED(source=CSV)` 审计后直接进入 `CLEAN`。`CLEAN` 将 Provider 或 CSV 输入映射到 canonical schema；`VALIDATE` 按冻结 UTC 窗口核对 schema、实际小时数、UTC 唯一性、连续性、范围和数值质量，生成不可变 quality report。
4. STORE transaction 以四元 staging key 在 MySQL 中幂等创建完整 `PASSED` formal batch；`batchId + timestampUtc` 唯一，checksum、行数、quality、fingerprint 和 lineage 一起提交。重复执行复用同一 formal batch，且不触碰 current/归档/Task 终态。
5. 独立 publish transaction 锁定 Project current 指针和候选 formal batch，重新计算并比较项目当前依赖指纹。仅在全部守卫成立，且 `attemptId/retryEpoch` 仍等于 Business Task 的 `currentAttemptId/retryEpoch` 时，以 compare-and-set 原子更新 current pointer、归档前一 current，并将当前 attempt 与 Task 镜像 `RUNNING -> SUCCEEDED`；任一守卫失败则三项均不更新。旧 attempt 的晚到完成或 ack 只能记录为被拒事件，不能覆盖新 attempt 镜像或 current。
6. 历史仿真在一次一致性读取中取得 current pointer、batch 和 quality report，要求 `PASSED` 且指纹仍匹配；仿真 run 保存所消费的 `batchId` 和指纹。运行期间 current 后续切换不改变已冻结 run 输入。

## 状态与进度

下表描述单个 attempt 的状态；Business Task 对外镜像且只镜像 `currentAttemptId/retryEpoch` 指向的这一行状态。

| 状态/阶段 | 进入条件 | 允许操作 | 退出条件 |
|---|---|---|---|
| `QUEUED` | 已派发或合法 attempt 排队 | 查询、取消、Worker 认领 | Provider lease 进入 `RUNNING/LOCATE`；CSV lease 记录前三阶段 `SKIPPED` 后进入 `RUNNING/CLEAN` |
| `RUNNING/LOCATE` | Worker 首次认领或从该阶段恢复 | 定位、查询、取消 | 持久化定位结果后进入 `REQUEST` |
| `RUNNING/REQUEST` | location 已保存 | Provider 请求、查询、取消 | 请求引用保存后进入 `DOWNLOAD` |
| `RUNNING/DOWNLOAD` | 请求可下载 | 下载/校验原始对象、查询、取消 | 原始 checksum 保存后进入 `CLEAN` |
| `RUNNING/CLEAN` | Provider 文件或 CSV 已冻结 | 规范化、查询、取消 | canonical 临时批次保存后进入 `VALIDATE` |
| `RUNNING/VALIDATE` | canonical 行集完成 | 质量校验、查询、取消 | quality `PASSED` 后进入 `STORE`；失败进入 `FAILED` |
| `RUNNING/STORE` | quality 已通过 | STORE transaction 提升 formal batch；随后 publish transaction；查询、取消 | publish transaction 成功进入 `SUCCEEDED`；依赖过期进入 `STALE` |
| `SUCCEEDED` | STORE transaction 已提交，且独立 publish transaction 原子提交 current/archive/attempt+Task CAS | 查询、仿真引用 | 终态 |
| `FAILED` | 结构化错误已持久化 | 查询；仅 `retryable=true` 时重试；Provider 失败可上传 CSV | 合法重试进入 `QUEUED`，或保持终态 |
| `CANCELLED` | 授权取消请求胜出 CAS | 查询 | 终态；晚到 Worker 结果只能丢弃 |
| `STALE` | input revision/依赖已变化或发布守卫失败 | 查询 | 终态；不得成为 current |

每次合法 attempt 状态、阶段或计数变化递增 attempt `version`，并在相同 `taskId + attemptId + retryEpoch` CAS 中更新 Business Task 聚合镜像。API 字段固定为 `stage`、`stageProcessed`、`stageTotal`、`overallPercent`：

- 阶段 ordinal 固定为 LOCATE=0、REQUEST=1、DOWNLOAD=2、CLEAN=3、VALIDATE=4、STORE=5；同一 attempt/epoch 只前进。Provider attempt 的有效阶段数为 6；CSV attempt 的前三阶段为 `SKIPPED`，有效阶段数为 3，overall 计算从 CLEAN 记为第 0 个有效阶段。
- 活动阶段必须满足 `0 <= stageProcessed <= stageTotal` 且 `stageTotal > 0`。同一 stage 内 `stageProcessed` 只增；进入下一 stage 时允许按新阶段工作量重置 `stageProcessed=0` 和修订 `stageTotal`，这不是倒退。
- `overallPercent = floor(100 * (completedEffectiveStages + stageFraction) / effectiveStageCount)`，其中 `stageFraction = min(stageProcessed, stageTotal) / stageTotal`；活动状态 clamp 为 0..99，`SUCCEEDED` 固定 100，失败/取消/过期保持最后值。禁止按墙钟时间猜测进度。
- 同一 stage 若发现总量估计需要修订，只接受不会降低已显示 fraction 的新 `stageTotal`；否则在下一个 stage 才应用新估计，或同时提高 `stageProcessed` 使 fraction 不降。旧 stage、旧 version、旧 attempt/epoch 更新全部拒绝。

重启、轮询乱序和重复消息依据三元身份、version/CAS 收敛；终态不回退只约束同一 attempt/epoch。Business Task 只有通过授权且满足失败恢复条件的 Retry/CSV recovery command 才能开启新 epoch；新 epoch 的 `stageProcessed/stageTotal/overallPercent` 可明确重置，普通 Worker 消息无权改变 epoch。

## 城市变更、取消、重试与幂等

- 只有影响适用性的依赖变化才创建新业务 Task。修改 country/adminArea/city/timezone 必须在一个项目事务内递增 `inputRevision`、重算依赖指纹、将旧 revision 的活动 Task CAS 为 `STALE` 或 `CANCELLED`、创建新 `WEATHER_HISTORY_FETCH` Task 与 OutboxEvent。事务失败则四项均不生效。
- 深圳改为东莞后，新 Task 只绑定东莞 revision；旧深圳 Worker 可以保存脱敏日志和不可变归档 batch，但在 `STORE` 发布事务中必因 revision/指纹守卫失败，不能覆盖东莞 current。
- 用户取消只以 `taskId + currentAttemptId + retryEpoch` CAS 改变当前尚未终态的 attempt 和 Task 镜像；Worker 在外部请求前、阶段提交前和 current 发布前检查取消/lease。已发出的 Provider 请求可能继续产生外部副作用，本地结果仍不得入 current。
- `retryable=true` 的失败重试必须在单一事务中验证当前 attempt 仍为可重试 `FAILED`，复用同一 business `taskId`，将 `retryEpoch` 原子加一，创建新 `attemptId`，切换 `currentAttemptId`，并把聚合镜像初始化为新 attempt 的 `QUEUED` 与初始进度。Provider retry 保留前一 attempt 的 source lineage，不覆盖历史回执，并为新 attempt 保存自己的 Provider lineage。相同重试幂等键的并发请求由唯一约束/CAS 收敛到同一新 attempt 和同一新 epoch，不得重复递增。
- API/UI 必须把 `retryEpoch`、`currentAttemptId` 与镜像进度一起返回。客户端只在观察到更大的 epoch 时明确重置进度并显示“新一次尝试”；同一 epoch 的较小 stage、stageProcessed 或 overallPercent 必须丢弃。旧 epoch 的轮询响应、Worker late update、完成或 ack 不得覆盖较新 epoch。
- Provider→CSV 恢复不递增 `inputRevision`、不创建新业务 Task、不改变 `dependencyFingerprint`；它只在同一 `taskId` 下创建 CSV attempt 和独立 source lineage。相同 CSV checksum、schema version 与业务 Task 的恢复幂等键必须复用已存在的 attempt/已验证 batch，不重复清洗、入库或发布。
- `retryable=false` 的 Provider 错误对普通 retry 命令返回稳定错误且不得创建 attempt；只有修复外部配置后由明确的管理动作，或使用 CSV recovery 命令，才可创建不同恢复类型的 attempt。
- Worker 崩溃后 lease 到期可由另一 Worker 认领，从同一 attempt 的最后持久阶段恢复。阶段 side effect 与阶段完成标记必须通过 `taskId + attemptId + retryEpoch`、唯一键或事务收敛；数据库提交后、broker ack 前崩溃的重投不得重复标准行、batch 或 current 切换，旧 epoch ack 必须成为 no-op。
- 外部 Provider 不受本地事务控制，因此不承诺请求、计费或 Provider 作业 exactly-once。实现应发送稳定 provider request key、保存回执并优先查询/复用；无法去重时允许外部重复，但本地入库和发布仍必须幂等。

## 失败与恢复

统一 Task error 至少含 `code`、`messageKey`、`stage`、`retryable`、脱敏 `details`、`requestId`、`providerRequestId`（可用时）和 `occurredAt`。

| 触发 | 状态/错误 | 写入与 current | 恢复动作 |
|---|---|---|---|
| Provider 限流、超时或连续 5xx | `FAILED / PROVIDER_UNAVAILABLE / retryable=true` | 保留已提交阶段；current 不变 | 指数退避后重试原 Task，或上传标准 CSV |
| Provider 认证/许可/请求不可修复 | `FAILED / PROVIDER_REJECTED / retryable=false` | 保存脱敏错误；current 不变 | 普通 retry 返回稳定错误且零新 attempt；管理员修复配置后显式恢复，或 CSV |
| CSV schema 不符 | `FAILED / CSV_SCHEMA_INVALID / retryable=false` | 不写标准 batch；current 不变 | 下载 schema 示例，修正后重新上传 |
| 缺时、重复 UTC 或窗口不符 | `FAILED / WEATHER_CONTINUITY_INVALID / retryable=false` | 保存失败报告；不得补点或发布 | 更换 Provider 数据或合格 CSV |
| STORE transaction 失败或 commit unknown | `RUNNING/STORE` 或结构化可重试失败 | staging 保持隔离；不得触碰 current/终态或提前清理 | 对账 formal batch checksum/quality 与 store receipt；committed 则进入 publish，aborted 才以四元 key 重放 |
| Publish transaction 失败或 commit unknown | `RUNNING/STORE` 或读取胜出终态 | formal batch 保留；current/archive/终态只允许全有或全无 | 对账 current/archive/attempt+Task CAS 与 publish receipt；committed 幂等返回，aborted 才重放；解析前禁止 GC |
| 项目 revision 在执行中变化 | `STALE` 或已 `CANCELLED` | 可保留归档，不改 current | 查询新 Task；旧 Task 不可重试为当前 revision |
| current 发布 CAS 冲突 | `STALE` 或读取胜出结果 | 不覆盖胜出 current | 重读项目 revision/指纹；只有仍同依赖的幂等重放可成功 |
| Worker/容器重启 | lease 到期，持久状态不变 | 已提交阶段保留 | 新 Worker 从最后阶段恢复 |
| 未认证或无权读取/取消/重试/上传 | `401`、不可区分 `404` 或写操作 `403` | 无业务写入 | 重新认证或使用授权账号 |

## 权限与审计

- `ENGINEER` 只能列出和读取自己项目的 Task/batch/quality report，并对自己的可恢复 Task 执行取消、重试或 CSV 上传；`ADMIN` 可治理所有项目。列表在数据库 scope 内过滤。
- 跨 owner 的已存在单项 id 与随机不存在 id 返回相同 `404` error envelope、message 和 timing class；不得泄露城市、Provider、状态、owner、行数或 batch 是否存在。写操作在已授权资源上角色不足返回 `403`。
- 审计至少记录 `WEATHER_STAGE_CHANGED`、`WEATHER_PROVIDER_FAILED`、`WEATHER_CSV_ACCEPTED/REJECTED`、`WEATHER_BATCH_VALIDATED`、`WEATHER_CURRENT_PUBLISHED/REJECTED`、`WEATHER_TASK_CANCELLED/RETRIED`、`PROJECT_GEOGRAPHY_REVISED` 和 `HISTORICAL_SIMULATION_INPUT_BOUND`。
- 审计含 `requestId`、actorId、projectId、inputRevision、taskId、batchId、前后状态、阶段、指纹摘要、结果和错误码；不得记录 Provider 密钥、认证 header、完整原始文件、跨 owner payload 或不必要的地理精度。授权失败只记录调用者、requestId、操作和目标 id 的不可逆摘要。

## API、数据与版本

- 复用 `GET /tasks/{taskId}` 与 `GET /tasks?projectId=&activeOnly=` 暴露 Business Task 的持久化 `retryEpoch/currentAttemptId/status/stage/stageProcessed/stageTotal/overallPercent/version/error/recoveryActions` 聚合镜像；M2 工具卡和任务坞不拥有第二份状态。attempt history 读取必须标明各自 epoch，不能混排为一个全局单调进度流。
- M4 实现前先批准取消、重试、CSV 上传、batch/quality/current 查询的 OpenAPI 与 schema。响应只按服务端允许动作显示恢复入口。
- 数据迁移须提供 Task 业务键、retry/recovery 幂等键、attempt、四元 staging key、CSV checksum/schema/task 复用键、`batchId + timestampUtc`、current pointer 及 dependency fingerprint 的唯一约束/索引，并分别保留不可变 source lineage、quality report、原始 checksum、publish reconciliation 和 current 切换审计。
- publish transaction 必须锁定/条件更新 project current pointer，验证已提交 formal batch/quality 与当前依赖指纹，归档旧 pointer，并提交 attempt 与 Task 终态；禁止与 STORE transaction 合并，也禁止先标 `SUCCEEDED` 再异步切换 current。
- 三年仿真接口必须要求或解析 project 的 current weather batch；若不存在、quality 非 `PASSED`、指纹不匹配或 revision 已改变，返回稳定阻断错误，不回退到“最近一个”批次。

## 可观察性

- 指标包含各阶段耗时/失败数、Provider retry/限流、CSV 接受率、预期/实际小时数、连续性失败、Task 版本冲突、lease 重领、重复入库去重、current 发布成功/拒绝及 stale late completion 数。
- 日志用 requestId、providerRequestId、projectId、inputRevision、taskId、attemptId、batchId 关联；敏感 Provider 凭据和原始 payload 必须脱敏。
- 告警覆盖 Provider 连续失败、Task 长时间无单调进展、STORE 重试堆积、current 发布拒绝异常增长和仿真缺 current；告警不得自动将失败数据标为通过。

## 验收场景

1. **六阶段成功：** Given 合格 Provider 数据，When Worker 执行，Then阶段只按六阶段前进且 overallPercent 单调；换 stage 仅 stageProcessed 可重置。STORE transaction 先提交唯一 PASSED formal batch，独立 publish transaction 再原子提交 current/archive/`SUCCEEDED`。
2. **Provider 与 CSV：** Given Provider 连续失败，When 同一 Business Task 创建 CSV attempt，Then dependency fingerprint 不变，CSV 以独立 source lineage 从 CLEAN 开始，前三阶段仅记 `SKIPPED` 审计，并走同一校验和入库门禁；合格后可发布，不合格时 current 不变。
3. **城市 revision：** Given 深圳 revision 正在下载，When 改为东莞，Then revision 递增、深圳 Task 失效/取消、东莞新 Task 创建；深圳晚完成只能归档且不能覆盖东莞 current。
4. **进度与恢复：** Given 同 epoch 乱序消息、重复投递和容器重启，When Worker 恢复，Then attempt version、stage ordinal、stageProcessed 和 overallPercent 不倒退；换 stage 仅 stageProcessed 可重置。Given Retry command 开启更大 epoch，Then Business Task 镜像原子切换并允许 UI 明确重置，新旧 attempt 均无重复标准行或 current 切换。
5. **UTC 与 DST：** Given 跨闰日和 DST 的三年窗口，When 校验，Then expectedRows 由 UTC 半开区间实际整点计算，重复本地小时有两个 UTC key，跳失本地小时不补，任何 UTC 缺失均阻断。
6. **两事务与原子 current：** Given STORE/publish 两个独立事务及各自 commit unknown，When 对账和重放，Then formal batch 提升幂等，只有项目当前 revision/taskType/fingerprint 完全匹配的 PASSED formal batch可发布；current/archive/终态一次完整提交，读者不观察半状态。
7. **仿真消费：** Given current 质量通过批次和另一个较新但失败/过期批次，When 启动三年仿真，Then只绑定 current 的 batchId/fingerprint；current 缺失或失配时阻断。
8. **重试与权限：** Given 可重试/不可重试错误、并发重试、重复 CSV 与 owner/其他工程师/Admin，When 重试、上传或查询，Then taskId/fingerprint 稳定，epoch/currentAttempt 镜像原子切换，attempt/lineage 独立且幂等，旧 attempt 晚到更新隔离，不可重试错误零新 attempt，并且作用域、401/403/404 和脱敏审计符合本规格。

## 测试映射

| 验收条件 | 测试层级 | 测试文件/fixture | 门禁 |
|---|---|---|---|
| 六阶段、进度单调、错误结构 | unit / contract | `tests/unit/weather/test_ingestion_state_machine.py`；`tests/contracts/test_weather_task_contract.py` | required |
| 三年 UTC、唯一键、连续性与 CSV schema | unit / property | `tests/unit/weather/test_weather_quality.py`；`tests/property/test_weather_utc_timeline.py` | required |
| Provider、重试、重启、幂等入库 | integration | `tests/integration/test_weather_ingestion_worker.py` | required |
| 城市 revision、晚完成与 current 原子切换 | integration | `tests/integration/test_weather_current_publication.py` | required |
| 权限、审计和错误恢复 | integration / security | `tests/integration/test_weather_authorization_audit.py` | required |
| 任务坞恢复、CSV 和仿真消费 | e2e | `tests/e2e/test_weather_ingestion_recovery.py`；`tests/e2e/test_historical_simulation_weather_binding.py` | required |

## 阻断审批的问题

无。Provider 供应商选择、凭据和许可由实现环境配置，不改变本规格的 adapter、质量、幂等和 current 守卫。
