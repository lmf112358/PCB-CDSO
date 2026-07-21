# PRD v0.6 Rebaseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将已确认的新版 PRD 固化为可治理、可追踪、可分阶段执行的项目基线，同时保持 M0 已交付能力不返工。

**Architecture:** PRD 继续作为最高产品事实，并恢复稳定 P0 ID；追踪矩阵负责唯一 Primary Milestone；M1、M2、M4 Feature Spec 分别冻结可靠任务创建、类 Codex 对话工作台和真实气象采集边界。当前重基线只更新规格与测试治理，不提前修改运行时代码或 OpenAPI。

**Tech Stack:** Markdown 治理文档、Python 3.12 governance checker、unittest、GitHub Actions、现有 OpenAPI/JSON Schema 契约优先流程。

---

## 文件结构

| 文件 | 职责 |
|---|---|
| `docs/product/PRD_v0.6.md` | 新版产品事实与稳定 P0 验收 ID |
| `docs/testing/P0_TRACEABILITY.md` | P0 到唯一 Primary Milestone、Feature Spec 和证据的映射 |
| `docs/milestones/M0-repository-baseline.md` | 记录 M0 不返工及后续兼容边界 |
| `docs/milestones/M1-identity-template-project.md` | 项目首轮确认、地理字段、Outbox 和初始气象任务 |
| `docs/milestones/M2-controlled-data-collection.md` | 连续消息流、Composer、结构化卡和全局任务坞 |
| `docs/milestones/M4-weather-simulation-forecast.md` | Provider、六阶段任务、城市失效、旧结果防覆盖 |
| `docs/milestones/M6-export-delivery-closure.md` | 新验收剧本进入最终回归 |
| `docs/specs/m1/project-weather-dispatch.md` | M1 原子项目/事件/任务契约规格 |
| `docs/specs/m2/expert-conversation-workspace.md` | M2 交互与恢复规格 |
| `docs/specs/m4/weather-ingestion.md` | M4 数据抓取、质量和 current 规则 |
| `docs/testing/plans/M1-test-plan.md` | M1 可执行门禁与证据路径 |
| `docs/testing/plans/M2-test-plan.md` | M2 可执行门禁与证据路径 |
| `docs/testing/plans/M4-test-plan.md` | M4 可执行门禁与证据路径 |

运行时代码、`contracts/openapi/openapi.json` 和 `contracts/schemas/task.schema.json` 不在本次重基线提交中修改；它们由对应里程碑按照契约先行和 TDD 更新。

### Task 1: 恢复 PRD 稳定追踪 ID

**Files:**
- Modify: `docs/product/PRD_v0.6.md`
- Test: `tests/governance/test_check_governance.py`

- [ ] **Step 1: 运行治理测试确认新版 PRD 的已知失败**

Run:

```powershell
python scripts/quality/check_governance.py
```

Expected: FAIL，明确列出 `missing P0_01` 至 `missing P0_14`；不得出现其他新增失败。

- [ ] **Step 2: 恢复 P0 编号并保留新版文字**

将新版 P0 列表改为以下稳定映射：

```markdown
- **P0_01** Docker Compose、MySQL、Redis、前后端骨架、数据库迁移。
- **P0_02** 两角色认证、项目归属、管理员账号维护。
- **P0_03** 三个内置产品模板及不可变快照。
- **P0_04** 类 Codex 连续对话、底部 Composer、结构化确认卡、工具执行卡、8 阶段状态机、即时保存、恢复与影响分析。
- **P0_05** 建筑、楼层、区域、唯一工序绑定与主要工序覆盖门禁。
- **P0_06** 工艺环境、设备/照明/人员/新风、PCW、计划和水蓄冷采集。
- **P0_07** 首轮产品/地理确认后自动启动过去三年气象抓取；右下角全局任务坞、Provider 接口、可恢复进度和 CSV 兜底。
- **P0_08** 真实静态公式、区域中间值、工艺与空间聚合。
- **P0_09** 三年经验仿真、七天预测、每小时刷新基础能力。
- **P0_10** 静态/历史/预测/质量/CSV 多 Tab 结果中心。
- **P0_11** 区域详情、关键图表、五类筛选与 URL 同步。
- **P0_12** 中英文、明暗主题。
- **P0_13** 三个可选可复制的已发布模板；HDI 配套完整验收项目，另外两个配套只读演示项目。
- **P0_14** 关键单元、契约、E2E、四主题组合与空库启动验收。
```

