# PCB-CDSO v0.6 分阶段开发 SOP

| 属性 | 值 |
|---|---|
| 状态 | approved |
| 版本 | 0.1.0 |
| 生效日期 | 2026-07-21 |
| 主仓库 | GitHub |
| 方法 | SDD 主导 + TDD 落地 |
| 适用对象 | 产品负责人、2 名全栈开发、Codex、Claude Code、Coder、测试/验收 Agent |

## 1. SOP 的目的

本 SOP 用于把 `docs/product/PRD_v0.6.md` 转化为可分阶段开发、测试和验收的软件，同时避免多个 Agent 各自理解需求、重复造轮子、覆盖文件或用未验证数据制造“看似完成”的结果。

执行本 SOP 后，每个功能都必须能回答：

1. 需求来自哪里？
2. 哪份规格冻结了行为和失败路径？
3. 哪个机器契约定义接口和数据？
4. 哪个测试在实现前失败、实现后通过？
5. 哪个 PR 合并了它？
6. 哪份验收记录证明阶段通过？
7. 结果属于软件验证还是专家验证？

## 2. 不可违反的原则

- GitHub 是唯一合并入口，`main` 是唯一可发布分支。
- PRD、ADR、Spec、契约、测试、代码按事实优先级管理，聊天记录不作为需求。
- 没有批准的 Feature Spec 和验收条件，不写产品代码。
- 新行为和缺陷修复必须先有失败测试，再做最小实现。
- 一个 Issue、一个主要结果、一个分支、一个活跃写入 Agent。
- 同一文件同一时间只有一个写入所有者。
- 接口变化先合并契约，再并行开发消费者。
- 任何阶段未过门禁都不得宣布完成，不得关闭校验或删除测试。
- 暖通计算的 `SOFTWARE_VERIFIED` 不等于 `EXPERT_VERIFIED`。
- 0.6 不实现前馈控制、冷站选型或运行优化策略，不显示假入口。

## 3. 单一事实源

从高到低：

```text
PRD
  -> ADR
    -> Milestone Spec
      -> Feature Spec
        -> OpenAPI / Schema / Migration / Seed
          -> Tests / Golden Fixtures
            -> Implementation Plan
              -> Issue / PR / Agent Handoff
```

低层内容与高层冲突时，低层内容无效。确需改变上层时：

1. 在 Issue 中引用冲突位置。
2. 停止相关实现和合并。
3. 提交 PRD 修订或 ADR/Spec 变更。
4. 产品负责人批准。
5. 更新追踪矩阵、契约、fixture 和测试。
6. 从新的 main 重新派发实现任务。

## 4. 必备文档

### 4.1 开工前必须存在

| 文档 | 负责人 | 用途 | 缺失后果 |
|---|---|---|---|
| PRD v0.6 | 产品负责人 | 版本范围和验收目标 | 全项目停止 |
| `AGENTS.md` | 技术负责人 | 统一所有 Agent 行为 | 禁止并行派发 |
| 系统上下文/数据流 | 技术负责人 | 系统边界和数据路径 | 不得冻结架构 |
| 技术 ADR | 技术负责人 | 框架、认证、任务、存储决策 | 对应模块不得编码 |
| M0-M6 Milestone Spec | 产品+技术 | 阶段范围和门禁 | 对应阶段不得开始 |
| Feature Spec | Spec Agent | 单功能行为与失败路径 | 对应功能不得编码 |
| OpenAPI / JSON Schema | API/数据负责人 | 机器可执行契约 | 前后端不得并行 |
| Test Plan | Test Agent | 风险与验收映射 | 不得进入实现 |
| Implementation Plan | Implementer/Planner | 文件级实施步骤 | 不得开始写代码 |
| Acceptance Record | Acceptance Agent | 阶段证据与签认 | 阶段不能关闭 |

### 4.2 文档状态

所有规格在元数据中使用：

```text
draft -> approved -> implementing -> verified -> superseded
```

- `draft`：可以讨论，不能作为编码依据。
- `approved`：产品/技术负责人同意，可进入计划。
- `implementing`：已有活跃 Issue/PR。
- `verified`：实现合并且验收记录通过。
- `superseded`：被新版本替代，保留追溯链接。

只有产品负责人可批准产品行为；技术负责人可批准不改变产品行为的 ADR；Acceptance Agent 只能基于证据标记 verified，不能修改规格。

## 5. 必备数据与验证级别

详细矩阵见 `docs/testing/DATA_AND_FIXTURE_REQUIREMENTS.md`。最少需要：

