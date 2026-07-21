# M4 三年气象摄取与 current 安全发布测试计划

| 属性 | 值 |
|---|---|
| 状态 | approved |
| Spec | `docs/specs/m4/weather-ingestion.md` v1.0.0 |
| Owner | M4 Test Agent / Acceptance Agent |
| Fixture Version | `fixtures/acceptance/M4/weather-ingestion/1.0.0`，PLANNED / NOT_VERIFIED |

本计划定义未来 M4 实现门禁。当前重基线只批准规格和计划；所有运行时用例结果均为 `not_run`，fixture 仅为 `PLANNED / NOT_VERIFIED`。

## 风险排序

| 风险 | 影响 | 概率 | 测试策略 | PR 门禁 |
|---|---|---|---|---|
| 旧城市任务晚完成覆盖 current | high | high | 深圳→东莞并发屏障和独立 publish transaction CAS | yes |
| UTC/DST 行数或唯一键错误 | high | medium | 跨闰日、DST property 与真实三年窗口断言 | yes |
| 缺小时被静默补点 | high | medium | 删除随机 UTC 小时并核对失败报告/标准行 | yes |
| 重启/重投重复入库或倒退进度 | high | high | 阶段故障注入、lease 到期、乱序版本回放 | yes |
| Provider 失败后 CSV 绕过质量规则 | high | medium | 同一数据分别走 Provider/CSV 并比较 schema/report | yes |
| 仿真消费非 current 或失败批次 | high | medium | 多批次并存，记录 run 绑定 batchId/fingerprint | yes |
| 权限或错误日志泄露 Provider/项目信息 | high | medium | 跨 owner 等价 404、日志/审计脱敏扫描 | yes |
| 外部 Provider 重复副作用被误报 exactly-once | medium | medium | 模拟不可去重 Provider，断言仅本地行和发布幂等 | yes |

## 测试用例

