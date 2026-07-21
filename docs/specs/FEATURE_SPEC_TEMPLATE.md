# {{feature_name}} Feature Spec

| 属性 | 填写值 |
|---|---|
| 状态 | draft / approved / implementing / verified / superseded |
| 版本 | {{semver}} |
| Owner | {{role_or_team}} |
| Milestone | {{M0_to_M6}} |
| Issue | {{github_issue}} |
| PRD 追踪 | {{section_and_requirement}} |

## 用户结果

一句话描述用户完成什么，以及可观察的成功结果。

## 范围与非目标

### 包含

- {{in_scope_behavior}}

### 不包含

- {{non_goal}}

## 领域词汇与不变量

列出本功能使用的稳定术语、编码、单位和不能被破坏的规则。

## 正常流程

用编号步骤或状态图描述输入、确认、写入、输出和后续状态。

## 失败与恢复

| 触发 | 错误码/状态 | 用户提示 | 是否写入 | 恢复动作 |
|---|---|---|---|---|
| {{condition}} | {{code}} | {{message_key}} | 是/否 | {{recovery}} |

## 状态清单

| 状态 | 进入条件 | 允许操作 | 退出条件 |
|---|---|---|---|
| {{state}} | {{entry}} | {{actions}} | {{exit}} |

## 规则与权限

列出字段类型、单位、范围、条件必填、阻断/警告、角色和项目归属规则。

## API、数据与版本

列出 OpenAPI 操作、Schema、迁移、幂等键、revision、快照和兼容规则。

## 可观察性

定义审计事件、业务日志、任务指标和错误关联 ID；禁止记录密钥和敏感输入。

## 验收场景

用 Given / When / Then，包含成功、边界、权限、并发和失败恢复。

## 测试映射

| 验收条件 | 测试层级 | 测试文件/fixture | 门禁 |
|---|---|---|---|
| {{criterion}} | unit / contract / integration / e2e | {{path}} | required |

## 阻断审批的问题

只列出会改变实现或验收的问题。存在未关闭项时状态不得改为 approved。