- 三个 PCB 产品模板及主/辅助工序种子。
- HDI 完整双语字段 registry、问题、帮助、选项和错误消息。
- 工艺环境规则、天气系数矩阵、生产率到生产系数分段表。
- 两角色账号和越权反例。
- 建筑/楼层/区域/工艺绑定项目 fixture。
- 三个静态计算软件基准及中间值。
- 一个 24 小时动态基准。
- 三年历史气象、168 小时预测、缺失/重复/越界/DST 反例。
- revision 冲突、幂等重试、旧任务晚到和容器重启 fixture。
- 五维聚合守恒、CSV golden、四主题截图基线。

验证状态只能是：

- `UNVERIFIED`：研究或经验种子，尚未完成软件基准。
- `SOFTWARE_VERIFIED`：schema、范围、公式和自动化测试通过。
- `EXPERT_VERIFIED`：专家对来源、参数、公式和样例签认。

升级验证状态必须生成新版本和 checksum，不原地修改已发布数据。

## 6. GitHub 初始化

### 6.1 创建主仓库

1. 在 GitHub 创建私有仓库 `PCB-CDSO`，不自动生成 README。
2. 将本地仓库绑定为 `origin`。
3. 推送 `main` 和治理标签。
4. 创建团队或 CODEOWNERS 对应组：Product、Platform、Web、API、Calculation、QA。
5. 在仓库 Settings 中启用 Issues、Actions、分支保护和 secret scanning。

远程地址由仓库管理员提供后执行：

```bash
git remote add origin <GitHub SSH or HTTPS repository URL>
git push -u origin main
git push origin --tags
```

### 6.2 `main` 分支保护

设置以下规则：

- Require a pull request before merging。
- 至少 1 个批准；影响公式、权限、迁移或契约时必须有对应 CODEOWNER。
- Dismiss stale approvals when new commits are pushed。
- Require review from Code Owners。
- Require status checks：`governance`、`unit`、`pull-request-evidence`，M0 后加入 `lint`、`typecheck`、`contract`、`integration`、`e2e-critical`、`build`。
- Require branches to be up to date before merging。
- Require conversation resolution。
- Block force pushes and deletions。
- 管理员也遵守规则，不设长期 bypass。

### 6.3 Git 命名

```text
feat/123-static-load-split
fix/241-revision-conflict
spec/098-weather-contract
chore/012-ci-baseline
```

Conventional Commit：

```text
feat(calc): add low and medium chilled-water split
fix(auth): reject cross-owner project access
test(sim): cover DST repeated hour
docs(spec): freeze weather CSV contract
chore(ci): add contract validation gate
```

## 7. 标准功能开发循环

### Step 1：创建 Issue

Issue 必须包含来源 milestone/spec、用户结果、范围、非目标、依赖、数据、允许路径、验收条件和风险。Orchestrator 检查它是否只包含一个主要结果。

### Step 2：Definition of Ready

全部满足才可派发：

- [ ] 上游 Milestone Spec 为 approved。
- [ ] Feature Spec 为 approved，正常/失败路径可判定。
- [ ] ADR 决策已关闭阻断问题。
- [ ] OpenAPI/Schema/Seed 契约已合并或本任务就是契约任务。
- [ ] 所需 fixture 可用且有 verification status/checksum。
- [ ] 测试计划覆盖高风险行为。
- [ ] 允许路径与文件租约无冲突。
- [ ] 验收命令可复制执行。
- [ ] base SHA 已记录。

### Step 3：创建分支与 worktree

推荐：

```bash
git fetch origin
git switch main
git pull --ff-only
git worktree add ../PCB-CDSO-worktrees/feat-123 -b feat/123-static-load-split main
```

验证：

```bash
git -C ../PCB-CDSO-worktrees/feat-123 status --short --branch
git -C ../PCB-CDSO-worktrees/feat-123 rev-parse HEAD
```

Windows 异常处理：若 linked worktree 文件哈希与 main/Git 对象不一致，或文本被透明保护封装：

1. 保存 `Get-FileHash`、`Format-Hex`、`git show` 证据。
2. 确认 main 工作树干净。
3. 移除刚创建的 worktree。
4. 在主目录切换到专用分支就地开发。
5. 同一时间只允许一个写入 Agent，直到环境问题解决。

不得让 Agent 在读取到异常字节后继续修改。

### Step 4：建立任务包和文件租约

Orchestrator 在 GitHub Issue 中登记：

```text
Agent: Codex / Claude Code / Coder
Role: Implementer
Branch: feat/123-static-load-split
Base SHA: <40-char SHA>
Active file lease:
- services/api/domain/cooling/**
- services/api/tests/domain/test_cooling_*.py
Expires: 2026-07-22T18:00:00+08:00
```

