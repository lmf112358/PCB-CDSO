# PCB-CDSO v0.6

PCB 工厂冷源需求计算与仿真预测专家系统。v0.6 聚焦受控数据采集、静态冷量计算、历史动态仿真、七天预测、区域级图表与逐时 CSV 导出；不交付前馈控制、冷站配置或运行优化策略。

## 开始前必读

按以下顺序阅读，后者不得覆盖前者：

1. `docs/product/PRD_v0.6.md`
2. `AGENTS.md`
3. 当前 `docs/milestones/` 规格
4. 目标 `docs/specs/` 功能规格和相关 ADR
5. `contracts/`、`fixtures/` 与测试
6. 目标实施计划

完整协作流程见 `docs/sop/DEVELOPMENT_SOP.md`。

## M0 环境

- Python 3.12
- Node.js 22.17、npm 11
- Docker 26+、Docker Compose 2.27+
- MySQL 8.4、Redis 7.4（由 Compose 启动）

复制 `.env.example` 为 `.env` 后，仅在本地开发环境使用其中占位值。共享或生产环境必须全部替换。

```bash
cp .env.example .env
docker compose up --build --wait
python scripts/quality/verify_m0.py
```

Web 地址为 `http://localhost:3000`，API 文档为 `http://localhost:8000/docs`。

## 统一质量命令

| 命令 | 作用 |
|---|---|
| `make governance` | 校验规格、里程碑、可追溯性与验收治理文件 |
| `make secrets` | 检查配置文件中误提交的具体密钥值 |
| `make api-test` | 运行 API 单元与集成测试 |
| `make web-test` | 运行 Web 组件与交互测试 |
| `make contract` | 运行 OpenAPI、JSON Schema 和治理契约测试 |
| `make build` | 运行 Python lint/类型检查及 Web 类型检查/构建 |
| `make verify` | 本地提交前的确定性质量门禁，不清理数据卷 |
| `make m0-smoke` | 清空本项目开发卷并执行 M0 空环境验收与浏览器测试 |
| `make acceptance MILESTONE=M0` | 校验指定里程碑的 GO 记录、候选 SHA 和证据 |

Windows 没有 `make` 时，可从 `Makefile` 按顺序执行对应命令；GitHub Actions 使用同一组入口。

## Git 与多 Agent 规则

- `main` 只通过 Pull Request 合并，使用 squash merge。
- 分支格式：`feat/<issue>-<slug>`、`fix/<issue>-<slug>`、`spec/<issue>-<slug>`、`chore/<issue>-<slug>`。
- 提交遵循 Conventional Commits。
- 同一工作目录同一时刻只允许一个写入 Agent；其他 Agent 只审查或在独立分支/worktree 工作。
- 所有 Agent 遵循 `AGENTS.md`，交接使用 `docs/handoffs/AGENT_HANDOFF_TEMPLATE.md`。

产品参数即使通过软件测试，在专家签认前仍保持 `UNVERIFIED` 或 `SOFTWARE_VERIFIED`，不得宣称为国家标准验证结果。
