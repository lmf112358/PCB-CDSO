# M0 仓库与契约基线

| 属性 | 值 |
|---|---|
| 状态 | approved |
| Owner | Platform / Orchestrator |
| 时间盒 | 0.5 天目标；门禁不过不进入 M1 |
| PRD 追踪 | 第六、十、十一章 |

## 目标

从全新环境可重复建立仓库、运行治理/测试/构建命令，并冻结后续并行开发需要的技术栈和机器契约边界。

## 范围

包含：GitHub 保护、CI、统一命令、目录骨架、环境变量规范、Docker Compose 骨架、数据库迁移骨架、OpenAPI/错误体/任务状态/schema/seed 骨架、日志关联 ID、首个管理员注入方案。

不包含：业务页面、真实静态公式、完整模板编辑器、气象 Provider。

## Definition of Ready

- [ ] PRD、治理设计、SOP、AGENTS 已合并。
- [ ] GitHub 仓库 Owner 和 CODEOWNERS 团队已确定。
- [ ] 开发机可运行 Git、Python、Node 和 Docker；具体版本由本阶段 ADR 冻结。
- [ ] 技术 ADR 评审人已分配。

## 交付物

- ADR：前端栈、API/认证、异步任务、MySQL 逐时存储、测试工具。
- `apps/web`、`services/api`、共享 contracts、infra 目录骨架。
- 一条命令启动依赖和空应用；一条命令执行 verify。
- OpenAPI 最小错误体、任务状态、revision/幂等操作基线。
- `.env.example`，首个管理员通过一次性环境变量创建，明文不入日志/数据库。
- GitHub Actions 和 main 分支保护清单。

## 测试与质量门禁

| 检查 | 通过条件 |
|---|---|
| 空库启动 | 删除本地 volume 后按 README 启动成功 |
| 迁移 | upgrade 到 head、空库重跑幂等、rollback 策略有证据 |
| 治理 | checker 和测试通过，无未完成标记/非法 JSON |
| API | health 和 OpenAPI 可访问；错误体契约测试通过 |
| Web | 登录壳可加载，无控制台阻断错误 |
| Secrets | 仓库和日志无凭据，GitHub secret scan 开启 |
| CI | PR 上治理、单元和构建检查必需且不可跳过 |

## 演示脚本

在干净机器克隆仓库，复制 `.env.example`，注入一次性管理员变量，启动服务；显示 migration、health、Web 登录壳和 CI 绿色结果；停止并再次启动，状态一致。

## Definition of Done

- [ ] 所有 ADR 为 approved。
- [ ] README 命令在 Windows 和 CI/Linux 有等价路径。
- [ ] OpenAPI/Schema 可被机器解析并生成共享类型。
- [ ] 空库和重启证据进入 Acceptance Record。
- [ ] M1 依赖版本已锁定。

## 停止条件

若认证、任务队列或 MySQL 存储 ADR 未批准，或干净环境不能启动，M1 不得开始。worktree 字节异常按 SOP 降级并记录环境风险。

