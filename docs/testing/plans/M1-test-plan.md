# M1 项目创建与气象任务可靠派发测试计划

| 属性 | 值 |
|---|---|
| 状态 | approved |
| Spec | `docs/specs/m1/project-weather-dispatch.md` v1.0.0 |
| Owner | M1 Test Agent / Acceptance Agent |
| Fixture Version | `fixtures/acceptance/M1/project-weather-dispatch/1.0.0`，PLANNED / NOT_VERIFIED |

本计划冻结未来 M1 实现的可执行门禁。当前 PRD 重基线只交付规格，不声称下列尚未实现的运行时测试已经通过。

## 风险排序

| 风险 | 影响 | 概率 | 测试策略 | PR 门禁 |
|---|---|---|---|---|
| 项目已写入但 Task/Outbox 缺失 | high | medium | 写点/pre-commit 故障断言零行；commit outcome unknown 用同键重放解析 | yes |
| 重试或并发生成重复项目/任务 | high | high | 串行重放、并发屏障、数据库唯一约束检查 | yes |
| dispatcher 不可用导致任务丢失 | high | medium | 停止 fake dispatcher，查询持久化状态，再恢复派发 | yes |
| 跨 owner 存在性泄漏 | high | medium | `ENGINEER` scoped lookup；越权已存在 id 与随机 id 的 404 envelope/message/timing/log 对比 | yes |
| API 在 2 秒内无法查询持久化 task id | high | medium | API 响应与两个 `GET /tasks` 查询比对同 id 和单调时钟 | yes |
| publish 后确认部分提交或重复执行 | high | medium | 确认事务双写点故障、reconciler、持久化 Worker execution record | yes |
| M1 越界访问真实 Provider | high | low | 网络封锁与调用 spy，断言零外部气象请求和零气象批次 | yes |

## 测试用例

