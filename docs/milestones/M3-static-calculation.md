# M3 静态冷量计算

| 属性 | 值 |
|---|---|
| 状态 | approved |
| Owner | Calculation + API + QA |
| 时间盒 | 1 天目标 |
| PRD 追踪 | P0_08；3.5、4.3、5.3、8 |

## 目标

基于冻结输入生成可追溯的区域静态冷量及工艺/楼层/建筑/工厂聚合，明确低温、中温和 PCW 分流。

## 范围

包含：土建、照明、人员、设备、新风、PCW；湿空气焓值；新风三口径取最大；水温档分流；中间值/来源/公式版本；静态批次和五维聚合。

不包含：冷站容量、设备选型、再热/自然冷却收益、精准动态模型、专家验证结论。

## Definition of Ready

- [ ] M2 verified，项目可冻结完整 revision。
- [ ] 静态公式 Feature Spec 和单位契约 approved。
- [ ] 三个静态 fixture 有输入、中间值、期望、库版本和 checksum。
- [ ] 湿空气库 ADR approved。

## 计算不变量

- 设备/照明/PCW 为 kW，面积 m²，风量 m³/h，焓值 kJ/kg 干空气。
- `Q_fresh = MAX(0, Q_fresh_raw)`。
- 末端全量进入 terminal water class，新风进入 fresh-air water class，PCW 独立。
- `TOTAL_REFERENCE = CHW_LOW + CHW_MEDIUM + PCW`。
- TOTAL 不落入再次求和的聚合输入。
- UI、API 和 CSV 使用同一领域计算/聚合服务。

## 测试矩阵

| 层级 | 必测行为 |
|---|---|
| Unit | 六分项、焓值、截断、低/中温分流、PCW 直输 |
| Property | 负荷非负、分项总和、空间/工艺聚合守恒 |
| Contract | 静态任务、详情血缘、批次状态/错误 |
| Integration | 输入指纹、staging、current 原子切换、旧 revision 保护 |
| Golden | 3 fixture 各中间值和结果误差 ≤0.01 kW 或 fixture 容差 |

## 演示脚本

运行 HDI 静态计算，打开任一区域详情，展示六分项输入、公式、中间值、来源、规则/公式版本；按工艺和空间聚合对账；修改设备功率后旧静态/历史/预测标记失效，禁止作为有效 CSV 批次。

## 质量门禁与 Definition of Done

- [ ] 三个软件基准全部通过并标记 SOFTWARE_VERIFIED。
- [ ] 分流、TOTAL 和五维聚合守恒测试通过。
- [ ] 失败批次不产生部分 current。
- [ ] 界面明确待专家验证，不宣称国标核验。
- [ ] M3 Acceptance Record 为 GO。

## 停止条件

任何单位含糊、TOTAL 重复计数、聚合不守恒、结果无血缘或旧任务切 current 阻断 M4。