租约过期不自动允许覆盖。Orchestrator 先联系 Agent 或检查分支/PR，再释放或续期。

### Step 5：SDD 小规格检查

Implementer 用自己的话回答并写入 PR：

- 输入和输出是什么？
- 正常状态如何转换？
- 哪些错误必须阻断，哪些警告可确认放行？
- 哪些字段/接口/数据版本受影响？
- 幂等、并发、失效和回滚如何处理？
- 哪些是本任务非目标？

回答与 Spec 不一致时停止，不允许“边写边猜”。

### Step 6：TDD 红—绿—重构

每个行为执行：

1. 写一个只证明该行为的最小失败测试。
2. 运行精确测试，确认因行为缺失而失败，不是导入或拼写错误。
3. 写使测试通过的最小实现。
4. 再运行精确测试和受影响测试集。
5. 绿色后才重构，重构后再次运行。
6. 提交一个可解释变化。

缺陷修复必须先复现；不能先改代码再补测试。

### Step 7：本地质量门禁

治理阶段统一执行：

```bash
python scripts/quality/check_governance.py
python -m unittest discover -s tests -p "test_*.py" -v
git diff --check
git status --short
```

M0 冻结应用栈后把 formatter、lint、typecheck、contract、integration、E2E 和 build 加入 `make verify` 或等价统一脚本。Agent 不直接调用一套只在自己机器可用的私有命令作为唯一证据。

### Step 8：Pull Request

PR 必须：

- 链接 Issue、Spec 和 ADR。
- 说明行为变化与非目标。
- 粘贴新鲜测试命令和结果摘要。
- 对 UI 提供固定视口截图；对 CSV 提供 schema/checksum；对公式提供输入、中间值和容差。
- 说明迁移、兼容、风险与回滚。
- 填写 Agent handoff。

禁止提交密钥、真实凭据、生产数据、大型临时导出或 Agent 推理日志。

### Step 9：双阶段审查

1. Spec Review：验收条件、状态机、权限、失败路径、契约和范围是否一致。
2. Code Quality Review：实现、测试设计、可维护性、安全、性能和可观察性。

同一 Reviewer 可连续完成两阶段，但必须分别给出结论。Implementer 不能独自批准自己的 PR。

### Step 10：合并与回收

1. 所有必需检查通过。
2. 对话解决，CODEOWNER 批准。
3. squash merge 到 main。
4. 删除远程分支，移除 worktree。
5. 释放 Issue 文件租约。
6. 更新 milestone 追踪和 handoff。
7. 在干净 main 运行 smoke test。

## 8. 多 Agent 并行模型

统一角色为 Orchestrator、Spec Agent、Contract Agent、Implementer、Test Agent、Reviewer 和 Acceptance Agent。Contract Agent 只冻结机器契约及生成类型，不同时实现多个消费者；Reviewer 只读检出 PR merge ref/head SHA，Acceptance Agent 只读检出候选 SHA/标签或干净 main。只读角色不申请文件租约，除非另开 `spec/` 任务提交审查文档。

租约路径使用仓库相对 POSIX 格式、禁止 `..`，Windows 比较时不区分大小写；目录覆盖全部子路径，glob 与实际匹配路径冲突，重命名同时占用源/目标，生成文件必须显式列入。单一 Orchestrator 串行登记和释放租约，避免两个调度者同时占用同一路径。

### 8.1 可安全并行

- 已冻结 OpenAPI 后：Web 客户端、API 实现、契约测试。
- 已冻结字段 registry 后：问答 UI、状态机、seed 数据。
- 已冻结公式契约后：计算实现、fixture 构建、结果图表。
- 不相交文档、测试或组件路径。

### 8.2 必须串行

- PRD/ADR/Spec 决策与其实现。
- OpenAPI/Schema 与消费者生成类型。
- 数据库迁移与依赖新 schema 的实现。
- 公式定义与 golden expected results。
- 同一共享配置、同一文件或同一路径租约。

### 8.3 推荐派发顺序

```text
Spec Agent
  -> Contract Agent
      -> Implementer A (API/domain)
      -> Implementer B (Web)
      -> Test Agent (fixtures/E2E)
          -> Reviewer (spec)
              -> Reviewer (quality)
                  -> Acceptance Agent
```

Orchestrator 只派发依赖已满足的任务。Agent 完成不等于可合并；必须等审查、CI 和验收。

### 8.4 Codex、CC、Coder 的统一方式