| Test ID | 层级 | 前置条件 | 输入/动作 | 预期结果 | 精确命令 | 证据路径 |
|---|---|---|---|---|---|---|
| M4-U-001 | unit | Provider attempt `RUNNING`，version=10；六阶段事件 fixture | 顺序应用 LOCATE 至 STORE；同阶段更新 stageProcessed/stageTotal，换阶段重置 | ordinal 只前进；同 stage 的 stageProcessed 只增且不超过 stageTotal；换阶段可重置；overallPercent 按冻结公式确定且 0..99，SUCCEEDED=100 | `python -m pytest tests/unit/weather/test_ingestion_state_machine.py::test_provider_stage_progress_and_overall_percent_are_deterministic -q` | `artifacts/acceptance/M4/M4-U-001.txt` |
| M4-U-002 | unit | attempt A epoch=0 已到 `VALIDATE` version=20 | 依次到达同 epoch 旧 `DOWNLOAD`、较小 stageProcessed、重复 version、`RUNNING` 覆盖 `FAILED` | 全部旧更新为 no-op；同一 attempt/epoch 的终态、ordinal、stage fraction、overallPercent 和 version 不倒退 | `python -m pytest tests/unit/weather/test_ingestion_state_machine.py::test_out_of_order_progress_cannot_regress_same_attempt_epoch -q` | `artifacts/acceptance/M4/M4-U-002.txt` |
| M4-C-001 | contract | Task error schema 和 Provider adapter | 模拟 timeout、429、连续 5xx、401/许可拒绝 | `FAILED` error 含 code/messageKey/stage/retryable/requestId；临时错误可重试，认证/许可默认不可重试 | `python -m pytest tests/contracts/test_weather_task_contract.py::test_provider_errors_are_structured_and_classified -q` | `artifacts/acceptance/M4/M4-C-001.txt` |
| M4-U-003A | unit | `windowEndUtc=2024-02-29T00:00:00Z` | 执行 subtractCalendarYears(end,3) 和 expectedRows | 精确 start=`2021-02-28T00:00:00Z`，expectedRows=`26304`；2/29 clamp 到目标年 2/28 | `python -m pytest tests/unit/weather/test_weather_quality.py::test_calendar_year_subtraction_clamps_feb29_and_counts_26304_hours -q` | `artifacts/acceptance/M4/M4-U-003A.txt` |
| M4-U-003B | unit | `windowEndUtc=2023-03-01T00:00:00Z` | 执行 subtractCalendarYears(end,3) 和 expectedRows | 精确 start=`2020-03-01T00:00:00Z`，expectedRows=`26280`；普通日期保留月日与 UTC 时刻 | `python -m pytest tests/unit/weather/test_weather_quality.py::test_calendar_year_subtraction_preserves_ordinary_boundary -q` | `artifacts/acceptance/M4/M4-U-003B.txt` |
| M4-U-005 | unit/contract | CSV attempt epoch=2，从 CLEAN 开始；前三阶段 SKIPPED | 更新 CLEAN/VALIDATE/STORE；发送旧 stage、旧 epoch、同 stage stageProcessed/stageTotal 修订 | effectiveStageCount=3，CLEAN 从 overall 0 开始；SKIPPED 不伪造活动进度；同 stage fraction/overall 不降，换 stage 可重置；旧 stage/epoch 拒绝 | `python -m pytest tests/unit/weather/test_ingestion_state_machine.py::test_csv_skipped_stages_total_revision_and_epoch_reset_contract -q` | `artifacts/acceptance/M4/M4-U-005.txt` |
| M4-PROP-001 | property | 生成跨多个 IANA DST 区的 UTC 窗口 | UTC→local→UTC 往返并生成 key | 每个 UTC 整点唯一；重复本地小时保留两个 UTC key；跳失本地小时不生成补点 | `python -m pytest tests/property/test_weather_utc_timeline.py::test_dst_never_changes_utc_uniqueness_or_row_count -q` | `artifacts/acceptance/M4/M4-PROP-001.txt` |
| M4-U-004 | unit | 完整三年 canonical 行集 | 删除一个中间 UTC 小时、复制另一小时、加入非整点/窗口外行 | `WEATHER_CONTINUITY_INVALID`；quality `FAILED`；不得插值、前向填充、补零或发布 | `python -m pytest tests/unit/weather/test_weather_quality.py::test_missing_duplicate_and_out_of_window_hours_block_without_fill -q` | `artifacts/acceptance/M4/M4-U-004.txt` |
| M4-I-001 | integration | stub Provider 返回合格三年数据；空 MySQL | 执行完整 Worker | 持久化六阶段；标准行数等于实际 UTC 小时；`batchId+timestampUtc` 唯一；quality PASSED，current 与 `SUCCEEDED` 原子提交 | `python -m pytest tests/integration/test_weather_ingestion_worker.py::test_provider_happy_path_stores_valid_three_year_batch -q` | `artifacts/acceptance/M4/M4-I-001.json` |
| M4-I-002 | integration | Provider 连续返回 timeout/429/5xx；冻结时钟 | 执行到重试上限并查询 Task | 每 attempt 错误结构化且保留各自 Provider source lineage；指数退避；Task 最终 `FAILED retryable=true`；原 current 不变；CSV recovery action 可见 | `python -m pytest tests/integration/test_weather_ingestion_worker.py::test_consecutive_provider_failures_preserve_retryable_recovery -q` | `artifacts/acceptance/M4/M4-I-002.txt` |
| M4-I-003 | integration | 完成 M4-I-002；准备同 schema 合格 CSV | owner 上传 CSV 并恢复原业务 Task | 复用同 taskId/dependency fingerprint，创建新 CSV attempt/source lineage；LOCATE/REQUEST/DOWNLOAD 仅审计为 SKIPPED，实际进度从 CLEAN 开始；合格后可发布 current | `python -m pytest tests/integration/test_weather_ingestion_worker.py::test_csv_fallback_uses_same_dependency_and_starts_at_clean -q` | `artifacts/acceptance/M4/M4-I-003.json` |
| M4-I-004 | integration | 失败 Task；CSV 缺一小时或字段/单位错误 | 分别上传三类不合格 CSV | 稳定 schema/continuity 错误；无 PASSED batch、无 current 切换、无静默补点 | `python -m pytest tests/integration/test_weather_ingestion_worker.py::test_invalid_csv_cannot_bypass_quality_gate -q` | `artifacts/acceptance/M4/M4-I-004.txt` |
| M4-I-005 | integration | 深圳 revision=1 Task 停在 DOWNLOAD；已有深圳 current 可选 | 原子修改城市为东莞 | `inputRevision=2`；旧活动 Task `STALE` 或 `CANCELLED`；创建唯一东莞 Task+Outbox；项目地理、revision、旧终态和新 Task 同事务生效 | `python -m pytest tests/integration/test_weather_current_publication.py::test_shenzhen_to_dongguan_revision_invalidates_old_task_and_creates_new -q` | `artifacts/acceptance/M4/M4-I-005.json` |
| M4-I-006 | integration | M4-I-005；阻塞深圳 Worker；东莞 Task 已发布 current | 释放旧深圳 Worker，使其完成 STORE | 深圳 batch 可归档但发布守卫失败，旧 Task 终态 `STALE/CANCELLED`；东莞 current batchId/fingerprint 不变 | `python -m pytest tests/integration/test_weather_current_publication.py::test_late_shenzhen_completion_cannot_overwrite_dongguan_current -q` | `artifacts/acceptance/M4/M4-I-006.json` |
| M4-I-007A | integration/parameterized | 两套完全隔离 fixture/数据库：P 仅有 current attempt=Provider 和唯一合法 Provider PASSED formal batch；C 仅有 current attempt=CSV 和唯一合法 CSV PASSED formal batch；两套依赖字段相同 | 分别运行 P、C eligibility/publish，不在同一 Task 创建两个合格 attempt | P/C 各自唯一候选均通过；predicate 只比较 dependency/quality/current attempt，source lineage 仅随 formal batch 保存且不影响 eligibility | `python -m pytest tests/integration/test_weather_current_publication.py::test_isolated_provider_and_csv_scenarios_are_equally_eligible -q` | `artifacts/acceptance/M4/M4-I-007A.json` |
| M4-I-007B | integration | STORE transaction 已为同一 current attempt/batch 提交 PASSED formal batch；两个 Worker/发布命令；publish 事务屏障；pointer/archive/Task CAS/commit 故障注入 | 并发执行相同 publish，并逐写点注入失败与 publish commit unknown | 最多一次完整 pointer+archive+attempt/Task SUCCEEDED 提交；失败方对账 publish receipt 后幂等读取胜出结果；读者不见半状态，unknown 未解析前 staging 不清理 | `python -m pytest tests/integration/test_weather_current_publication.py::test_same_formal_batch_concurrent_publish_is_one_atomic_commit_with_reconciliation -q` | `artifacts/acceptance/M4/M4-I-007B.json` |
| M4-I-008 | integration | Task 在每个阶段已有持久 checkpoint；可重启 Worker 容器 | 六个阶段分别 kill 容器，lease 到期后重启消费 | 从最后提交 checkpoint 恢复；version/stageProcessed/overallPercent 不倒退；标准行、batch、quality report、current switch 均不重复 | `python -m pytest tests/integration/test_weather_ingestion_worker.py::test_container_restart_resumes_each_stage_idempotently -q` | `artifacts/acceptance/M4/M4-I-008.json` |
| M4-I-009 | integration | Task 分别处于 REQUEST、VALIDATE、STORE；Provider 请求可能已发出 | owner 取消，并让晚到回调/Worker 继续 | CAS 后 Task `CANCELLED`；外部请求可重复或完成但本地 current 不变；取消审计脱敏 | `python -m pytest tests/integration/test_weather_ingestion_worker.py::test_cancellation_blocks_late_local_store_and_publication -q` | `artifacts/acceptance/M4/M4-I-009.txt` |
| M4-I-010 | integration | Provider 不支持幂等且记录两次外部调用；本地首次 commit 后 ack 前崩溃 | 重投同 Task/attempt | 允许记录两次 Provider 调用且不声称 exactly-once；本地每个 UTC key 一行、一个 batch、一次 current 切换 | `python -m pytest tests/integration/test_weather_ingestion_worker.py::test_external_duplicate_side_effect_still_has_idempotent_local_results -q` | `artifacts/acceptance/M4/M4-I-010.json` |
| M4-I-011 | integration | Business Task epoch=0/current=A；A 因 timeout 为 `FAILED retryable=true` 且有 lineage | 使用幂等键 `retry-001` 请求 Provider 重试 | 单事务保持 taskId/fingerprint，epoch 变 1、创建 B、currentAttemptId=B、镜像为 B/QUEUED/初始进度；A lineage/FAILED 保留，B 有独立 lineage | `python -m pytest tests/integration/test_weather_ingestion_worker.py::test_retry_atomically_advances_epoch_and_switches_task_mirror -q` | `artifacts/acceptance/M4/M4-I-011.json` |
| M4-I-012 | integration | Task 因许可拒绝为 `FAILED retryable=false` | 以普通 retry 命令重复请求 | 每次返回相同稳定错误；attempt 数、Task fingerprint、batch/current 均不变 | `python -m pytest tests/integration/test_weather_ingestion_worker.py::test_non_retryable_error_rejects_retry_without_new_attempt -q` | `artifacts/acceptance/M4/M4-I-012.txt` |
| M4-I-013 | integration | epoch=4/current=A 的 retryable Task；并发屏障；统一幂等键 | 20 个并发 retry 请求 | 20 个响应收敛到 epoch=5 和同一新 attemptId；数据库只新增一个 attempt、epoch 只加一次，镜像指向 winner，历史 lineage 不被覆盖 | `python -m pytest tests/integration/test_weather_ingestion_worker.py::test_concurrent_retry_creates_exactly_one_new_epoch_and_attempt -q` | `artifacts/acceptance/M4/M4-I-013.json` |
| M4-I-014 | integration | 同一 Task 已用 CSV checksum/schema 成功产生 PASSED batch | 以相同 checksum、schema version 和 recovery key 重复/并发上传 | 复用原 CSV attempt、source lineage、quality report 和 batch；标准行/current 发布不重复，revision/fingerprint 不变 | `python -m pytest tests/integration/test_weather_ingestion_worker.py::test_duplicate_csv_reuses_verified_attempt_and_batch -q` | `artifacts/acceptance/M4/M4-I-014.json` |
| M4-I-015 | integration | epoch=0/A 已 FAILED；Retry 已切换到 epoch=1/B 并运行到 VALIDATE | 发送 A 的晚到 progress、SUCCEEDED、STORE commit callback 和 broker ack | 所有带 taskId+A+epoch0 的 CAS 均为 no-op；B 镜像、epoch1、currentAttemptId、batch/current 均不变；记录 late-update 拒绝审计 | `python -m pytest tests/integration/test_weather_ingestion_worker.py::test_late_old_attempt_updates_and_ack_cannot_cross_epoch -q` | `artifacts/acceptance/M4/M4-I-015.json` |
| M4-I-016 | integration/contract | Task 有 A/FAILED epoch0、B/FAILED epoch1、C/RUNNING epoch2 | 查询 Business Task 与 attempt history | Task 镜像只等于 C 的 status/stage/stageProcessed/stageTotal/overallPercent/error，返回 retryEpoch=2/currentAttemptId=C；A/B 保持各自终态且不混成全局进度 | `python -m pytest tests/integration/test_weather_ingestion_worker.py::test_business_task_mirrors_only_current_attempt_with_history_preserved -q` | `artifacts/acceptance/M4/M4-I-016.json` |
| M4-I-017 | integration | A epoch0、B epoch1 staging；B formal batch/current；A 为 FAILED/CANCELLED/STALE 组合；TTL/lease 可控 | 分别在 STORE 写 formal rows/checksum/quality/receipt/commit 与 publish pointer/archive/Task CAS/receipt/commit 边界注入故障和 outcome unknown，再对 A 运行 GC | STORE unknown 先对账 formal batch/receipt，publish unknown 另行对账 current/archive/终态/receipt；任一未解析时零 GC；解析且 TTL 后只删 A staging，B staging/formal batch/current/new attempt 不受影响 | `python -m pytest tests/integration/test_weather_ingestion_worker.py::test_two_transaction_reconciliation_gates_attempt_isolated_gc -q` | `artifacts/acceptance/M4/M4-I-017.json` |
| M4-S-001 | integration/security | owner A、工程师 B、Admin；A 有 Task/batch；固定随机 id | B 列表/单项/取消/重试/CSV，Admin 和 A 执行授权动作；扫描日志审计 | B 列表过滤；存在跨 owner id 与随机 id 单项均不可区分 404；越权写不生效；授权动作成功；无密钥、payload、owner/城市泄露 | `python -m pytest tests/integration/test_weather_authorization_audit.py::test_scope_recovery_actions_and_audit_are_non_leaking -q` | `artifacts/acceptance/M4/M4-S-001.txt` |
| M4-E-001 | e2e | Docker Compose；任务坞通过 GET tasks；Task 到 CLEAN 后停止容器 | 刷新/重登，重启 Worker，轮询至完成 | 任务坞恢复同 taskId、retryEpoch、stage/version/stageProcessed/stageTotal/overallPercent；不显示本地猜测进度；完成后 current 正确 | `python -m pytest tests/e2e/test_weather_ingestion_recovery.py::test_dock_and_worker_recover_persisted_progress_after_restart -q` | `artifacts/acceptance/M4/M4-E-001.zip` |
| M4-E-002 | e2e | Provider 连续失败；owner 登录；合格/不合格 CSV 各一份 | 查看结构化失败，先上传坏 CSV，再上传合格 CSV | 失败和允许动作可见；坏 CSV 保持失败且 current 不变；合格 CSV 显示前三阶段 SKIPPED、从 CLEAN→VALIDATE→STORE 成功，taskId/revision/fingerprint 不变 | `python -m pytest tests/e2e/test_weather_ingestion_recovery.py::test_provider_failure_to_csv_recovery_flow -q` | `artifacts/acceptance/M4/M4-E-002.zip` |
| M4-E-003 | e2e/integration | current=A/PASSED；另有 B/FAILED 和 C/PASSED 但旧指纹 | 启动三年历史仿真并查看 run 输入 | 仿真只消费 A，保存 A batchId/fingerprint；若撤去 A current 则稳定阻断，不回退 B/C | `python -m pytest tests/e2e/test_historical_simulation_weather_binding.py::test_simulation_consumes_only_current_quality_passed_batch -q` | `artifacts/acceptance/M4/M4-E-003.json` |
| M4-E-004 | e2e | 任务坞显示 epoch=0 attempt A `FAILED` 且 overallPercent=90；Retry command 可用 | 点击重试并让新 attempt B 进入 LOCATE | 响应/轮询原子显示 retryEpoch=1/currentAttemptId=B；UI 明确标识新尝试并允许 stageProcessed/overallPercent 重置为 B 初值；迟到的 A 响应不把镜像改回 90 或 FAILED | `python -m pytest tests/e2e/test_weather_ingestion_recovery.py::test_ui_resets_progress_only_when_retry_epoch_increases -q` | `artifacts/acceptance/M4/M4-E-004.zip` |
| M4-G-001 | governance | 仓库包含本规格与计划 | 运行治理、占位符、21 单测和 diff 检查 | governance valid；占位符零匹配；21/21 governance tests OK；diff 无空白错误 | `python scripts/quality/check_governance.py` | `artifacts/acceptance/M4/M4-G-001.txt` |

