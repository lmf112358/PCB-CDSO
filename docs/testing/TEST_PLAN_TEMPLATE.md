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

| Spec 条件 | Unit | Property | Contract | Integration | E2E | Visual | Performance | Expert |
|---|---|---|---|---|---|---|---|---|
| {{criterion}} | path/NA | path/NA | path/NA | path/NA | path/NA | path/NA | path/NA | record/NA |

## Fixture

列出 dataset id、版本、verification status、checksum、来源、时间范围、预期值和容差。

## 环境

记录 OS、CPU/内存、浏览器、数据库、时区、依赖锁文件和容器镜像摘要。

## 执行命令与预期

逐条列出可复制命令、通过数、失败数和性能阈值。不得只写“运行全部测试”。

## 失败分类

定义产品缺陷、测试缺陷、fixture 缺陷、环境缺陷和专家待确认的判定与处理人。

