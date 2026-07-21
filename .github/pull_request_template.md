## 关联事实

- Issue：
- Milestone Spec：
- Feature Spec / ADR：
- Base SHA：

## 结果与范围

说明用户/系统可观察变化。

### 非目标

列出本 PR 明确未处理的内容。

## 变更摘要

- 领域/行为：
- API/Schema：
- 数据库迁移：
- Seed/Fixture：
- UI/i18n：

## 测试证据

| 命令 | 退出码 | 结果摘要 | 证据路径 |
|---|---:|---|---|
|  |  |  |  |

对 UI 附固定视口截图；对 CSV 附 schema、行数和 checksum；对计算附输入、中间值、预期、实际和容差。

## 风险与回滚

- 风险：
- 监控/日志：
- 回滚步骤：
- 不可逆变化：

## Agent Handoff

- Implementer / Tool：
- Branch / Worktree：
- Head SHA：
- Handoff path：
- Remaining risks / blockers：

## 自检

- [ ] 变更符合已批准 Spec，未扩大范围。
- [ ] 新行为先有失败测试，缺陷有回归测试。
- [ ] 没有删除、跳过或放宽测试以获得绿色 CI。
- [ ] OpenAPI/Schema/迁移/共享类型保持一致。
- [ ] 权限、并发、幂等、失败和失效路径已覆盖。
- [ ] 用户文案已进入 zh-CN/en-US 资源。
- [ ] 未提交密钥、敏感数据、临时导出或 Agent 推理日志。
- [ ] `git diff --check` 和 required commands 已新鲜运行。

