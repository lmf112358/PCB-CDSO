# ADR-0001：M0 应用技术栈与部署基线

| 属性 | 值 |
|---|---|
| 状态 | approved |
| 日期 | 2026-07-21 |
| 决策人 | Product Owner / Orchestrator |
| 适用范围 | M0-M6 |

## 背景

PCB-CDSO v0.6 由两个全栈开发者在 1.5 周内交付桌面 Web 试开发版本。系统需要强状态机、MySQL、逐时数据、异步气象/仿真任务、图表、双语和明暗主题。技术选择必须成熟、易被多个编码 Agent 一致执行，并避免为试开发引入微服务复杂度。

## 决策

采用模块化单体 FastAPI、独立 Celery Worker、React SPA 和 Docker Compose：

| 类别 | 锁定选择 | M0 起始版本 |
|---|---|---|
| Python | CPython | 3.12 系列；容器验收记录精确 digest |
| API | FastAPI | 0.139.2 |
| ORM | SQLAlchemy | 2.0.51 |
| Migration | Alembic | 1.18.5 |
| Worker | Celery + Redis transport | 5.6.3 |
| Python test | pytest | 9.1.1 |
| Node | Node.js LTS | 22 系列；容器验收记录精确 digest |
| Web | React | 19.2.7 |
| Build | Vite | 8.1.5 |
| Language | TypeScript | 7.0.2 |
| Components | Ant Design | 6.5.1 |
| Charts | Apache ECharts | 6.1.0 |
| Web test | Vitest / Playwright | 4.1.10 / 1.61.1 |
| Database | MySQL | 8.4 LTS；验收记录精确 image digest |
| Broker/cache | Redis | 7.4 系列；验收记录精确 image digest |
| Deployment | Docker Compose | 2.27+ |

应用依赖使用精确锁文件；Dockerfile 基础镜像使用批准的稳定版本线，并在 M0 Acceptance Record 冻结实际解析到的 sha256 digest。后续升级必须通过独立 ADR 或依赖升级 PR，不允许 Agent 自行改版本。

API 数据访问使用 SQLAlchemy 2.0 同步 Session，每请求/每任务一个 Session。Celery 使用 Redis 作为 broker 和试开发 result backend；业务结果写入 MySQL。前端使用 npm workspaces，不引入第二套包管理器。

Python Redis client 锁定 `redis-py 6.4.0`。Celery 5.6.3 的 Kombu Redis transport 要求 `redis-py < 6.5`；Redis Server 版本仍为 7.4，两者版本号不要求一致。

## 驱动与安全选择

- MySQL DBAPI 使用 PyMySQL，减少本地编译依赖。
- 密码哈希采用维护良好的 Argon2 库封装，不自行实现密码学。
- 服务端会话在 M1 落地；M0 只冻结可撤销会话接口与 bootstrap 管理员路径。
- API、Worker 与迁移复用同一领域和数据库包，入口彼此独立。

## 结果

正面结果：部署单元少、事务边界清晰、前后端可并行、Python 计算生态可复用、异步任务有成熟重试能力。

代价：API 与多个领域共享一个代码库和数据库；Redis result backend 不作为长期事实源；同步数据库访问需要通过 worker 数量和连接池控制并发。

## 替代方案

- Django：管理后台成熟，但现有 PRD 已以 FastAPI/OpenAPI/异步契约为中心，切换收益不足。
- 全异步 SQLAlchemy：理论并发更高，但增加驱动、会话和测试复杂度，0.6 无证据需要。
- 微服务：超出两个全栈和 1.5 周时间盒。

## 版本来源与复核

2026-07-21 通过 npm registry 与 PyPI 查询应用依赖可用版本；FastAPI、Celery、SQLAlchemy 的架构用法由其官方文档复核。Context7 因月度额度耗尽未能返回文档。版本在生成锁文件和容器构建时再次验证；不存在或不兼容即停止实现并修订本 ADR，不静默替换。
