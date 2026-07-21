# M0 Repository Runtime Baseline Test Plan

| 属性 | 值 |
|---|---|
| 状态 | approved |
| Spec | `docs/specs/m0/repository-runtime-baseline.md` v1.0.0 |
| Owner | Test Agent / Acceptance Agent |
| Fixture Version | `m0-empty-db/1.0.0`，SOFTWARE_VERIFIED |

## 风险排序

| 风险 | 影响 | 概率 | 测试策略 | PR 门禁 |
|---|---|---|---|---|
| 空库无法启动或迁移 | high | medium | 真实 MySQL 空卷、upgrade 两次、重启 | yes |
| 密码或连接串泄漏 | high | medium | 仓库与容器日志扫描 | yes |
| OpenAPI 与实现漂移 | high | medium | 生成契约逐字节比较 | yes |
| ready 假阳性 | high | medium | 分别停止 MySQL/Redis | yes |
| Web 双语/主题退化 | medium | medium | Vitest + Playwright 固定视口 | yes |
| Worker 无法消费任务 | medium | medium | 真实 Redis/Celery smoke | yes |

## 验收追踪

| Requirement ID | Spec 条件 | 预期/阈值 | Fixture 版本 | 层级 | 测试文件 | 精确命令 | 结果 | 证据 | NA 原因 |
|---|---|---|---|---|---|---|---|---|---|
| P0_01 | 治理与契约 | checker、OpenAPI、Schema 全部通过 | contracts@1.0.0 | contract | `tests/contract/` | `make contract` | not_run | `artifacts/acceptance/M0/contract.txt` | 不适用 |
| P0_01 | API health | live 200；ready 200/503 正确；request ID 一致 | m0-empty-db/1.0.0 | unit/integration | `services/api/tests/test_health.py` | `make api-test` | not_run | `artifacts/acceptance/M0/api-test.txt` | 不适用 |
| P0_01 | 空库迁移 | upgrade head 两次成功；重启后 schema 一致 | m0-empty-db/1.0.0 | integration | `scripts/quality/verify_m0.py` | `make m0-smoke` | not_run | `artifacts/acceptance/M0/m0-smoke.txt` | 不适用 |
| P0_01 | bootstrap 幂等 | 重复运行仅一个 ADMIN；密码为 Argon2 哈希 | m0-empty-db/1.0.0 | integration/security | `services/api/tests/integration/test_bootstrap.py` | `make integration` | not_run | `artifacts/acceptance/M0/integration.txt` | 不适用 |
| P0_01 | Worker 连通 | smoke task 30 秒内 SUCCEEDED | m0-empty-db/1.0.0 | integration | `services/api/tests/integration/test_tasks.py` | `make integration` | not_run | `artifacts/acceptance/M0/integration.txt` | 不适用 |
| P0_01 | Web 登录壳 | zh/en、light/dark、loading/error 通过 | web-shell/1.0.0 | unit/e2e | `apps/web/src/App.test.tsx`、`tests/e2e/login-shell.spec.ts` | `make web-test` | not_run | `artifacts/acceptance/M0/web-test.txt` | 不适用 |
| P0_14 | 统一门禁基线 | lint/typecheck/unit/contract/build 全通过 | repository@candidate | all | `.github/workflows/governance.yml` | `make verify` | not_run | `artifacts/acceptance/M0/verify.txt` | P0_14 Primary 在 M6；M0 只建立并验证基线 |

## Fixture

- `m0-empty-db/1.0.0`：全新 MySQL volume、Redis 空实例、固定 bootstrap email，SOFTWARE_VERIFIED；密码只由测试进程注入，不进入 Git。
- `contracts@1.0.0`：error/task/revision/idempotency JSON Schema 与生成 OpenAPI。
- `web-shell/1.0.0`：固定 1440×900、`zh-CN/en-US × light/dark` 状态组合。

正式 manifest 与 checksum 在 fixture 文件生成时提交；没有 manifest 的测试数据不得用于 M0 GO。

## 环境

验收记录必须保存：OS、CPU/内存、Docker/Compose、浏览器、Python/Node、依赖锁文件哈希、MySQL/Redis/API/Web 镜像 digest 和本地时区。计算与存储时区固定 UTC。

## 执行命令与预期

```text
make governance   -> exit 0
make api-test     -> exit 0
make web-test     -> exit 0
make contract     -> exit 0
make integration  -> exit 0
make build        -> exit 0
make m0-smoke     -> exit 0
make verify       -> exit 0
```

## 失败分类

- 产品缺陷：实现不满足 Spec，由 Implementer 修复并新增回归测试。
- 测试缺陷：断言与 approved Spec 不一致，由 Test Agent 修复，不能放宽需求。
- Fixture 缺陷：manifest、checksum 或预期错误，创建新 fixture 版本，不覆盖原版本。
- 环境缺陷：Docker、端口、网络或资源不足，记录环境证据后修复并从空卷重跑。
- 专家待确认：M0 无领域参数签认；不得用专家 pending 阻塞软件骨架测试，也不得宣称领域验证。