| Test ID | 层级 | 前置条件 | 输入/动作 | 预期结果 | 精确命令 | 证据路径 |
|---|---|---|---|---|---|---|
| M1-C-001 | contract | API、OpenAPI；已发布模板 `tpl-hdi-v1`；`ENGINEER` A token | 合法 `CreateProject`：`深圳 HDI 工厂`、模板、`CN/广东省/深圳市/Asia/Shanghai`、key `m1-happy-001` | `201`；响应含 project、snapshotIds、`inputRevision=1`、`weatherTaskId`；Task 初态 `DISPATCH_PENDING` | `python -m pytest tests/contracts/test_create_project_contract.py::test_create_project_success -q` | `artifacts/acceptance/M1/M1-C-001.txt` |
| M1-C-002 | contract | 同上 | 逐项缺失/非法 name、templateVersionId、countryCode、adminArea、city、timezone、idempotencyKey；伪造 actorId | 每例 `422 VALIDATION_FAILED` 或认证 actor 生效；零写入；稳定字段错误码 | `python -m pytest tests/contracts/test_create_project_contract.py::test_create_project_validation_matrix -q` | `artifacts/acceptance/M1/M1-C-002.txt` |
| M1-I-001 | integration | 空 MySQL；事务故障注入开启 | 分别令幂等记录、Project、快照、Task、Outbox 写入及 pre-commit 失败 | 每个子例 `503 TRANSACTION_FAILED`；幂等记录与四组业务记录均零行，无占坑 | `python -m pytest tests/integration/test_project_weather_transaction.py::test_precommit_failures_roll_back_idempotency_and_aggregate -q` | `artifacts/acceptance/M1/M1-I-001.txt` |
| M1-I-002 | integration | 空 MySQL；`ENGINEER` A | 同一 `actorId + m1-replay-001` 串行提交两次相同 canonical hash | 首次 `201`、重放 `200`；project、snapshotIds、task id 相同；每组仅一套记录 | `python -m pytest tests/integration/test_project_weather_idempotency.py::test_serial_replay_returns_original_aggregate -q` | `artifacts/acceptance/M1/M1-I-002.txt` |
| M1-I-003 | integration | 空 MySQL；并发屏障；`ENGINEER` A | 20 个并发请求使用同一 key 和相同 canonical hash | winner `201`，loser 等待后 `200`；仅一个幂等记录、project、task、OutboxEvent | `python -m pytest tests/integration/test_project_weather_idempotency.py::test_concurrent_same_hash_has_one_winner -q` | `artifacts/acceptance/M1/M1-I-003.txt` |
| M1-I-004 | integration | 已完成 key `m1-conflict-001` | 同 actor、同 key 改 city 或 templateVersionId 后再次提交 | `409 IDEMPOTENCY_CONFLICT`；数据库无新增或修改 | `python -m pytest tests/integration/test_project_weather_idempotency.py::test_same_key_different_input_conflicts -q` | `artifacts/acceptance/M1/M1-I-004.txt` |
| M1-I-005 | integration | `ENGINEER` A/B；空 MySQL | A、B 使用相同 key 各建一个项目 | 两次均可创建；各自 owner 正确；证明去重作用域含 actorId | `python -m pytest tests/integration/test_project_weather_idempotency.py::test_idempotency_key_is_scoped_by_actor -q` | `artifacts/acceptance/M1/M1-I-005.txt` |
| M1-I-006 | integration | fake dispatcher 已停止 | 创建项目并连续查询 Task/Outbox | 项目创建成功；同一 Task 持续 `DISPATCH_PENDING`；Outbox 未丢失且可重试；没有第二 Task | `python -m pytest tests/integration/test_weather_outbox_dispatch.py::test_dispatcher_unavailable_preserves_pending_task -q` | `artifacts/acceptance/M1/M1-I-006.txt` |
| M1-I-007 | integration | 完成 M1-I-006；启动 fake dispatcher | 触发重试并等待一次派发 | 复用原 event/task id；Task 条件转为 `QUEUED`；派发审计和重试次数正确 | `python -m pytest tests/integration/test_weather_outbox_dispatch.py::test_recovery_dispatches_original_task -q` | `artifacts/acceptance/M1/M1-I-007.txt` |
| M1-I-008A | integration | broker publish 成功；注入确认事务 Outbox metadata 写失败 | 执行确认事务 | Outbox 未 dispatched、attempt metadata 未部分提交、Task 保持 `DISPATCH_PENDING`；重发同 event/task | `python -m pytest tests/integration/test_weather_outbox_dispatch.py::test_outbox_confirmation_write_failure_rolls_back_task -q` | `artifacts/acceptance/M1/M1-I-008A.txt` |
| M1-I-008B | integration | broker publish 成功；Outbox metadata 写后注入 Task 转态写失败 | 执行确认事务 | Outbox metadata 回滚、Task 保持 `DISPATCH_PENDING`；reconciler/dispatcher 重发同 event/task | `python -m pytest tests/integration/test_weather_outbox_dispatch.py::test_task_transition_failure_rolls_back_outbox_confirmation -q` | `artifacts/acceptance/M1/M1-I-008B.txt` |
| M1-I-008C | integration | broker publish 成功；确认事务 commit 回包断连 | 执行确认并运行 reconciler | 不凭客户端异常判定完成；reconciler 读取 Outbox/Task 持久化组合，原子对账或重发同事件，最终两者一致且无新 Task | `python -m pytest tests/integration/test_weather_outbox_dispatch.py::test_confirmation_commit_disconnect_is_reconciled -q` | `artifacts/acceptance/M1/M1-I-008C.txt` |
| M1-I-009 | integration/security | `ENGINEER` A/B、`ADMIN`；A 已有项目和 Task；固定随机不存在 id | B 列表、用 A 的存在 id 与随机 id 单项查询；A/ADMIN 查不存在 id；Admin 查 A 资源 | B 列表 `200` 且过滤；两种 B 单项及 owner/ADMIN 不存在均为相同 `404` envelope/message/timing class；Admin 授权查询 `200`；外部响应、日志、审计无敏感字段 | `python -m pytest tests/integration/test_project_task_authorization.py -q` | `artifacts/acceptance/M1/M1-I-009.txt` |
| M1-I-010 | integration | fake dispatcher/Worker；网络 deny；Provider spy | 完成一次 fake 派发链路 | Provider 调用为 0、下载文件为 0、气象 batch 为 0；允许 Task 模拟到 `SUCCEEDED` | `python -m pytest tests/integration/test_weather_outbox_dispatch.py::test_m1_fake_dispatch_never_downloads_weather -q` | `artifacts/acceptance/M1/M1-I-010.txt` |
| M1-I-011 | integration | 同 actor/key；commit 已发送后断开数据库响应 | 首次请求得到 outcome unknown，再以同 key/hash 重放 | 不预断言零行；重放最终为一次安全 `201` 或原结果 `200`；数据库最终仅一个幂等记录和聚合 | `python -m pytest tests/integration/test_project_weather_transaction.py::test_commit_disconnect_resolved_by_same_key_replay -q` | `artifacts/acceptance/M1/M1-I-011.txt` |
| M1-I-012 | integration | 同 actor/key；并发屏障 | 两个不同 canonical hash 同时竞争 | 唯一 winner `201`；loser 等待后 `409`；只有 winner 聚合 | `python -m pytest tests/integration/test_project_weather_idempotency.py::test_concurrent_different_hash_rejects_loser -q` | `artifacts/acceptance/M1/M1-I-012.txt` |
| M1-I-013 | integration | 首次请求在 pre-commit 确定失败 | 用相同 actor/key/hash 重试 | 首次无幂等占坑；重试可 `201` 且最终仅一个聚合 | `python -m pytest tests/integration/test_project_weather_idempotency.py::test_same_key_retry_after_deterministic_failure -q` | `artifacts/acceptance/M1/M1-I-013.txt` |
| M1-I-014 | integration | 构造两类 Outbox/Task 不一致；fake broker | 运行 reconciler | 未确认 publish 的事件重发；可证明已确认的记录原子对账；最终 Outbox dispatched 与 Task `QUEUED` 一致 | `python -m pytest tests/integration/test_weather_outbox_dispatch.py::test_reconciler_repairs_or_redelivers_inconsistent_state -q` | `artifacts/acceptance/M1/M1-I-014.txt` |
| M1-I-015A | integration/real-MySQL | `weather_dispatch_probe`、execution、Task 表已迁移；fake Worker 故障注入 | 领取后、effect 事务前崩溃，lease 到期后重投 | 首次无 probe 且无 terminal execution；重投在同一事务提交 probe、execution `SUCCEEDED`、Task CAS `RUNNING -> SUCCEEDED`；probe 恰一行，Task 最终 `SUCCEEDED` | `python -m pytest tests/integration/test_weather_outbox_dispatch.py::test_crash_before_effect_retries_and_commits_one_probe -q` | `artifacts/acceptance/M1/M1-I-015A.txt` |
| M1-I-015B | integration/real-MySQL | 同上；可在三项事务 commit 后、broker ack 前崩溃 | 提交 probe+execution+Task 后崩溃并重投 | 重投复用相同 effect/execution/Task；真实 MySQL probe 恰一行，execution 与 Task 均为 `SUCCEEDED`，Task 不倒退 | `python -m pytest tests/integration/test_weather_outbox_dispatch.py::test_crash_after_effect_commit_before_ack_reuses_one_probe -q` | `artifacts/acceptance/M1/M1-I-015B.txt` |
| M1-P-001 | API/performance | Docker Compose M1 环境；`ENGINEER` A token；dispatcher 可开或关 | 从 `POST /projects` 请求开始计时，捕获 task id，轮询 `GET /tasks/{id}` 与列表 | `<=2.0s` 两个 GET 均返回同一持久化 task id；不涉及 UI、dispatcher、Worker 或下载 | `python -m pytest tests/performance/test_initial_weather_task_visibility.py::test_same_persisted_task_id_visible_within_two_seconds -q` | `artifacts/acceptance/M1/M1-P-001.json` |
| M1-G-001 | governance | 仓库工作树含本规格和计划 | 执行治理、占位符与 Markdown diff 检查 | governance valid；无未完成标记；`git diff --check` 零错误 | `python scripts/quality/check_governance.py` | `artifacts/acceptance/M1/M1-G-001.txt` |

