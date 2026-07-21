# {{milestone_or_feature}} Acceptance Record

| 属性 | 填写值 |
|---|---|
| 状态 | draft / passed / failed / conditional |
| 日期 | {{ISO_8601_with_timezone}} |
| Candidate SHA | {{40_character_sha}} |
| Tag | {{candidate_tag}} |
| Acceptance Agent | {{name_and_tool}} |
| Product Sign-off | {{name_or_pending_reason}} |
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

## 最终决定

只允许 `GO`、`NO-GO` 或带到期日和责任人的 `CONDITIONAL GO`。软件验证和专家验证分别列出。

