# {{feature_name}} Test Plan

| 属性 | 填写值 |
|---|---|
| 状态 | draft / approved / verified |
| Spec | {{feature_spec_path_and_version}} |
| Owner | {{test_owner}} |
| Fixture Version | {{dataset_id_and_version}} |

## 风险排序

| 风险 | 影响 | 概率 | 测试策略 | PR 门禁 |
|---|---|---|---|---|
| {{risk}} | high/medium/low | high/medium/low | {{strategy}} | yes/no |

## 验收追踪

| Requirement ID | Spec 条件 | 预期/阈值 | Fixture 版本 | 层级 | 测试文件 | 精确命令 | 结果 | 证据 | NA 原因 |
|---|---|---|---|---|---|---|---|---|---|
| {{requirement_id}} | {{criterion}} | {{expected}} | {{fixture_version}} | unit/contract/integration/e2e/visual/performance/expert | {{path}} | {{command}} | not_run/pass/fail | {{evidence_path}} | {{reason_or_not_applicable}} |

每个 Requirement ID 可以有多行覆盖不同层级；任何 `NA` 都必须说明为何该层级不适用，不能用 NA 掩盖缺测试。

## Fixture

列出 dataset id、版本、verification status、checksum、来源、时间范围、预期值和容差。

## 环境

记录 OS、CPU/内存、浏览器、数据库、时区、依赖锁文件和容器镜像摘要。

## 执行命令与预期

逐条列出可复制命令、通过数、失败数和性能阈值。不得只写“运行全部测试”。

## 失败分类

定义产品缺陷、测试缺陷、fixture 缺陷、环境缺陷和专家待确认的判定与处理人。
