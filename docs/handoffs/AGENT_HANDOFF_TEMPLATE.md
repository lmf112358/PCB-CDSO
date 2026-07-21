# Agent Handoff Record

| 字段 | 填写内容 |
|---|---|
| 状态 | draft / ready_for_review / blocked / accepted |
| 日期与时区 | ISO-8601，Asia/Shanghai |
| Agent / 工具 | 名称与版本 |
| 角色 | Spec / Contract / Implementer / Test / Reviewer / Acceptance |
| Issue | GitHub Issue 链接或编号 |
| Source Spec | 仓库相对路径与版本 |
| Branch / Worktree | 分支与绝对路径 |
| Base SHA | 开始任务时的 40 位 SHA |
| Head SHA | 交接时的 40 位 SHA |

## 目标与边界

- Objective：填写单一可观察结果。
- Allowed paths：逐行列出。
- Forbidden paths：逐行列出。
- Non-goals：列出本次明确不处理的事项。

## 已完成变更

逐文件说明行为变化及其上游依据，不粘贴大段 diff。

## 测试证据

| 命令 | 退出码 | 结果摘要 | 证据路径 |
|---|---:|---|---|
| 填写完整命令 | 填写整数 | 通过数/失败数/关键指标 | 日志、截图或报告 |

## 契约、迁移与数据

- OpenAPI / Schema 变化：列出版本与兼容性。
- 数据库迁移：列出 upgrade、rollback 和验证结果。
- Fixture / Seed：列出版本、verification status 和 checksum。

## 决策与偏差

- 新决策：必须链接 ADR 或写明“不涉及”。
- 与计划偏差：说明原因和批准者；没有则写“无”。

## 风险、阻断与下一步

- Remaining risks：仍需 Reviewer 特别检查的内容。
- Blockers：阻断条件、已尝试证据、需要谁决定；没有则写“无”。
- Recommended next action：一个明确动作及建议负责人角色。

## 自检

- [ ] 当前 HEAD 已运行全部 required commands。
- [ ] `git diff --check` 通过。
- [ ] 没有任务外文件、密钥、跳过测试或未解释生成物。
- [ ] 交接信息足以让新 Agent 在不读聊天记录时继续。
