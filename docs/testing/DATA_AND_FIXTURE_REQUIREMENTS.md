# PCB-CDSO v0.6 数据与 Fixture 准备指南

| 属性 | 值 |
|---|---|
| 状态 | approved |
| 版本 | 0.1.0 |
| 目标 | 在编码前明确所需数据、责任、格式、验证等级和验收用途 |

## 1. 数据治理原则

- 所有 seed 和 golden fixture 必须进入 Git 或受版本控制的制品库，不能只在聊天、Excel 临时副本或个人目录中。
- 每个数据集必须有稳定 ID、版本、来源、Owner、verification status 和 SHA-256 checksum。
- `UNVERIFIED` 数据可用于试开发演示，但不能产生法规硬阻断或专家验证标签。
- Golden fixture 审批后不可原地修改；变更产生新版本并更新预期结果。
- 生产/客户数据进入 fixture 前必须脱敏；默认使用合成数据。
- 时间数据以 UTC 为计算键，同时保存项目 IANA 时区和本地展示值。
- 所有计算和存储使用 SI 单位。

## 2. 数据集总表

每个 manifest 必须分别记录 `producer`、`softwareVerifier`、`expertApprover`。生产者与软件验证者不得是同一执行身份；未要求专家验收时 `expertApprover` 为 `null`，不得用待签字暗示已经完成专家验证。

| 数据集 ID | 内容 | 最晚阶段 | 初始验证 | Owner | 主要验收用途 |
|---|---|---|---|---|---|
| `seed-product-templates` | 多层板、HDI、IC 载板模板及版本 | M1 | UNVERIFIED | 产品/PCB 专家 | 模板发布和项目创建 |
| `seed-process-catalog` | 主/辅助工序、双语名、顺序 | M1 | UNVERIFIED | PCB 专家 | 主要工序覆盖 |
| `seed-field-registry` | 八阶段字段、类型、单位、规则引用 | M2 | SOFTWARE_VERIFIED | 产品/技术 | 强状态机和问答 |
| `seed-conversation` | 双语问题、帮助、示例、选项、错误键 | M2 | SOFTWARE_VERIFIED | 产品/UI | 中英文采集流程 |
| `seed-environment-rules` | 温湿度、洁净度、压差、来源 | M2 | UNVERIFIED | 暖通/PCB 专家 | 阻断与警告 |
| `seed-weather-coefficients` | 水温档 × 温湿度矩阵 | M4 | UNVERIFIED | 暖通专家 | 动态经验模型 |
| `seed-production-coefficients` | productionRate 分段点/系数 | M4 | UNVERIFIED | 暖通/生产专家 | 工序负荷变化 |
| `fixture-users-projects` | 管理员、工程师、项目/空间结构 | M1-M2 | SOFTWARE_VERIFIED | QA | 权限、层级和复制 |
| `fixture-static-001..003` | 三个静态输入、中间值、结果 | M3 | SOFTWARE_VERIFIED | Calculation+QA | 公式与单位 |
| `fixture-dynamic-24h` | 24 小时天气、计划、系数、负荷 | M4 | SOFTWARE_VERIFIED | Calculation+QA | 动态公式 |
| `fixture-weather-history` | 最长三年 UTC 整点气象 | M4 | SOFTWARE_VERIFIED | Data+QA | 历史仿真和性能 |
| `fixture-weather-forecast` | 连续 168 小时预报 | M4 | SOFTWARE_VERIFIED | Data+QA | 未来预测 |
| `fixture-weather-invalid` | 缺失、重复、越界、DST 反例 | M4 | SOFTWARE_VERIFIED | Data+QA | 失败与恢复 |
| `fixture-concurrency` | revision、幂等、旧任务晚到 | M2-M4 | SOFTWARE_VERIFIED | API+QA | 原子性和 current |
| `fixture-aggregation` | 区域/工艺/楼层/建筑/工厂预期 | M3-M6 | SOFTWARE_VERIFIED | Calculation+QA | 聚合守恒 |
| `golden-csv` | 五维长表导出与 checksum | M6 | SOFTWARE_VERIFIED | QA | CSV 语义和编码 |
| `golden-ui` | 5 页面 × 中英 × 明暗截图 | M5 | SOFTWARE_VERIFIED | UI+QA | 主题和溢出 |
| `expert-static-golden` | 专家签认静态样例 | 交付后 | EXPERT_VERIFIED | 暖通专家 | 领域验证升级 |

## 3. 产品、工序与问答种子

### 3.1 产品模板

每个模板记录：

- `templateId`、语义版本、产品编码、双语名称。
- 生命周期 `DRAFT/PUBLISHED/ARCHIVED` 与核验状态分离。
- 主要工序和辅助工序稳定编码及顺序。
- 规则、对话、天气系数、生产系数的已发布版本引用。
- 来源文档、适用范围、创建人、审批记录和 checksum。

内置模板均以 `PUBLISHED + UNVERIFIED` 交付；已发布快照只读。

### 3.2 字段 registry

每个字段记录：

- 稳定 `fieldCode` 和所属阶段。
- 数据类型、SI 单位、精度、最小/最大值、枚举。
- 条件必填表达式和依赖字段。
- 默认值及默认值来源。
- 阻断规则、警告规则、允许覆盖与覆盖原因要求。
- 双语 label/help/example/message key。
- 写入目标和影响的下游阶段/结果域。