- [ ] **Step 3: 验证 PRD 治理恢复**

Run:

```powershell
python scripts/quality/check_governance.py
python -m unittest tests.governance.test_check_governance -v
git diff --check -- docs/product/PRD_v0.6.md
```

Expected: governance valid；治理单测全部 PASS；无空白错误。

- [ ] **Step 4: 提交 PRD 重基线**

```powershell
git add docs/product/PRD_v0.6.md
git commit -m "docs(prd): adopt expert workspace and weather prefetch"
```

### Task 2: 重排 P0 追踪与里程碑边界

**Files:**
- Modify: `docs/testing/P0_TRACEABILITY.md`
- Modify: `docs/milestones/M0-repository-baseline.md`
- Modify: `docs/milestones/M1-identity-template-project.md`
- Modify: `docs/milestones/M2-controlled-data-collection.md`
- Modify: `docs/milestones/M4-weather-simulation-forecast.md`
- Modify: `docs/milestones/M6-export-delivery-closure.md`

- [ ] **Step 1: 先写追踪断言并运行失败检查**

在 `tests/governance/test_check_governance.py` 增加：

```python
def test_rebaseline_terms_are_traceable(self) -> None:
    prd = (PROJECT_ROOT / "docs/product/PRD_v0.6.md").read_text(encoding="utf-8")
    traceability = (PROJECT_ROOT / "docs/testing/P0_TRACEABILITY.md").read_text(encoding="utf-8")
    self.assertIn("类 Codex 连续对话", prd)
    self.assertIn("首轮产品/地理确认后自动启动", prd)
    self.assertIn("project-weather-dispatch.md", traceability)
    self.assertIn("expert-conversation-workspace.md", traceability)
    self.assertIn("weather-ingestion.md", traceability)
```

Run:

```powershell
python -m unittest tests.governance.test_check_governance.GovernanceCheckerTest.test_rebaseline_terms_are_traceable -v
```

Expected: FAIL，因为三个新 Feature Spec 映射尚未写入。

- [ ] **Step 2: 更新追踪矩阵**

保持所有 P0 的 Primary Milestone 唯一，并至少采用以下映射：

```markdown
| P0_04 | 类 Codex 连续对话、8 阶段和影响分析 | M2 | `docs/specs/m2/expert-conversation-workspace.md` | 消息流/Composer/确认卡/工具卡/恢复/409/422 |
| P0_07 | 首轮自动气象任务、Provider、任务坞和 CSV | M4 | `docs/specs/m1/project-weather-dispatch.md`；`docs/specs/m4/weather-ingestion.md` | 原子触发、2 秒可见、六阶段、失败恢复、UTC |
```

P0_07 的 Primary Milestone 仍为 M4；M1 是必需前置契约，不重复认领 P0。

- [ ] **Step 3: 更新里程碑职责**

在各里程碑写入明确交付：

```text
M0: 基础设施兼容后续持久化任务；不实现业务气象任务。
M1: POST /projects 的地理字段、幂等键、项目/Outbox/Task 原子提交。
M2: 时间线、Composer、四类消息、工具卡、GET /tasks 驱动的任务坞恢复。
M4: Provider、LOCATE/REQUEST/DOWNLOAD/CLEAN/VALIDATE/STORE、城市 revision 失效。
M6: 执行首轮自动气象抓取与全局进度验收剧本。
```

- [ ] **Step 4: 验证并提交追踪调整**

Run:

```powershell
python -m unittest tests.governance.test_check_governance -v
python scripts/quality/check_governance.py
git diff --check -- docs/testing docs/milestones
```

