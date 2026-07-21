# Development Governance Pack Acceptance Record

| 属性 | 值 |
|---|---|
| 状态 | GO |
| 日期 | 2026-07-21T18:00:00+08:00 |
| Candidate SHA | `0706d6c67589dc9f853b3d8d129098dc4a235641` |
| Acceptance Agent | Codex / Orchestrator |
| Product Sign-off | 用户已批准治理方案、GitHub 主仓和统一多 Agent 工作方式；2026-07-21 |
| Expert Sign-off | not_required；本记录不签认暖通/PCB 领域数据 |

## 验收范围

本记录验收开发治理包：开发 SOP、Agent 协议、Git/GitHub 规则、M0-M6 阶段规格、模板、数据契约、治理检查、CI 和交接机制。它不验收 PCB-CDSO 产品实现，也不表示 M0-M6 已完成。

## 执行证据

| 场景/命令 | 预期 | 实际 | 退出码 | 证据路径 | 结论 |
|---|---|---|---:|---|---|
| `python scripts/quality/check_governance.py` | 治理基线有效 | `Governance baseline valid.` | 0 | `scripts/quality/check_governance.py` | pass |
| `python -m unittest discover -s tests -p "test_*.py" -v` | 全部治理测试通过 | 23 tests, OK | 0 | `tests/governance/` | pass |
| `python .../qiaomu-ai-prd/scripts/lint_prd.py docs/product/PRD_v0.6.md` | PRD lint 通过 | `PRD lint passed.` | 0 | `docs/product/PRD_v0.6.md` | pass |
| `python scripts/quality/check_governance.py --acceptance-ready M6` | 未开发产品不得被误报完成 | 因缺 M6 Test Plan 和 Acceptance Record 被拒绝 | 1（预期） | `docs/milestones/M6-export-delivery-closure.md` | pass |
| `git diff --check` | 无空白错误 | 无输出 | 0 | Git candidate diff | pass |

## 独立读者复核

- 首次上手读者能够从零解释 M0 DoR、统一命令、事实冲突处理与 worktree 降级流程；其无法回答项均为 M0 必须冻结的真实输入，而非 SOP 歧义。
- 多 Agent 读者提出 Contract 角色、任务包字段、租约语义、只读审查 ref、双审查证据等缺口；均已纳入规则、Issue/PR 模板和 CI。
- 质量读者提出 P0 唯一追踪、M5/M6 冲突、验收状态、空壳 acceptance-ready、manifest schema/checksum 和验证证据问题；复核确认问题 3-5 已 Closed，并判定开发治理包 GO。

## 偏差与风险

| 项目 | 决策 | 后续动作 |
|---|---|---|
| 本机 E: 盘 linked worktree 内容被透明层写成不可读包装文件 | 非阻断环境偏差；已按 SOP 退化为专用分支就地开发，期间仅一个写入 Agent | 在另一台开发机或 GitHub runner 验证正常 worktree 后再恢复并行写入 |
| GitHub `origin` 尚未配置 | 阻断推送/PR，不阻断本地治理包 GO | 获得 GitHub 仓库 URL 后配置 remote、推送分支并启用保护规则 |
| 应用技术栈精确版本尚未冻结 | 符合范围；属于 M0 DoR/ADR 工作 | M0 首先批准技术 ADR，再生成应用骨架 |
| PCB/暖通参数未由专家验证 | 符合 v0.6 试开发边界 | 保持 `UNVERIFIED`/`SOFTWARE_VERIFIED`，功能交付后另行专家验证 |

## 最终决定

开发治理包为 **GO**。产品实现仍处于 M0 准备阶段；任何 M0-M6 阶段只有在对应 Test Plan、真实 Candidate SHA、Primary P0 证据、Product Sign-off 和 Acceptance Record 全部通过后才能单独签发 GO。