字段类型、单位、八阶段骨架和强校验由代码固定；管理员不能通过配置改变。

### 3.3 环境规则

规则最少包含：稳定编码、产品/工序/字段适用范围、运算符、阈值、SI 单位、严重度、来源类型、标准编号/版本/条款、核验状态和有效版本。没有专家签认记录时只可产生经验警告。

## 4. 气象数据

标准 CSV：UTF-8、逗号分隔、BOM 可选，表头固定：

```csv
timestamp_utc,temp_c,rh_pct,pressure_pa,source_quality
2024-01-01T00:00:00Z,12.4,68.0,101325,OBSERVED
```

规则：

- `timestamp_utc` 为唯一 UTC 整点，不重复。
- `temp_c` 范围 -80 到 60。
- `rh_pct` 范围 0 到 100。
- `pressure_pa` 可空或 80000 到 110000。
- `source_quality` 为 `OBSERVED/FORECAST/FILLED`。
- 所选区间缺一小时即阻断；0.6 不自动插补。
- 历史窗口最长三个连续本地日历年；预测从下一 UTC 整点起 168 小时。
- DST 回拨的两个本地同名小时保留为不同 UTC；跳时不补造本地小时。

反例 fixture 至少覆盖：错误表头、非 UTF-8、无时区、半小时、重复、缺失、RH 越界、压力越界、内部矩阵缺点和坐标轴外钳制。

## 5. 静态计算 fixture

每份基准必须同时提供输入、期望中间值和期望输出：

- 区域面积、高度、室内设定、站点压力。
- 土建指标、照明、人员、设备清单及利用/散热系数。
- 排风、压差补风、人员/面积最小新风。
- 室外温湿度、湿空气库和版本。
- PCW 峰值、利用率。
- 末端/新风水温档。
- `Q_civil/Q_lighting/Q_people/Q_equipment/Q_fresh_raw/Q_fresh/Q_PCW`。
- CHW_LOW、CHW_MEDIUM、PCW、TOTAL_REFERENCE。
- 工艺、楼层、建筑、工厂聚合结果。

功率默认绝对容差 0.01 kW；若湿空气库造成更大可解释差异，必须在 fixture metadata 冻结容差和库版本。

三份最小情形：

1. 末端中温、新风低温、PCW 非零。
2. 末端与新风同一水温档，验证相加不重复。
3. `Q_fresh_raw < 0`，验证机械制冷新风负荷截断为 0。

## 6. 动态与并发 fixture

24 小时动态基准记录每小时：UTC、本地时间、天气、productionRate、插值后的天气/生产系数、三类静态基准、三类动态负荷和 TOTAL。

必须覆盖：

- `Kweather(PCW)=1`。
- 分段点线性插值、端点钳制、无计划时 productionRate=0。
- 例外日覆盖周计划，区间左闭右开。
- 两个 Agent/Tab 使用同一旧 revision，第二次确认返回 409 且不部分写入。
- 同一幂等键返回同一任务。
- 旧任务晚完成不切换 current。
- 容器重启后任务恢复或明确失败，不生成半成品有效批次。

## 7. 输出 fixture

CSV golden 每行是“时间 × 实体 × cooling_type”。选择全部冷源时最多包含 CHW_LOW、CHW_MEDIUM、PCW、TOTAL_REFERENCE；TOTAL 不参与再次汇总。功能区的三个分项可有原始系数，TOTAL 和聚合行只用 effective combined coefficient。

每个 golden 记录：

- 筛选条件和批次依赖指纹。
- 预期展开行数。
- UTF-8 BOM 规则。
- 列顺序、时间格式、浮点格式和空值表示。
- 文件 SHA-256。

UI golden 固定 1440×900，覆盖登录、项目列表、问答、结果中心、管理员模板，执行 `zh-CN/en-US × light/dark`。

## 8. 文件结构与命名

```text
contracts/seeds/
  seed-manifest.schema.json
  <dataset-id>/<version>/manifest.json
fixtures/
  acceptance/<milestone>/<version>/
  calculation/static/<case-id>/<version>/
  calculation/dynamic/<case-id>/<version>/
  weather/history/<dataset-id>/<version>/
  weather/forecast/<dataset-id>/<version>/
  weather/invalid/<case-id>/
  export/<case-id>/<version>/
  visual/<page>/<locale>/<theme>/
```

版本目录创建后不可覆盖。较大三年数据若超过 GitHub 普通文件限制，使用 Git LFS 或固定生成器与小型种子，但 manifest/checksum/生成器必须进入 Git。

## 9. 数据进入阶段的门禁

1. Owner 创建 manifest 和数据。
2. 通过仓库内 Draft 2020-12 子集校验器执行 manifest schema，并自动检查编码、范围、唯一性和 checksum；schema 自身缺少核心声明时直接阻断。
3. Test Agent 运行正反例。
4. 对计算数据核对中间值和聚合守恒。
5. Reviewer 检查来源、单位、许可和敏感信息。
6. 合并后不可原地修改；更新必须新版本。
7. 专家签认单独生成记录并升级状态，不改历史发布快照。

每次状态升级都必须追加 `verificationEvidence`，记录验证级别、验证人、时间、方法和签字记录路径。`EXPERT_VERIFIED` 必须存在对应专家证据；任何数据内容变化都创建新版本并重新计算 checksum。
