# PCB-CDSO 领域词汇表

| 中文 | 稳定英文/编码 | 定义 |
|---|---|---|
| 项目/工厂 | Project / Factory | 0.6 中一一对应，只生产一种 PCB 产品 |
| 产品模板 | Product Template | 产品对应的主要/辅助工序、规则、对话和系数版本集合 |
| 工序 | Process | 固定 PCB 生产步骤或辅助活动 |
| 主要工序 | Main Process | 模板明确要求，项目必须至少有一个功能区绑定 |
| 辅助工序 | Auxiliary Process | 可选生产辅助或非生产功能，如上料、更衣、暂存 |
| 功能区 | Zone | 最小空间和计算单元，只绑定一道工序 |
| 输入修订 | Input Revision | 关键答案确认后单调递增的项目版本 |
| 静态批次 | Static Batch | 基于冻结输入和公式版本的区域/聚合冷量结果 |
| 历史仿真 | Historical Simulation | 三年逐时天气与生产负荷经验系数计算 |
| 未来预测 | Forecast | 连续 168 小时经验预测 |
| 低温冷冻水 | CHW_LOW | 区域指定的低温末端或新风水温档 |
| 中温冷冻水 | CHW_MEDIUM | 区域指定的中温末端或新风水温档 |
| 工艺冷却水 | PCW | 用户直接输入的工艺冷却水负荷 |
| 综合参考 | TOTAL_REFERENCE | 三类负荷之和，不参与再次求和 |
| 软件验证 | SOFTWARE_VERIFIED | 自动化证明实现符合契约，不代表专家签认 |
| 专家验证 | EXPERT_VERIFIED | 领域专家对来源、参数、公式和样例的签认 |

