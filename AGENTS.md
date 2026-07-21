# PCB-CDSO Agent 协作宪法

本文件适用于整个仓库，是 Codex、Claude Code、Coder、IDE Agent 和人类开发者共同遵守的最低规则。工具私有提示不得覆盖本文件；如工具无法读取本文件，调度者必须把本文件和任务包一并提供。

## 1. 开始任务前

按顺序完成并在交接中确认：

1. 读取 `docs/product/PRD_v0.6.md` 的相关范围。
2. 读取当前 `docs/milestones/` 规格。
3. 读取目标 Feature Spec、相关 ADR、机器契约、fixture 和既有测试。
4. 运行 `git status --short --branch`，确认分支和工作树。
5. 记录任务包中的 base SHA、允许修改路径、禁止路径和验收命令。
6. 先运行基线测试；若失败，停止并报告既有失败，不把它冒充为本任务问题。

## 2. 事实优先级

```text
已批准 PRD
  > 已接受 ADR
  > 已批准 Milestone Spec
  > 已批准 Feature Spec
  > 已合并 OpenAPI / Schema / Migration / Seed
  > 已合并测试与 Golden Fixture
  > 已批准 Implementation Plan
  > Issue / PR 描述
  > Agent 对话与临时笔记
```

发现冲突时停止实现，在 Issue 中引用冲突位置，由 Orchestrator 决定修改哪个上游事实。Agent 不得自行选择“更合理”的解释后继续。

## 3. 统一角色

| 角色 | 责任 | 不得做的事 |
|---|---|---|
| Orchestrator | 拆分任务、维护依赖图、分配路径所有权、决定合并顺序 | 同时派两个写入者修改同一文件 |
| Spec Agent | 编写 Spec、ADR、验收条件和追踪矩阵 | 在规格未批准时实现产品代码 |
| Contract Agent | 冻结 OpenAPI、Schema、迁移和生成类型 | 同时实现多个消费者或改变产品语义 |
| Implementer | 按计划和 TDD 做最小实现 | 改动任务外范围或上游契约 |
| Test Agent | 设计失败路径、边界、fixture、E2E 和验收证据 | 只追求覆盖率而忽略行为 |
| Reviewer | 独立核对规格、diff、测试与风险 | 依赖实现者的口头解释代替证据 |
| Acceptance Agent | 在干净环境执行阶段剧本并签发记录 | 修改实现以让验收通过 |

同一 Agent 可在不同任务中承担不同角色，但同一 PR 的 Implementer 不得作为唯一 Reviewer 或最终 Acceptance Agent。

## 4. 标准任务包

任何 Agent 开始前必须收到以下字段；缺一项就返回 Orchestrator 补齐：

```yaml
issue: "GH-编号"
objective: "一个可观察结果"
role: "Spec | Contract | Implementer | Test | Reviewer | Acceptance"
base_sha: "40 位提交 SHA"
branch: "类型/issue-英文短名"
worktree: "绝对路径"
source_spec: "仓库相对路径"
allowed_paths:
  - "允许写入的路径"
forbidden_paths:
  - "明确禁止的路径"
dependencies:
  - "Issue、PR 或契约版本"
required_commands:
  - "可复制命令"
acceptance:
  - "Given/When/Then 或数值断言"
handoff_path: "docs/handoffs/记录文件.md"
```

任务目标只能包含一个主要结果。需要同时改变契约和多个消费者时，先建立契约任务，再分别建立消费者任务。

## 5. 分支、worktree 与文件所有权

- `main` 禁止直接开发和直接推送。
- 每个 Issue 使用独立短分支：`feat/`、`fix/`、`spec/` 或 `chore/`。
- 默认每个写入 Agent 使用独立 worktree。若本机透明加密或沙箱使 linked worktree 不可读，必须保存哈希/错误证据，退化为独立分支就地开发，并确保同时只有一个写入 Agent。
- GitHub Issue 是路径租约登记处。Orchestrator 在 Issue 中维护 `Active file lease` 清单；相交路径未释放前不得派发第二个写入任务。
- 路径租约统一为仓库相对 POSIX 路径并禁止 `..`；Windows 比较不区分大小写。目录租约覆盖全部子路径，glob 与任何实际匹配路径冲突；重命名同时租赁源和目标，生成文件也必须列入。符号链接按解析后的仓库内路径判断。单一 Orchestrator 是租约串行化入口，不允许两个调度者并发派发。
- Agent 只能修改 `allowed_paths`。发现任务外必要改动时先停下，请求扩展任务包。
- 接口变更先合并契约 PR，再从新 main 派发前端、后端、测试等消费者任务。
- 不得使用 `git reset --hard`、强推、删除他人分支、跳过 hooks 或批量覆盖冲突。
- Reviewer 只读检出 PR merge ref 或 PR head SHA；Acceptance Agent 只读检出候选 SHA/标签或合并后的干净 main。只读任务不申请文件租约，也不创建写分支；发现问题通过 review/Issue 返回 Implementer。只有需要提交审查文档时才另建 `spec/` 分支和独立任务包。

## 6. SDD 与 TDD

- 没有批准的 Feature Spec 和可判定验收条件，不写产品代码。
- 新行为先写失败测试并确认失败原因正确，再写最小实现，然后重构。
- 缺陷先写能复现问题的回归测试。
- OpenAPI/Schema 变化先改契约测试；数据库变化必须有前向迁移、兼容窗口和回滚说明。
- 不得删除、跳过、放宽断言或改写 golden 结果来获得绿色 CI，除非上游规格和 fixture 版本已批准变更。
- 软件公式测试只证明实现忠实执行契约；专家未签认时不得标记 `EXPERT_VERIFIED`。

## 7. 代码与文档约定

- 标识符、API 字段、数据库名使用英文；产品文档以中文为主，关键术语保留稳定英文编码。
- 用户可见文案必须走 `zh-CN` / `en-US` 资源键，不在组件中硬编码双语文本。
- SI 是唯一计算和存储单位；转换只发生在受测试的边界层。
- 不提交密钥、密码、真实个人数据、生产凭据或未脱敏客户数据。
- 优先使用项目已冻结的成熟库，禁止不同 Agent 并行引入等价框架。
- 注释解释原因、约束和来源，不重复代码表面行为。

## 8. 提交与 Pull Request

- 提交使用 Conventional Commits，例如 `feat(calc): add fresh-air load split`。
- 每次提交只包含一个可解释变化，并附对应测试。
- PR 必须链接 Issue、Spec/ADR，说明非目标、测试命令与结果、契约/迁移、风险、回滚和证据。
- PR 先做规格符合性审查，再做代码质量审查；两项都通过后才能进入 CI/验收合并队列。
- 合并使用 squash；PR 标题成为 main 的提交信息。

## 9. 停止条件

出现以下任一情况立即停止并报告：

- 上游事实冲突或验收不可判定。
- base SHA 已过期且相关契约发生变化。
- 基线测试失败或测试出现非预期错误。
- 需要修改禁止路径、共享文件或别的 Agent 租约路径。
- 发现密钥、敏感数据、破坏性迁移或不可逆操作。
- 同一问题连续三次修复失败；此时应重新审视设计而非继续试错。

## 10. 完成交接

Agent 只有在以下条件全部满足时才可报告完成：

- 验收命令已在当前 HEAD 新鲜运行并记录退出码。
- `git diff --check` 无错误。
- 变更没有未解释的生成文件或任务外文件。
- handoff 记录已填写并包含风险与未完成项。
- 未解决项明确标记为 blocker，不能用“基本完成”替代。
