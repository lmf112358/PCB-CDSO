# M0 仓库与运行基础测试计划

| 属性 | 值 |
|---|---|
| 状态 | approved |
| Spec | `docs/specs/m0/repository-runtime-baseline.md` v1.0.0 |
| Owner | Test Agent / Acceptance Agent |
| Fixture | `fixtures/acceptance/M0/1.0.0`，SOFTWARE_VERIFIED |

## 风险与策略

| 风险 | 影响 | 测试策略 | PR 门禁 |
|---|---|---|---|
| 空数据库无法启动或迁移 | high | 真实 MySQL 空卷、重复迁移、重启 | yes |
| 密码或连接串泄漏 | high | 仓库密钥扫描、日志检查 | yes |
| OpenAPI 与实现漂移 | high | 重新生成后逐字节比较 | yes |
| ready 假阳性 | high | 停止 Redis，验证 live=200、ready=503 | yes |
| Web 双语或主题退化 | medium | Vitest 与固定桌面视口 Playwright | yes |
| Worker 无法消费 | medium | 真实 Redis/Celery smoke | yes |

## 执行结果

| Requirement ID | 检查 | 命令 | 结果 | 证据 |
|---|---|---|---|---|
| P0_01 | 治理、Schema、OpenAPI | `make contract` | pass | `artifacts/acceptance/M0/contract.txt` |
| P0_01 | API health、错误契约、Request ID | `make api-test` | pass | `artifacts/acceptance/M0/api-test.txt` |
| P0_01 | 空卷迁移、重启、依赖负向验证 | `make m0-smoke` | pass | `artifacts/acceptance/M0/m0-smoke.txt` |
| P0_01 | bootstrap 幂等和 Worker 消费 | `make integration` | pass | `artifacts/acceptance/M0/integration.txt` |
| P0_01 | Web 中英、明暗主题和浏览器 E2E | `make web-test`、`npm run e2e` | pass | `artifacts/acceptance/M0/web-test.txt` |
| P0_14 | lint、typecheck、测试、构建、运行探针 | `make verify` | pass | `artifacts/acceptance/M0/verify.txt` |

## 判定

所有软件测试均通过。M0 在产品方签认验收记录后方可从候选状态转为 GO。
