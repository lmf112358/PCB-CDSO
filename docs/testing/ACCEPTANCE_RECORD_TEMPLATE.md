# {{milestone_or_feature}} Acceptance Record

| 属性 | 填写值 |
|---|---|
| 状态 | draft / GO / NO-GO / CONDITIONAL-GO / EXPIRED |
| 日期 | {{ISO_8601_with_timezone}} |
| Candidate SHA | {{40_character_sha}} |
| Tag | {{candidate_tag}} |
| Acceptance Agent | {{name_and_tool}} |
| Product Sign-off | {{signed_name_and_time_or_not_required}} |
| Expert Sign-off | not_required / pending / signed_record_path |

## 验收范围

列出 Milestone Spec、Feature Specs、ADRs、contracts 和非目标。

## 环境与数据

记录硬件、OS、浏览器、容器镜像、数据库迁移、seed/fixture 版本和 checksum。

## 执行证据

| 场景/命令 | 预期 | 实际 | 退出码 | 证据路径 | 结论 |
|---|---|---|---:|---|---|
| {{scenario}} | {{expected}} | {{actual}} | {{code}} | {{path}} | pass/fail |

## 偏差与风险

每项偏差写明严重度、影响、负责人、修复 Issue 和 go/no-go 决策；没有则写“无”。

## 决策规则

| 条件 | 强制状态 |
|---|---|
| 任一安全、越权、数据完整性、不可恢复迁移或 Milestone 停止条件触发 | NO-GO |
| 任一 required test/质量门禁失败，或必需签字缺失 | NO-GO |
| 全部 required gate 通过且无未关闭阻断项 | GO |
| 仅存在不影响主链、数据正确性、安全或回滚的非阻断偏差 | CONDITIONAL-GO |
| CONDITIONAL-GO 超过到期日未复验通过 | EXPIRED，并按 NO-GO 处理 |

`CONDITIONAL-GO` 必须为每项偏差记录 Owner、到期日、修复 Issue、复验命令和失败后的回滚/禁用动作。Product Sign-off 对 GO/CONDITIONAL-GO 必需；Expert Sign-off 只在对应 Milestone 明确要求领域升级时必需。

## 最终决定

本节结论必须与顶部状态完全一致，只能写一个状态。分别列出软件验证和专家验证，不得用 pending expert sign-off 阻塞一个明确不要求专家验收的试开发软件门禁，也不得把 pending 伪装成已验证。