## Fixture

| Dataset ID | 版本 | 状态 | 内容与来源 | 校验 |
|---|---|---|---|---|
| `m4-weather-three-year-utc` | 1.0.0 | PLANNED / NOT_VERIFIED | 计划生成固定 UTC 半开窗口、跨 2024 闰日的逐时 canonical 数据；非真实个人或生产数据 | 文件尚不存在，不能声明 checksum、行数已验证或签名 |
| `m4-weather-dst-cases` | 1.0.0 | PLANNED / NOT_VERIFIED | 计划生成 America/New_York、Europe/Berlin 等 DST 重复/跳失本地小时映射 | 文件尚不存在，不能声明 property 验证结果 |
| `m4-weather-invalid-continuity` | 1.0.0 | PLANNED / NOT_VERIFIED | 计划从完整 UTC 集合派生缺时、重复、非整点、越界和错误单位反例 | 文件尚不存在，不能作为质量门禁证据 |
| `m4-provider-responses` | 1.0.0 | PLANNED / NOT_VERIFIED | 计划包含脱敏的成功、timeout、429、5xx、认证/许可错误 adapter 响应 | 文件尚不存在，不含真实凭据，不声明 Provider 认证 |
| `m4-shenzhen-dongguan-race` | 1.0.0 | PLANNED / NOT_VERIFIED | 计划包含 revision=1 深圳晚完成与 revision=2 东莞先发布的确定性屏障 | 文件尚不存在，不能声明并发结果已验证 |

