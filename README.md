# PCB-CDSO v0.6

PCB 工厂冷源需求计算与经验仿真试开发系统。0.6 交付受控数据采集、静态冷量计算、三年历史仿真、七天预测、图表下钻和逐时 CSV；不交付前馈控制、冷站配置或运行优化策略。

## 开始前必读

按以下顺序读取，后者不得覆盖前者：

1. `docs/product/PRD_v0.6.md`
2. `AGENTS.md`
3. 当前 `docs/milestones/` 规格
4. 目标 `docs/specs/` 功能规格及相关 ADR
5. `contracts/`、`fixtures/` 与测试
6. 目标实施计划

完整流程见 `docs/sop/DEVELOPMENT_SOP.md`。

## 环境要求

- Git 2.40+
- Python 3.12+，治理检查仅使用标准库
- GitHub 主仓库及受保护的 `main`
- 应用运行时、Node/Python 包管理器和 Docker 版本在 M0 技术 ADR 中冻结后写入本节；冻结前不得由不同 Agent 各自选择

## 统一命令

Python 命令是跨平台事实，Makefile 是便捷入口：

```bash
python scripts/quality/check_governance.py
python -m unittest discover -s tests -p "test_*.py" -v
make verify
make acceptance MILESTONE=M0
```

| 命令 | 作用 |
|---|---|
| `make governance` | 校验治理文件、状态、JSON 和未完成标记 |
| `make test` | 运行治理单元测试；M0 后扩展为项目测试入口 |
| `make verify` | 本地提交前的默认质量门禁 |
| `make acceptance MILESTONE=M0` | 检查指定 M0-M6 阶段的 Test Plan、验收记录和证据是否齐备 |

## Git 工作方式

- `main` 只通过 Pull Request 合并。
- 每个 Issue 使用独立短分支和 worktree；若本机透明加密使 linked worktree 内容不可读，记录证据后退化为独立分支就地开发。
- 分支格式：`feat/<issue>-<slug>`、`fix/<issue>-<slug>`、`spec/<issue>-<slug>`、`chore/<issue>-<slug>`。
- 提交使用 Conventional Commits；PR 使用 squash merge。
- 所有 Agent 任务与交接必须采用 `AGENTS.md` 和 `docs/handoffs/AGENT_HANDOFF_TEMPLATE.md`。

## 当前状态

仓库处于开发治理与 M0 准备阶段。产品参数即使通过软件测试，也必须在专家签认前保持 `UNVERIFIED` 或 `SOFTWARE_VERIFIED`，不得宣称为国家标准验证结果。
