# M6 导出与试开发收口

| 属性 | 值 |
|---|---|
| 状态 | approved |
| Owner | API + Web + QA + Acceptance |
| 时间盒 | 1 天目标 |
| PRD 追踪 | P0_12、P0_13、P0_14；第 8、10、11.e 章 |

## 目标

按当前筛选异步导出五维逐时 CSV，完成示例、审计、关键测试、Docker Compose 部署和 v0.6 试开发验收。

## 范围

包含：export estimate/task/download、长表 CSV、百万行阻断、重复任务复用、24 小时清理、三个示例项目、审计、性能基线、部署/回滚/备份、最终验收记录。

不包含：Excel、PDF、JSON 报告、图片报告、P&ID、移动端、生产 SLA、动态精度承诺和专家黄金样例签认。

## Definition of Ready

- [ ] M5 verified。
- [ ] CSV schema 和 golden approved。
- [ ] 部署硬件/浏览器/性能环境已记录。
- [ ] PRD P0 追踪矩阵无缺口。
- [ ] M6 Test Plan 和 Acceptance Agent 已确定。

## 导出不变量

- CSV 每行是时间 × 实体 × cooling_type。
- 选择全部冷源最多输出 CHW_LOW、CHW_MEDIUM、PCW、TOTAL_REFERENCE；TOTAL 不与分项再次相加。
- 功能区分项可输出原始系数；TOTAL/聚合只输出 effective combined coefficient。
- 同时输出 UTC、本地时间和 IANA 时区，编码为 UTF-8。
- UI 与 CSV 使用同一 analytics 查询；展开行数按导出查询计算。
- 失效批次终止导出并禁止下载；临时文件成功后保留 24 小时。

## 测试矩阵

| 层级 | 必测行为 |
|---|---|
| Contract | estimate/task/status/download、403/409/422、expiresAt |
| Integration | 同查询、百万行阻断、幂等复用、失效终止、24h 清理 |
| Golden | CSV 列、行数、空值、浮点、BOM、时间和 checksum |
| E2E | 五维导出、跨 owner 与不存在导出单项均 404、列表 200 filtered、scope 内已定位但角色不足的写操作 403、归档项目只读导出 |
| Deployment | 空库/seed 启动、重启、备份恢复、日志和 health |
| Performance | 30 区域硬门禁；300 区域记录环境、耗时、存储和内存 |

## 演示脚本

按 LDI 工艺导出历史逐时 CSV，核对 estimate、任务进度、golden/checksum 和 24 小时过期；另一个工程师分别下载跨 owner 的已存在导出与随机不存在导出，两者返回不可区分的 404，导出列表返回 200 filtered；对 scope 内已定位但角色缺少写权限的操作返回 403；启动三个演示项目；在干净环境部署、重启和恢复；执行 PRD 六个既有验收剧本，并执行验收剧本 7：首轮产品/地理确认后自动原子创建气象任务，2 秒内对话工具卡与全局任务坞显示同一 task id，验证六阶段进度、失败恢复、刷新恢复、UTC 数据和旧 revision 防覆盖。

## 质量门禁与 Definition of Done

- [ ] P0_12、P0_13、P0_14 全部有证据。
- [ ] CSV golden、权限、失效和清理通过。
- [ ] 三个示例项目可演示，HDI 主链完整。
- [ ] 空库部署、重启、备份/恢复和回滚说明可执行。
- [ ] 30/300 区域性能结果附环境，超门限有 go/no-go 结论。
- [ ] 软件验证和专家待验证标签清楚。
- [ ] M6 Acceptance Record 为 GO；合并 main 后创建 `trial-v0.6.0` 标签。

## 停止条件

任一越权、CSV 与界面口径不一致、TOTAL 重复计数、失效结果可下载、干净部署失败、关键测试失败或把经验模型宣称为专家验证均强制 NO-GO。
