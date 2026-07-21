# PCB-CDSO v0.6 开发 SOP 治理设计

| 属性 | 内容 |
|---|---|
| 状态 | approved |
| 日期 | 2026-07-21 |
| 主仓库 | GitHub |
| 目标目录 | `E:\lmf\PCB-CDSO` |
| 产品基线 | `PRD_v0.6.md` |
| 团队约束 | 2 名全栈开发，1.5 周，多个异构 AI Agent 协作 |

## 1. 目标

建立一套可由人类开发者、Codex、Claude Code、Coder 等共同执行的开发治理体系，使 PCB-CDSO v0.6 按阶段完成规格、测试、实现、审查和验收。体系必须保证：需求来源唯一、接口与数据契约版本化、测试先于实现、Agent 互不覆盖、Git 历史可审计、未通过质量门禁的功能不能合并到主分支。

## 2. 方法选择

采用 SDD 主导、TDD 落地的混合方法：

```text
PRD
  --> Milestone Spec
      --> Feature Spec
          --> Implementation Plan
              --> Failing Test
                  --> Minimal Implementation
                      --> Refactor
                          --> Pull Request
                              --> CI + Review + Acceptance
```

SDD 负责冻结边界、行为、接口、状态机和验收条件；TDD 负责证明每个行为已实现。只写测试但没有规格会导致跨模块口径漂移，只写规格但没有测试会导致验收依赖人工解释，因此两者不能互相替代。

## 3. 单一事实源

事实优先级从高到低如下：

1. 已批准 PRD：产品范围、用户价值和版本边界。
2. 已接受 ADR：不可逆或跨模块技术决策。
3. 已批准 Milestone Spec：阶段目标、范围和质量门禁。
4. 已批准 Feature Spec：行为、状态、接口、失败路径和验收条件。
5. 已合并机器契约：OpenAPI、JSON Schema、数据库迁移、seed manifest。
6. 已合并测试和 fixture：可执行行为与数值基准。
7. Implementation Plan：实现顺序，不得覆盖上层规格。
8. Issue、PR 描述和 Agent 对话：协作上下文，不是永久事实源。

发生冲突时停止实现并修改较低层文档；如果确需改变高层事实，先提交 ADR 或 PRD 变更。聊天记录、Agent 记忆和未合并分支不得被视为已批准需求。

## 4. 目标仓库结构

