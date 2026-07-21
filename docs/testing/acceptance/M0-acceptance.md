# M0 仓库与运行基础验收记录

| 属性 | 值 |
|---|---|
| 状态 | CANDIDATE |
| Candidate SHA | 3591987a59040dcc12a42b73a2a20640151de1f8 |
| 验收日期 | 2026-07-21 |
| Implementer | Codex |
| Software Verifier | Automated M0 Gate |
| Product Sign-off | pending |
| GitHub Gate | blocked：`main` 未保护，候选分支尚无 PR/CI 状态 |

## 验收证据

| Requirement | 检查 | 预期 | 实际 | 证据 | 结果 |
|---|---|---|---|---|---|
| P0_01 | 治理与契约 | 全部通过且 OpenAPI 无漂移 | 30 项测试通过 | `artifacts/acceptance/M0/contract.txt` | pass |
| P0_01 | API 与类型检查 | 测试、lint、mypy 全通过 | 14 项测试通过 | `artifacts/acceptance/M0/api-test.txt` | pass |
| P0_01 | 空卷启动 | 七个服务按依赖启动 | 常驻服务健康，一次性任务退出 0 | `artifacts/acceptance/M0/m0-smoke.txt` | pass |
| P0_01 | MySQL/bootstrap/Worker | 迁移、幂等、真实消费通过 | ADMIN=1、审计=1、任务成功 | `artifacts/acceptance/M0/integration.txt` | pass |
| P0_01 | Web 登录壳 | 中英/明暗/禁用登录通过 | Vitest 与 Chromium E2E 通过 | `artifacts/acceptance/M0/web-test.txt` | pass |
| P0_14 | 统一质量门禁 | 确定性门禁退出 0 | 全量候选门禁退出 0 | `artifacts/acceptance/M0/verify.txt` | pass |
| P0_01 | GitHub 合并治理 | `main` 受保护且 PR 必需检查通过 | `main protected=false`、PR=0、候选状态上下文=0 | `artifacts/acceptance/M0/github-audit.txt` | fail |

## 软件验收结论

本地软件证据满足 M0 技术门禁。启用 `main` 分支保护、创建 PR 并取得 GitHub Actions 绿灯后，候选版本方可提交产品签认。上述条件和产品签认完成前，本记录保持 `CANDIDATE`，M0 不标记为 GO，也不进入 M1。