- 唯一规则是 `AGENTS.md`；`CLAUDE.md` 只转发到它，不维护第二套规则。
- 所有工具收到同一种 YAML 任务包，不使用工具专属口头缩写。
- 所有工具运行相同仓库命令，输出相同 handoff 模板。
- Agent 私有 memory、session 或聊天只用于临时推理；重要结论必须进入 ADR/Spec/Issue/PR。
- Orchestrator 用 GitHub Issue/PR 状态而不是“Agent 说完成”判断进度。
- 代码审查者只看规格、diff、测试和证据，避免被实现者的推理过程锚定。

## 9. 测试体系

| 层级 | 主要对象 | 典型风险 | 是否阻断 PR |
|---|---|---|---|
| 单元 | 公式、校验器、状态转换 | 单位/边界/分支错误 | 是 |
| 属性/不变量 | 聚合、快照、TOTAL | 重复计数、负数、污染历史 | 是 |
| 契约 | OpenAPI、Schema、错误码 | 前后端漂移 | 是 |
| 集成 | MySQL、Redis/Celery、迁移 | 事务、幂等、旧任务覆盖 | 是 |
| E2E | 管理员/工程师主链 | 跨模块失效 | 关键路径阻断 |
| 视觉 | 中英 × 明暗 | 溢出、对比度、错位 | 主页面阻断 |
| 性能 | 30/300 区域 | 超时、内存、存储 | 按 milestone 门限 |
| 专家 | 暖通/PCB 黄金样例 | 领域正确性 | 后置验证，不伪造通过 |

### 9.1 关键不变量

- 一个区域只绑定一道工序。
- 主要工序必须全覆盖。
- `TOTAL_REFERENCE = CHW_LOW + CHW_MEDIUM + PCW`，不得再次与分项相加。
- 区域到工艺/楼层/建筑/工厂聚合守恒。
- 已发布快照不可变。
- revision 冲突不产生部分写入。
- 旧异步任务不能覆盖新 current batch。
- PCW 不乘天气系数，0.6 只乘生产系数。
- UTC 是逐时唯一计算轴。
- 归档项目不得创建新任务。

### 9.2 测试失败处理

1. 保存完整命令、错误、环境和 SHA。
2. 判断是既有基线、测试问题、实现问题还是环境问题。
3. 对缺陷先增加或缩小复现测试。
4. 一次只验证一个根因假设。
5. 连续三次失败后停止补丁式尝试，回到 Spec/ADR 检查架构。

## 10. M0-M6 阶段推进

### M0：仓库和契约基线

交付：干净环境命令、GitHub 保护、CI、应用骨架 ADR、OpenAPI/seed/schema 骨架、空库启动方案。

门禁：新开发机按 README 执行成功；PR 规则生效；治理、单元、构建命令可重复；无秘密和未解释 fixture。

### M1：身份、模板与项目

交付：首个管理员、工程师账号、两角色权限、三模板已发布待核验快照、项目所有权和归档/转交。

门禁：空库验收、越权 403、模板不可变、首次登录不强制改密、项目复制不复制结果。

### M2：八阶段受控采集

交付：字段 registry、配置文案、状态机、强校验、主要工序覆盖、保存恢复、影响分析和 revision。

门禁：自然语言不直接落库；阻断/警告行为、面积 3% 规则、并发 409、刷新恢复和结果失效通过。

### M3：静态计算

交付：六分项公式、低/中温与 PCW 分流、区域中间值、五维聚合、血缘详情。

门禁：三个软件基准在容差内；单位、焓值、分流和聚合守恒；结果标记待专家验证。

### M4：气象、仿真和预测

交付：Provider/CSV、进度任务、UTC 时间轴、三年仿真、168 小时预测、每小时刷新。

门禁：缺失/重复/DST、插值边界、PCW 系数、幂等、取消/重试、任务乱序和重启恢复通过。

### M5：结果中心

交付：五 Tab、统一筛选、区域下钻、关键图表、五维查询、中英文/明暗主题。

门禁：UI/API 查询一致、权限、筛选保持、三次交互区域定位和四主题截图全部通过。

### M6：导出与试开发收口

交付：五维长表 CSV、审计、三个示例项目、性能基线、Docker Compose、备份/回滚和最终验收记录。

门禁：CSV schema/checksum、失效/权限/清理、空库部署、PRD 六剧本和 P0 追踪全部通过；合并 main 后才创建试开发标签。

每阶段完整 DoR/DoD 和测试矩阵见对应 `docs/milestones/` 文件。

## 11. 每日节奏（1.5 周时间盒）