## Fixture

| Dataset ID | 版本 | 状态 | 内容与来源 | 校验 |
|---|---|---|---|---|
| `m1-project-weather-dispatch` | 1.0.0 | PLANNED / NOT_VERIFIED | 计划包含固定 `ADMIN`、`ENGINEER` A/B、已发布模板、标准地理输入和幂等键集合 | 文件尚不存在，不能声明 checksum 或签名 |
| `m1-transaction-faults` | 1.0.0 | PLANNED / NOT_VERIFIED | 计划包含业务写点、pre-commit、commit outcome unknown 故障 | 文件尚不存在，不能声明验证结果 |
| `m1-dispatch-recovery` | 1.0.0 | PLANNED / NOT_VERIFIED | 计划包含 publish/确认双写点、reconciler、Worker 崩溃重投 | 文件尚不存在，不能声明执行计数 |

计划路径为 `fixtures/acceptance/M1/project-weather-dispatch/1.0.0/manifest.json`。只有文件实际创建、manifest schema 通过、所有文件 checksum 已生成并匹配、producer 与独立 verifier 身份不同、验证记录存在且 fixture 测试通过后，状态才可从 `PLANNED / NOT_VERIFIED` 升为 `SOFTWARE_VERIFIED`；在此之前不得作为通过证据。测试不得依赖真实 Provider、外网、生产账号或不稳定当前时间。