Expected: 全部 PASS，所有 P0 仍存在且 Primary Milestone 唯一。

```powershell
git add tests/governance/test_check_governance.py docs/testing/P0_TRACEABILITY.md docs/milestones
git commit -m "docs(governance): realign milestones to revised PRD"
```

### Task 3: 冻结 M1 可靠气象任务创建规格

**Files:**
- Create: `docs/specs/m1/project-weather-dispatch.md`
- Create: `docs/testing/plans/M1-test-plan.md`

- [ ] **Step 1: 编写 Feature Spec**

规格必须包含以下不可变语义：

```text
Command: CreateProject
Input: name, templateVersionId, countryCode, adminArea, city, timezone,
       idempotencyKey, actorId
Transaction: Project + immutable snapshots + Task(DISPATCH_PENDING)
             + OutboxEvent(WeatherFetchRequested)
Deduplication: actorId + idempotencyKey
Worker key: projectId + inputRevision + WEATHER_HISTORY_FETCH
Response: project, inputRevision=1, weatherTaskId
Failure: any transaction write failure rolls back all four records
```

状态至少定义 `DISPATCH_PENDING -> QUEUED -> RUNNING`，并说明 M1 使用 fake worker 验证派发，不下载真实气象。

- [ ] **Step 2: 编写 M1 测试计划**

测试计划必须列出：

```markdown
| Requirement | Case | Expected |
|---|---|---|
| P0_07 dependency | project + outbox + task atomicity | one commit or zero rows |
| P0_07 dependency | duplicate idempotency key | same project id and task id |
| P0_07 dependency | dispatcher unavailable | task remains DISPATCH_PENDING and is retryable |
| P0_02 | cross-owner project/task access | 403 without existence leak |
```

- [ ] **Step 3: 验证规格无占位符并提交**

Run:

```powershell
rg -n "TBD|TODO|待定|待补" docs/specs/m1 docs/testing/plans/M1-test-plan.md
python scripts/quality/check_governance.py
git diff --check -- docs/specs/m1 docs/testing/plans/M1-test-plan.md
```

Expected: `rg` 无匹配；治理和 diff 检查通过。

```powershell
git add docs/specs/m1/project-weather-dispatch.md docs/testing/plans/M1-test-plan.md
git commit -m "docs(m1): specify atomic weather task dispatch"
```

### Task 4: 冻结 M2 专家对话工作台规格

**Files:**
- Create: `docs/specs/m2/expert-conversation-workspace.md`
- Create: `docs/testing/plans/M2-test-plan.md`

- [ ] **Step 1: 编写交互状态规格**

定义四类消息和唯一写入路径：

```text
AGENT_PROMPT -> USER_DRAFT -> CONFIRMATION_CARD -> VALIDATING
VALIDATING -> COMMITTED | BLOCKED | WARNING_CONFIRMATION | REVISION_CONFLICT
TOOL_CARD mirrors persisted Task by taskId; it never owns task state.
Natural language may create a draft but cannot persist calculation fields.
```

同时冻结：Composer 草稿恢复、8 阶段导航、右侧工艺链、360px 任务坞、最多三个活动摘要、`Ctrl/Cmd+J`、双语/主题和不遮挡发送按钮。

- [ ] **Step 2: 编写 M2 测试计划**

至少包含以下 E2E：

```text
create Shenzhen HDI project -> tool card and dock show same task id
continue building questions while weather task RUNNING
refresh -> timeline, first incomplete question, composer draft and dock recover
switch browser tab -> no duplicate task and no progress reset
natural-language answer -> confirmation card only, no direct database write
```

- [ ] **Step 3: 验证并提交**

Run:

```powershell
rg -n "TBD|TODO|待定|待补" docs/specs/m2 docs/testing/plans/M2-test-plan.md
python scripts/quality/check_governance.py
git diff --check -- docs/specs/m2 docs/testing/plans/M2-test-plan.md
```

