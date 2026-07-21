# M1 身份、模板与项目

| 属性 | 值 |
|---|---|
| 状态 | approved |
| Owner | API + Web |
| 时间盒 | 1 天目标 |
| PRD 追踪 | P0_02、P0_03、P0_13；P0_07 dependency（Primary M4）；3.1、3.2、5.1 |

## 目标

管理员可建立工程师和发布版本化模板；工程师可登录并用已发布模板和地理信息创建只属于自己的项目，可靠提交首个气象任务并立即获得 task id。

## 范围

包含：首个管理员、工程师创建/停用/重置、两角色授权、三模板种子、生命周期与核验双状态、不可变快照、项目创建/列表/归档/恢复/复制/管理员转交；`POST /projects` 接收 `countryCode`、`adminArea`、`city`、`timezone` 和客户端 `idempotencyKey`，并在一个事务中提交 Project、Outbox 和 `DISPATCH_PENDING` Task，响应返回同一 weather task id。

不包含：邮件邀请、SSO、组织架构、第三角色、完整八阶段问答和计算。M1 只用 fake dispatcher 验证可靠派发，不连接真实 Provider 或下载真实气象数据。

阶段边界：M1 只负责气象 Task 的原子创建和 fake dispatch；M2 负责通用工具卡与全局任务坞；真实 Provider、六阶段抓取、CSV 兜底和 current 发布均由 P0_07 Primary M4 负责。

## Definition of Ready

- [ ] M0 verified。
- [ ] 认证/会话 ADR 和 OpenAPI 已批准。
- [ ] 三模板/工序 seed manifest 有版本、来源、Owner、checksum。
- [ ] 权限矩阵和越权 fixture 已批准。

## 关键规则

- 角色只有 ADMIN 和 ENGINEER。
- 工程师只能访问自己项目；管理员可见/转交全部项目。
- 首次登录不强制改密。
- 模板生命周期和核验状态正交；`PUBLISHED + UNVERIFIED` 合法。
- 已发布快照不可修改，只能复制新草稿。
- 项目复制只复制结构/输入，不复制天气、结果、任务、导出或审计。
- 归档项目只读，可查看/导出原有效结果，不能创建新任务。
- 同一 actor 与客户端幂等键重复创建时返回同一 project id 和 weather task id，不重复写 Project、Outbox 或 Task。
- Project、OutboxEvent 和 `DISPATCH_PENDING` Task 必须原子提交；任一写入失败全部回滚，dispatcher 不可用时保留可重试的待派发任务。

## 测试矩阵

| 层级 | 必测行为 |
|---|---|
| Unit | 密码哈希、角色策略、模板状态转换 |
| Contract | 登录、用户、模板、项目 API、地理字段、幂等键、weather task id 和 403/404/409/422 |
| Integration | 首个管理员一次性注入、会话撤销、模板发布事务/不可变、Project/Outbox/Task 原子提交和 fake dispatcher 重试 |
| E2E | 管理员建工程师；工程师登录、选模板建项目、归档恢复 |
| Security | 跨 owner 的已存在单项 id 与随机不存在 id 返回不可区分的 404；列表 200 且过滤不可见项；已在调用方 scope 内定位但角色缺少写权限才返回 403；停用后会话失效 |

## 演示脚本

空库启动后管理员登录，创建工程师；复制 HDI 模板并发布为待核验；工程师创建项目；另一个工程师分别请求该项目真实 id 与随机不存在 id，两者返回不可区分的 404，其项目列表返回 200 且不含该项目；对已在调用方 scope 内定位但角色缺少权限的写操作返回 403；归档项目后计算入口不可用；管理员转交后旧 Owner 立即失权并按相同防枚举规则返回 404。

## 质量门禁与 Definition of Done

- [ ] 三模板均可选/复制，HDI 有完整验收项目，其他有只读演示项目。
- [ ] 发布缺双语或无效引用时原子失败。
- [ ] 账号停用、项目转交、归档权限测试通过；跨 owner 与随机不存在单项 id 的 404 不可区分，列表 200 filtered，已定位资源的角色写权限不足才返回 403。
- [ ] 审计记录 actor、target、time、request ID，不记录密码。
- [ ] M1 Acceptance Record 为 GO。

## 停止条件

任何越权、快照可变、首个管理员凭据泄露或发布部分成功都阻断 M2。
