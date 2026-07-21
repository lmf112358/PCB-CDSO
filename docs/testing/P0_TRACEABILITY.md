# PRD P0 追踪矩阵

| 属性 | 值 |
|---|---|
| 状态 | approved |
| PRD 基线 | `docs/product/PRD_v0.6.md` v0.6 |
| 规则 | 每条 P0 只有一个 Primary Milestone；其他阶段只能作为依赖或最终复验 |

| P0 ID | 需求摘要 | Primary Milestone | 必须在阶段前批准的 Feature Spec | 最低自动化/验收证据 |
|---|---|---|---|---|
| P0_01 | Docker/MySQL/Redis/前后端/迁移 | M0 | `docs/specs/m0/repository-runtime-baseline.md` | 空库启动、迁移/重启、health、build、CI |
| P0_02 | 两角色认证、归属、账号维护 | M1 | `docs/specs/m1/identity-and-ownership.md` | 登录/停用/转交、跨 Owner 403、审计 |
| P0_03 | 三模板和不可变快照 | M1 | `docs/specs/m1/template-lifecycle.md` | 发布事务、缺引用失败、已发布不可变 |
| P0_04 | 类 Codex 连续对话、8 阶段和影响分析 | M2 | `docs/specs/m2/expert-conversation-workspace.md` | 消息流、Composer、确认卡/工具卡、恢复、409/422 |
| P0_05 | 空间层级、唯一工序、覆盖门禁 | M2 | `docs/specs/m2/space-process-binding.md` | 主工序遗漏、唯一绑定、面积 3%、300 区域 |
| P0_06 | 工艺环境和冷量/计划/蓄冷采集 | M2 | `docs/specs/m2/cooling-input-registry.md` | 字段类型/单位、PCW 明确值/0、蓄冷只保存 |
| P0_07 | 首轮自动气象任务、Provider、任务坞和 CSV | M4 | `docs/specs/m1/project-weather-dispatch.md`；`docs/specs/m4/weather-ingestion.md` | 原子触发、2 秒内同一 task id 可见、六阶段、失败恢复、UTC |
| P0_08 | 静态公式、中间值和聚合 | M3 | `docs/specs/m3/static-cooling-calculation.md` | 三基准、单位、分流、五维守恒、血缘 |
| P0_09 | 三年仿真、七天预测、每小时刷新 | M4 | `docs/specs/m4/simulation-and-forecast.md` | 24h golden、三年/168h、DST、任务乱序/恢复 |
| P0_10 | 五 Tab 结果中心 | M5 | `docs/specs/m5/results-workspace.md` | Tab/筛选保持、有效/失效、API/UI 对账 |
| P0_11 | 区域详情、图表、五维筛选/URL | M5 | `docs/specs/m5/analytics-and-zone-detail.md` | 三次交互定位、五维查询、URL 恢复、权限 |
| P0_12 | 中英文和明暗主题 | M5 | `docs/specs/m5/i18n-and-themes.md` | 5 页面 × 2 locale × 2 theme、缺 key 构建失败 |
| P0_13 | 三模板和三个示例项目 | M1 | `docs/specs/m1/template-demo-seeds.md` | 三模板可选/复制；HDI 完整，另两项目只读；M6 复验 |
| P0_14 | 单元/契约/E2E/主题/空库验收 | M6 | `docs/specs/m6/release-acceptance.md` | PRD 七个验收剧本、治理/测试/部署证据、M0-M5 回归 |

## 使用规则

1. 创建 Feature Spec 时把对应 P0 ID 写入元数据和验收条件。
2. 一个 Spec 可覆盖多个 P0，但测试追踪必须逐 ID 列出。
3. Primary Milestone 改动需要 PRD/治理评审，不允许在 Issue 中临时移动。
4. Milestone 进入 verified 前，该阶段所有 Primary P0 必须有通过证据。
5. M6 执行 P0_14，并复验 M0-M5；复验不改变其他 P0 的 Primary Milestone。
