# PRD v0.6 重基线影响设计

| 字段 | 内容 |
|---|---|
| 状态 | approved-by-product |
| 批准方式 | 用户选择方案 A |
| 基线 | `a4c3288a1ecb6a88453dc6994515a83e4bb62958` |
| 目标 | 保留新版 PRD 产品意图，恢复稳定追踪标识，并将新增能力分配到 M1、M2、M4，而不返工 M0 |

## 1. 已确认的产品变化

新版 PRD 将以下三项提升为 v0.6 硬约束：

1. 固定 PCB 工艺链是空间、问题、环境规则、生产负荷和结果按工艺汇总的共同上游。
2. 数据采集采用类 Codex 连续消息流，包含底部 Composer、结构化确认卡、系统校验卡和工具执行卡，不回退为分散表单。
3. 首轮确认产品和地理信息后，系统自动创建过去三年逐时气象抓取任务；任务不阻断后续问答，并通过对话工具卡和右下角全局任务坞持续呈现。

静态计算公式、经验仿真、七天预测、CSV 输出、两角色权限和桌面 Web 范围没有改变。

## 2. 方案选择

### 方案 A：保留 PRD 变化并重排下游里程碑（采用）

- 恢复 `P0_01` 至 `P0_14` 稳定编号，但不撤销新版需求文字。
- M0 作为可复用基础设施保持关闭，不追溯加入产品业务功能。
- M1 承担项目首轮确认、地理字段、可靠事件和气象任务创建。
- M2 承担连续消息流、Composer、结构化卡片和全局任务坞。
- M4 承担真实 Provider、三年数据质量、城市变更失效和仿真消费。

### 未采用方案

- 只修改 PRD、不更新下游文档：会使 Agent 按旧里程碑实现，产生规格漂移。
- 将新增能力塞回 M0：会推翻已验证基础阶段，并扩大关键路径。

## 3. 里程碑边界

| 里程碑 | 新增或调整后的职责 | 明确不包含 |
|---|---|---|
| M0 | 保留 MySQL、Redis、Celery、通用任务契约、OpenAPI 和 Web 壳；记录新版 PRD 对后续阶段的影响 | 项目业务表、真实气象任务、对话工作台业务实现 |
| M1 | 管理员/工程师身份与模板；项目首轮确认；国家、省/州、城市、时区；项目事务写 Outbox；幂等创建气象任务 | 下载和清洗真实气象数据；完整 8 阶段问答 |
| M2 | 类 Codex 消息流；Composer；确认/校验/工具卡；8 阶段状态机；任务坞；刷新、切 Tab、重新登录恢复 | 真实气象 Provider；仿真计算 |
| M3 | 静态计算、区域中间值、空间与工艺聚合 | 气象下载和动态仿真 |
| M4 | 三年气象 Provider、清洗、连续性校验、入库；城市 revision 变更；旧任务防覆盖；三年仿真和七天预测 | 前馈控制 |
| M5/M6 | 结果中心、导出、跨主题验收；新增气象任务剧本纳入最终回归 | 扩展为移动端或控制系统 |

## 4. 领域与数据流

首轮确认采用同步触发、异步执行：

```text
Engineer confirms product + geography + idempotency key
  -> MySQL transaction
       -> create Project(inputRevision=1)
       -> freeze template/conversation snapshots
       -> create OutboxEvent(WeatherFetchRequested)
       -> create/reuse Task(DISPATCH_PENDING)
  -> commit
  -> return Project + Task reference
  -> dispatcher publishes event at least once
  -> worker deduplicates by projectId + inputRevision + taskType
  -> task stages: LOCATE -> REQUEST -> DOWNLOAD -> CLEAN -> VALIDATE -> STORE
  -> only a task matching the current project revision may publish the current weather batch
```

项目创建、Outbox 事件和初始任务必须原子提交。下载不属于该事务，也不得阻塞问答。城市修改递增 `inputRevision`，使旧任务进入 `STALE` 或 `CANCELLED`；旧任务即使晚完成也不能成为 current。

## 5. 契约与状态机影响

需要在对应里程碑冻结以下契约：