计划 manifest 路径为 `fixtures/acceptance/M4/weather-ingestion/1.0.0/manifest.json`。只有实际创建文件、manifest schema 通过、checksum 匹配、producer 与独立 verifier 身份不同、验证记录存在且 fixture 测试通过后，才可升级为 `SOFTWARE_VERIFIED`；当前全部保持 `PLANNED / NOT_VERIFIED`。外部 Provider 在线响应不作为可重复 fixture，验收使用批准的 adapter stub 或明确记录的隔离环境。

## 环境

- Windows 或 Linux Docker host，至少 8 核 CPU、16 GB 内存、SSD；记录容器镜像摘要。
- MySQL、Redis、Celery/broker 使用仓库锁定版本；测试 schema 独立，Worker lease 和时钟可控。
- Python 3.12 与仓库锁文件依赖；应用、数据库连接和测试时钟默认 UTC。
- Provider integration 使用隔离 stub；需要真实 Provider smoke 时使用单独受控凭据且不得进入 fixture/日志，其结果不能替代确定性门禁。
- DST 用例显式加载锁定 tzdata；项目展示时区分别为 `Asia/Shanghai` 和 DST 时区，唯一性仍按 UTC。
- 重启证据记录 kill 点、最后持久 version/stage、lease 到期、重领 Worker id、前后行数与 current pointer。

