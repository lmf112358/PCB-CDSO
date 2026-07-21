# M0 仓库与运行基础

| 属性 | 值 |
|---|---|
| 状态 | implementing |
| Owner | Platform / Orchestrator |
| PRD 追踪 | P0_01；P0_14 基线 |

## 目标与范围

从空环境可重复建立 Web、API、MySQL、Redis、Celery Worker、迁移和管理员引导，并冻结 M1-M6 共同依赖的机器契约。M0 不包含业务页面、真实冷量公式、模板编辑器或气象 Provider。

## 已交付

- React/Vite 中英文、明暗主题桌面登录壳；M0 登录明确禁用。
- FastAPI live/ready、稳定错误体、Request ID 与 OpenAPI。
- SQLAlchemy/Alembic MySQL 基线和幂等 ADMIN 初始化。
- Redis/Celery 真实 Worker 与任务幂等基础。
- Docker Compose 七服务编排、非 root 应用容器和健康检查。
- JSON Schema、锁文件、统一质量命令和 GitHub Actions。
- 空卷、重启、浏览器、Redis 故障和真实 Worker 验收证据。

## 质量结论

候选提交 `3591987a59040dcc12a42b73a2a20640151de1f8` 已通过本地软件门禁，证据位于 `artifacts/acceptance/M0/`。GitHub 审计仍显示 `main protected=false` 且候选分支无 PR/CI 状态。启用分支保护、PR 必需检查全部通过并由产品方签认 `docs/testing/acceptance/M0-acceptance.md` 后，才能将状态更新为 `verified` 并进入 M1。