## 环境

- Windows 或 Linux Docker host；Docker Compose 单机，至少 8 核 CPU、16 GB 内存、SSD。
- MySQL 与 Redis 使用仓库锁定镜像摘要；每个原子性/幂等测试从空 schema 或唯一测试 schema 开始。
- Python 3.12 与仓库锁文件依赖。
- 应用默认 UTC；项目输入时区固定 `Asia/Shanghai`；测试时钟可冻结。
- 外部网络在 M1 测试中 deny，fake dispatcher/Worker 是唯一允许的派发实现。
- 性能证据必须记录 OS、CPU、内存、容器镜像摘要、开始/结束单调时钟和每次观测值。

## 执行顺序与门禁

从仓库根目录依次执行；每条命令退出码必须为 0：

```powershell
python scripts/quality/check_governance.py
python -m unittest tests.governance.test_check_governance -v
python -m pytest tests/contracts/test_create_project_contract.py -q
python -m pytest tests/integration/test_project_weather_transaction.py tests/integration/test_project_weather_idempotency.py -q
python -m pytest tests/integration/test_weather_outbox_dispatch.py tests/integration/test_project_task_authorization.py -q
python -m pytest tests/performance/test_initial_weather_task_visibility.py -q
git diff --check -- docs/specs/m1 docs/testing/plans/M1-test-plan.md
```

通过标准：上述测试零失败；pre-commit 故障全部零行，commit unknown 均由同键重放收敛；并发同 hash 20/20 返回同一聚合，不同 hash loser 为 `409`；列表过滤正确，跨 owner 存在 id 与随机 id 的单项响应/日志均为不可区分的 `404`；两项 Worker 崩溃测试在真实 MySQL 中均断言唯一 probe 一行、execution `SUCCEEDED`、Task 最终 `SUCCEEDED` 且重投不倒退；Provider 调用数为 0；`M1-P-001` 每次运行均 `<=2.0s` 且 API/GET tasks 同 task id。未完成标记扫描的合格结果是无匹配。M1 不把工具卡、任务坞、Composer、刷新或重登作为 gate，这些由 M2 和最终跨里程碑验收覆盖。

## 失败分类

| 分类 | 判定 | 处理人 | 门禁行为 |
|---|---|---|---|
| 产品缺陷 | 实现违反本规格、HTTP/状态/权限/原子性断言 | M1 Backend Owner | 阻断合并，修复后全量重跑 |
| 测试缺陷 | 测试与已批准规格不一致或存在非确定性 | M1 Test Owner | 修复测试并保留前后证据，不得放宽产品断言 |
| Fixture 缺陷 | checksum、seed、独立验证记录不一致 | Fixture Producer 与独立 Verifier | 阻断全部使用该 fixture 的结果 |
| 环境缺陷 | 容器、磁盘或硬件不满足已记录基线 | Acceptance Agent | 记录环境证据后重建环境；不得标记 pass |
| 性能缺陷 | 合格环境下同 task id 可见超过 2 秒 | M1 Backend Owner | 阻断 P0_07 前置契约；下载是否完成不影响判定 |
| 专家待确认 | 仅涉及真实 Provider 或气象质量语义 | M4 Product/Domain Owner | 不阻断 M1 fake 派发；进入 M4 风险登记 |

## 结果与证据保留

每个 Test ID 的原始 stdout/stderr、JUnit XML 和数据库断言快照写入表中固定路径；总索引为 `artifacts/acceptance/M1/index.json`，包含 commit SHA、环境摘要、命令、退出码、开始/结束时间和证据 checksum。M1 Acceptance Record 只能引用实际存在且 checksum 匹配的证据，所有 required 用例通过后才能判定 GO。