## 执行顺序与门禁

未来 M4 实现完成后，从仓库根目录依次执行，所有命令退出码必须为 0：

```powershell
python scripts/quality/check_governance.py
python -m unittest tests.governance.test_check_governance -v
python -m pytest tests/unit/weather/test_ingestion_state_machine.py tests/unit/weather/test_weather_quality.py tests/property/test_weather_utc_timeline.py -q
python -m pytest tests/contracts/test_weather_task_contract.py -q
python -m pytest tests/integration/test_weather_ingestion_worker.py tests/integration/test_weather_current_publication.py tests/integration/test_weather_authorization_audit.py -q
python -m pytest tests/e2e/test_weather_ingestion_recovery.py tests/e2e/test_historical_simulation_weather_binding.py -q
git diff --check -- docs/specs/m4 docs/testing/plans/M4-test-plan.md
```

通过标准：Provider 六阶段和同一 attempt/epoch 内 ordinal、stageProcessed/fraction/overallPercent 单调，换 stage 与新 epoch 按契约重置；CSV 前三阶段只记 SKIPPED 且从 CLEAN 开始；Provider/CSV 使用同一 schema/quality 但保存独立 source lineage；Retry 原子递增 epoch、创建 attempt 并切换 Business Task 镜像，旧 attempt late update/ack 全部隔离，并发 retry 只产生一个新 epoch/attempt；不可重试错误零新 attempt，重复 CSV 幂等；2/29 clamp 和普通边界精确行数通过；UTC key 零重复、缺时零静默补点；四元 staging 隔离，commit unknown 先对账，安全 TTL/GC 不影响 current/new attempt；同一 batch 并发 publish 仅一次完整提交且失败方读取胜出；深圳旧任务晚完成零 current 覆盖；三年仿真只绑定 `PASSED` current；权限响应和审计无泄露。当前文档提交只执行 governance、21 项治理单测、占位符扫描和 diff 检查，不把尚不存在的 M4 runtime tests 标记为 pass。