| 时间 | 固定动作 |
|---|---|
| 09:15 | Orchestrator 检查 main、CI、阻断、租约和依赖图 |
| 09:30 | 派发不相交任务包，确认 base SHA 和验收命令 |
| 12:00 | Agent 提交中间 handoff；接口变化优先合并 |
| 15:30 | 合并窗口一：小 PR、契约、测试和阻断修复 |
| 17:30 | 合并窗口二：运行阶段 smoke 和更新证据 |
| 18:00 | 记录 burn-up、风险、次日依赖，不用聊天记忆代替 |

每个工作日至少一次从干净 main 验证。功能未通过门禁时明确记录缺口；不得通过静默删减强校验、双语、权限或计算血缘来追赶工期。

## 12. Definition of Done

功能完成必须同时满足：

- [ ] Spec 验收条件全部有测试或明确人工证据。
- [ ] 红—绿证据可追溯，受影响测试全部通过。
- [ ] OpenAPI/Schema/迁移/seed 与实现一致。
- [ ] 错误、权限、并发、幂等和失效路径已覆盖。
- [ ] 用户可见文本完成中英文资源。
- [ ] 日志不含密钥和敏感数据，关键任务可追踪。
- [ ] 文档、Issue、PR、handoff 已更新。
- [ ] CI 和独立 Reviewer 通过。
- [ ] Acceptance Record 记录环境、SHA、fixture checksum 和结果。
- [ ] 未解决项被标记为 blocker 或后续 Issue，不使用模糊措辞。

## 13. 发布、回滚和验收

阶段候选从 main 创建带注释标签：

```text
m0-v0.1.0
m1-v0.1.0
...
trial-v0.6.0
```

发布前：

1. 在干净环境检出候选 SHA。
2. 执行治理、单元、契约、集成、关键 E2E、构建和阶段验收。
3. 记录数据库版本、seed/fixture checksum、镜像摘要和配置版本。
4. Acceptance Agent 签发记录。
5. 产品负责人做 go/no-go。

回滚必须同时定义应用版本、数据库迁移、配置/seed 快照和导出兼容性。无法安全回滚的变化在 ADR 和 PR 中明确，合并前提供前滚修复路径与备份验证。

验收状态统一使用 `draft / GO / NO-GO / CONDITIONAL-GO / EXPIRED`。安全、越权、数据完整性、不可恢复迁移、Milestone 停止条件、required test 失败或必需签字缺失一律 NO-GO；CONDITIONAL-GO 只允许不影响主链和数据正确性的非阻断偏差，并必须有 Owner、Issue、到期日、复验命令和失败处置，过期自动转 EXPIRED 并按 NO-GO 处理。

阶段验收统一运行 `make acceptance MILESTONE=M0`。标准输入路径为 `docs/testing/plans/M0-test-plan.md` 和 `docs/testing/acceptance/M0-acceptance.md`，M1-M6 依此命名。进入 acceptance-ready 必须具备 approved Test Plan，覆盖该阶段全部 Primary P0；Acceptance Record 必须是 `GO`，记录仓库中真实存在的 40 位 Candidate SHA、Product Sign-off，并为每条 Primary P0 提供通过证据，且每个证据路径在当前工作区真实存在。

## 14. 常见失败与处理

| 失败 | 处理 |
|---|---|
| 两 Agent 修改同一文件 | 停止后到者，保留前者租约；重新拆分或串行 |
| 前后端字段不一致 | 以已合并 OpenAPI/Schema 为准，先修契约消费者测试 |
| Agent 自行改验收值 | 拒绝 PR；fixture 变更必须独立 Issue、版本和批准 |
| PR 太大无法审查 | 拆为契约、领域、API、UI、E2E 等可运行小 PR |
| 测试偶发失败 | 标记 blocker，保存随机种子/时间/环境；不允许简单重跑后忽略 |
| worktree 内容异常 | 比较 Git 对象/main/worktree 哈希，按第 7 节降级，不继续编辑异常文件 |
| 工期不足 | 显式 go/no-go 或范围决策；核心门禁不得静默降级 |
| 专家数据未到 | 保持待验证标签，以软件 fixture 验实现，不宣称领域验证 |

## 15. 首次执行顺序

1. 完成本治理包机器检查和 GitHub 规则。
2. M0 技术栈 ADR：React/Vite、FastAPI、MySQL、Redis/Celery、ECharts、Docker Compose 的具体版本与库。
3. 冻结 OpenAPI 错误体、任务状态和 revision/幂等契约。
4. 冻结 HDI seed manifest、字段 registry 和气象 CSV fixture。
5. 创建 M1 Feature Specs 和测试计划。
6. 从最小纵向链开始：空库启动 → 登录 → 建项目 → 一个受控问题 → 保存 → 查询。
7. 每次扩展保持同一条链可运行，直到 M6。