- `POST /projects`：增加 `countryCode`、`adminArea`、`city`、`timezone` 和客户端幂等键；返回项目、快照标识和气象任务引用。
- `GET /tasks?projectId=&activeOnly=`：恢复当前用户可见的任务坞列表。
- `GET /tasks/{taskId}`：返回持久化的状态、阶段、处理量、总量、错误和可恢复操作。
- 任务状态至少包含 `DISPATCH_PENDING`、`QUEUED`、`RUNNING`、`SUCCEEDED`、`FAILED`、`CANCELLED`、`STALE`。
- 气象阶段包含 `LOCATE`、`REQUEST`、`DOWNLOAD`、`CLEAN`、`VALIDATE`、`STORE`。
- 所有项目和任务查询执行 Owner/Admin 权限过滤；工程师不能看到其他工程师的任务。

M0 的通用任务 Schema 可在 M1 兼容扩展，不能提前伪造真实业务端点。

## 6. UI 设计边界

M2 的桌面主工作区由四类消息组成：Agent 问题、用户回答、系统校验、工具执行。结构化计算字段只能通过确认卡提交；自然语言可以辅助解释和定位问题，但不能直接写入计算字段。

右下角任务坞：

- 默认宽 360px，最多显示三个活动摘要，可折叠为带数量的悬浮入口。
- 与对话工具卡使用相同 task id、阶段和色彩语义。
- 不遮挡 Composer 发送按钮；切换页面、刷新和重新登录不丢进度。
- 成功任务短暂保留后进入最近任务；失败任务持续显示重试和 CSV 恢复入口。
- 中文、英文、明暗主题使用同一套组件和设计令牌。

## 7. 错误与恢复

| 失败 | 系统行为 |
|---|---|
| 项目事务无法写 Outbox | 整体回滚，不创建孤立项目 |
| dispatcher 暂时失败 | Task 保持 `DISPATCH_PENDING`，后台重试，对话显示等待调度 |
| Provider 失败 | Task 进入 `FAILED`，保留结构化错误、重试和 CSV 上传入口 |
| 重复首轮请求 | 同一幂等键返回同一项目和同一 task id |
| 城市被修改 | 创建新 revision 和新任务；旧任务失效 |
| 旧任务晚完成 | 允许保留日志和数据批次，但禁止切换为 current |
| 浏览器刷新或重新登录 | 从 `GET /tasks` 恢复任务坞，不根据前端缓存猜测状态 |

## 8. 测试与验收调整

1. 治理测试继续要求 PRD 存在 `P0_01` 至 `P0_14`。
2. M1 增加项目、Outbox、Task 原子性，重复幂等键和无事件不建项目测试。
3. M2 增加连续消息流恢复、Composer 草稿、工具卡/任务坞同 task id、双语和明暗主题测试。
4. M4 增加六阶段进度、Provider 失败、CSV 恢复、城市修改和旧任务乱序完成测试。
5. 最终验收新增“首轮自动气象抓取与全局进度”剧本，2 秒指标只约束任务可见，不约束下载完成。

## 9. 下游文件更新范围

实施计划将更新：

- `docs/product/PRD_v0.6.md`
- `docs/testing/P0_TRACEABILITY.md`
- `docs/milestones/M0-repository-baseline.md`
- `docs/milestones/M1-identity-template-project.md`
- `docs/milestones/M2-controlled-data-collection.md`
- `docs/milestones/M4-weather-simulation-forecast.md`
- `docs/milestones/M6-export-delivery-closure.md`
- 对应 `docs/specs/m1/`、`docs/specs/m2/`、`docs/specs/m4/` 和测试计划
- `contracts/schemas/task.schema.json` 与 `contracts/openapi/openapi.json` 仅在其负责里程碑按契约优先流程更新

## 10. 自检结论

- 无 TBD、TODO 或未分配能力。
- 没有将前馈控制、移动端或精准度承诺带入 v0.6。
- M0 基础能力与新版 PRD 不冲突，不需要返工。
- P0 稳定编号必须恢复，否则治理、追踪和验收全部失去连接。
- 新增能力已经分别归属 M1、M2、M4，不存在两个里程碑重复拥有同一交付结果。