```text
PCB-CDSO/
|-- AGENTS.md
|-- README.md
|-- Makefile
|-- docs/
|   |-- product/PRD_v0.6.md
|   |-- sop/DEVELOPMENT_SOP.md
|   |-- architecture/
|   |   |-- system-context.md
|   |   |-- data-flow.md
|   |   `-- adr/
|   |-- milestones/
|   |-- specs/
|   |-- plans/
|   |-- testing/
|   `-- handoffs/
|-- contracts/
|   |-- openapi/
|   |-- schemas/
|   `-- seeds/
|-- fixtures/
|   |-- acceptance/
|   |-- weather/
|   `-- calculation/
|-- scripts/quality/
|-- apps/web/
|-- services/api/
|-- packages/contracts/
`-- infra/
```

每个目录只有一个主要职责。前后端共享类型从机器契约生成，禁止手工维护两套相同枚举。领域公式、状态机和数据访问层分离，保证公式可在无数据库和无 UI 条件下测试。

## 5. 阶段开发模型

开发按纵向可运行切片推进，而不是先完成全部后端再完成全部前端。建议阶段：

| 阶段 | 可观察交付物 | 主要门禁 |
|---|---|---|
| M0 仓库与契约基线 | 空库启动、统一命令、CI、PRD、ADR、seed/schema 骨架 | 全新环境一条命令启动；lint/test 命令可重复 |
| M1 身份、模板与项目 | 首个管理员、工程师账号、三模板快照、项目创建 | 权限测试、发布不可变测试、空库 E2E |
| M2 八阶段受控采集 | 问答、字段注册表、强校验、保存恢复、revision 冲突 | 状态机单元测试、契约测试、关键 E2E |
| M3 静态计算 | 分项公式、低/中温与 PCW 分流、五维聚合、血缘 | 基准 fixture 数值测试、单位测试、聚合守恒测试 |
| M4 气象与动态仿真 | CSV/Provider、三年历史、七天预测、任务状态 | 时间轴、DST、幂等、乱序任务和恢复测试 |
| M5 结果中心 | 多 Tab 图表、区域下钻、双语主题 | 查询口径、权限、筛选保持和截图 |
| M6 导出与收口 | CSV、示例、审计、部署和最终验收 | CSV 行语义、性能、部署和 PRD 验收剧本 |

每个阶段开始前必须有批准的 Milestone Spec，结束时必须生成验收记录。阶段未过门禁时不能用关闭校验、隐藏失败或替换为静态假数据的方式宣布完成。

## 6. 测试策略

使用测试金字塔和风险驱动分层：

- 单元测试：领域公式、单位换算、状态转换、校验器、系数插值。
- 属性/不变量测试：负荷非负、聚合守恒、TOTAL 不重复计数、快照不可变。
- 契约测试：OpenAPI、错误码、JSON Schema、前后端生成类型。
- 集成测试：MySQL、Redis/Celery、批次原子切换、迁移和权限边界。
- E2E：管理员发布、工程师八阶段采集、静态计算、仿真预测、CSV 导出。
- 视觉测试：中文/英文乘明/暗主题，在固定桌面视口进行截图比较。
- 性能基线：记录 30 区域和 300 区域数据规模，不把未经测量的估计写成事实。
- 专家验收：软件公式基准与专家黄金样例分离；专家未签认前只标记软件验证通过。

每个功能遵循 Red-Green-Refactor：先提交会因目标行为缺失而失败的测试，确认失败原因正确，再写最小实现，通过后重构。修复缺陷必须先增加能复现问题的回归测试。

## 7. Git 与 GitHub 模型

GitHub 是唯一主仓库和合并入口。采用受保护的 `main` 加短生命周期分支：

- `feat/<issue>-<slug>`：功能。
- `fix/<issue>-<slug>`：缺陷。
- `spec/<issue>-<slug>`：规格或 ADR。
- `chore/<issue>-<slug>`：工具和基础设施。

每个 Agent 使用独立 worktree 和分支；禁止多个 Agent 在同一工作目录或同一分支写入。一个分支只服务一个明确 Issue，建议一天内合并。提交采用 Conventional Commits，提交粒度对应一个可解释且通过测试的变化。

`main` 禁止直接推送，必须通过 PR。必需检查至少包含格式、lint、类型、单元、契约、集成、关键 E2E、迁移检查、secret scan 和构建。PR 必须链接 Issue/Spec，列出范围、测试证据、数据迁移、风险和回滚方式。合并采用 squash，PR 标题作为最终提交信息。

## 8. 多 Agent 统一协议

所有工具必须先读取根目录 `AGENTS.md`、当前 Milestone Spec、目标 Feature Spec 和相关契约。统一角色如下：

- Orchestrator：唯一任务调度者，维护依赖图、Issue 状态和合并顺序，不同时承担所有实现。
- Spec Agent：编写或修订规格、ADR 和验收条件，不在未批准规格上编码。
- Implementer：在独立 worktree 中按 Plan 和 TDD 实现。
- Test Agent：专注失败路径、边界、fixture 和验收自动化。
- Reviewer：不读取实现者的思考过程，只基于 diff、规格和测试做独立审查。
- Release/Acceptance Agent：在干净环境执行阶段验收并生成证据。

Agent 领取任务前必须写明目标、允许修改的文件、禁止范围、依赖、验收命令和预计交付。交接必须记录分支、HEAD、已完成内容、测试结果、剩余风险和下一动作。Agent 不得修改任务范围外文件，不得自行改变已批准契约，不得以删除测试获得绿色 CI。

同一文件只允许一个活跃写入所有者。接口变更先合并契约 PR，再并行生成前后端实现。发生冲突时由 Orchestrator 按依赖顺序重新基于最新 `main` 派发，禁止让两个 Agent 互相覆盖式解决冲突。

## 9. 必备文档与数据

开工前至少需要：

- PRD v0.6、系统上下文、数据流、领域词汇表。
- 技术栈 ADR、认证 ADR、异步任务 ADR、逐时数据存储 ADR。
- 六个 Milestone Spec 及阶段验收矩阵。
- OpenAPI 基线、统一错误模型、字段 registry schema、seed manifest schema。
- 三个产品模板种子，HDI 全量主/辅助工序，双语问题与选项。
- 标准气象 CSV schema 及三年 fixture、七天 fixture、缺失/重复/DST 反例。
- 至少三份静态软件基准、一个 24 小时动态基准、聚合守恒基准。
- 两角色权限矩阵、并发 revision 和旧任务乱序 fixture。
- 中文/英文乘明/暗主题截图基线和 CSV 黄金文件。
- 环境变量说明、Docker Compose、数据库迁移和备份恢复说明。

缺失数据必须登记为阻断或显式假设，注明责任人、截止阶段和验证方式。未经专家签认的参数以 `UNVERIFIED` 进入版本化 seed，不能伪装为法规硬规则。

## 10. SOP 交付包

最终开发治理包应包含：

1. `docs/sop/DEVELOPMENT_SOP.md`：从准备到验收的完整操作流程。
2. `AGENTS.md`：所有 Agent 的强制规则、事实源和命令。
3. Milestone Spec、Feature Spec、ADR、实施计划、测试计划、验收记录和 Agent handoff 模板。
4. GitHub Issue/PR 模板、CODEOWNERS、分支保护与 CI 检查清单。
5. 数据/fixture 准备矩阵以及专家验证状态表。
6. 每阶段 Definition of Ready、Definition of Done 和可复制命令。

## 11. 成功标准

- 新 Agent 在不读取聊天记录的情况下能在 15 分钟内找到当前规格、任务、契约和验证命令。
- 任一需求、接口、seed 或公式变更都能追溯到 Issue、Spec/ADR、测试和 PR。
- 两个 Agent 不能在流程上合法地同时修改同一文件。
- 任一阶段均可在干净环境通过一组确定命令得到成功或失败结论。
- GitHub PR 的绿色状态来自真实测试和验收证据，不来自跳过测试或降低门禁。
- 软件验证与专家验证状态始终分离并可查询。