Expected: 无占位符，治理通过。

```powershell
git add docs/specs/m2/expert-conversation-workspace.md docs/testing/plans/M2-test-plan.md
git commit -m "docs(m2): specify expert conversation workspace"
```

### Task 5: 冻结 M4 气象抓取和 current 安全规格

**Files:**
- Create: `docs/specs/m4/weather-ingestion.md`
- Create: `docs/testing/plans/M4-test-plan.md`

- [ ] **Step 1: 编写气象摄取规格**

冻结六阶段和 current 守卫：

```text
LOCATE -> REQUEST -> DOWNLOAD -> CLEAN -> VALIDATE -> STORE -> SUCCEEDED
Provider error -> FAILED(retryable=true/false, structured error)
City change -> inputRevision increment + old task STALE/CANCELLED + new task
Publish current iff task.projectId, inputRevision, taskType and weather batch
still match the current project dependency fingerprint.
```

明确过去三年的实际小时数按 UTC 窗口计算，连续性检查禁止静默补点，CSV 恢复使用同一标准 schema。

- [ ] **Step 2: 编写 M4 测试计划**

至少包含：六阶段进度单调、任务坞恢复、Provider 连续失败、CSV 兜底、城市深圳改东莞、旧深圳任务晚完成、容器重启、三年行数、DST/UTC 唯一键和历史仿真消费 current 批次。

- [ ] **Step 3: 验证并提交**

Run:

```powershell
rg -n "TBD|TODO|待定|待补" docs/specs/m4 docs/testing/plans/M4-test-plan.md
python scripts/quality/check_governance.py
git diff --check -- docs/specs/m4 docs/testing/plans/M4-test-plan.md
```

Expected: 无占位符，治理通过。

```powershell
git add docs/specs/m4/weather-ingestion.md docs/testing/plans/M4-test-plan.md
git commit -m "docs(m4): specify weather ingestion lifecycle"
```

### Task 6: 完成重基线质量门禁和 PR

**Files:**
- Modify if needed: `docs/superpowers/specs/2026-07-21-prd-rebaseline-impact-design.md`
- Modify if needed: `docs/superpowers/plans/2026-07-21-prd-rebaseline.md`
- Verify only: `.github/workflows/governance.yml`

- [ ] **Step 1: 运行完整文档治理门禁**

Run:

```powershell
python scripts/quality/check_governance.py
python -m unittest discover -s tests -p "test_*.py" -v
python scripts/quality/check_secrets.py
git diff --check
git status --short
```

Expected: 32 项以上测试全部通过；governance 和 secret scan 退出 0；工作树只包含本计划文件。

- [ ] **Step 2: 核对不应提前修改的运行时文件**

Run:

```powershell
git diff origin/main...HEAD --name-only
```

Expected: 不包含 `services/`、`apps/`、`contracts/openapi/openapi.json` 或 `contracts/schemas/task.schema.json`。

- [ ] **Step 3: 推送并创建 PR**

```powershell
git push -u origin docs/004-prd-rebaseline
```

PR 验收摘要必须写明：

```text
M0 runtime unchanged.
P0_01..P0_14 restored.
M1/M2/M4 ownership is explicit.
Runtime contracts remain milestone-gated.
Governance, unit, Build and PR evidence checks are required.
```

- [ ] **Step 4: 合并后验证 main**

Run:

```powershell
git fetch origin
git log --oneline -3 origin/main
python scripts/quality/check_governance.py
```

Expected: 重基线 PR 位于 `origin/main`，GitHub Governance 与 Build 成功，分支规则集保持 Active。

---

## 计划自检

- 新版 PRD 的三项核心变化均有明确任务和里程碑归属。
- P0 ID 恢复先于任何下游文档更新，治理不会在中间提交静默失效。
- M1、M2、M4 各自生成可独立评审的 Feature Spec 和测试计划。
- 本计划没有提前实现产品代码、数据库迁移或运行时契约。
- 每个任务均包含失败检查、最小文档变更、验证命令和独立提交。