## 失败分类

| 分类 | 判定 | 处理人 | 门禁行为 |
|---|---|---|---|
| 产品缺陷 | 状态、UTC、质量、幂等、current、仿真或权限违反 approved spec | M4 Data/Backend Owner | 阻断合并，修复后重跑全部受影响层级 |
| 测试缺陷 | 测试与规格不一致、时间/并发不可重复或错误断言外部 exactly-once | M4 Test Owner | 修复测试并保留前后证据，不放宽产品不变量 |
| Fixture 缺陷 | checksum、行数、UTC 窗口、producer/verifier 或验证记录不合格 | Fixture Producer 与独立 Verifier | 阻断使用该 fixture 的全部结果 |
| 环境缺陷 | 容器、tzdata、锁定依赖、磁盘或 Provider stub 不符合记录 | Acceptance Agent | 重建并记录环境；不得标记 pass |
| Provider 环境缺陷 | 真实 Provider 凭据/限额/网络异常且 adapter stub 门禁正常 | Provider Operator | 记录 smoke 失败；不得改变结构化失败与恢复契约 |
| 安全缺陷 | 跨 owner 泄露、越权写入、日志含密钥/原始 payload | Security Owner | 立即阻断并清理泄露证据，重新执行安全扫描 |

## 结果与证据保留

每个 Test ID 保存原始 stdout/stderr、JUnit XML、数据库断言快照和必要的脱敏 Task/batch/current 状态到表中路径。总索引 `artifacts/acceptance/M4/index.json` 必须记录 commit SHA、环境/镜像/tzdata 摘要、fixture manifest checksum、命令、退出码、开始/结束时间和证据 checksum。Acceptance Record 只能引用实际存在且 checksum 匹配的证据；任何 `PLANNED / NOT_VERIFIED` fixture 或 `not_run` 用例都不能支持 GO。
