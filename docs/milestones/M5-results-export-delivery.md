# M5 结果、导出与试开发交付

| 属性 | 值 |
|---|---|
| 状态 | approved |
| Owner | Web + API + QA + Acceptance |
| 时间盒 | 1.5 天目标 |
| PRD 追踪 | 2、3.7、7、8、10、11.e |

## 目标

工程师可在桌面 Web 快速理解工厂每个区域的静态和逐时冷量，按五种维度导出 CSV；系统完成中英文、明暗主题、部署和最终试开发验收。

## 范围

包含：静态/历史/预测/质量/导出 Tabs、统一 URL 筛选、KPI/曲线/排名/持续时间、区域详情、五维查询、异步 CSV、四主题组合、Docker Compose、示例项目和验收记录。

不包含：地图、2D Canvas、移动端、Excel/PDF/JSON 报告、冷站/前馈灰色入口。

## Definition of Ready

- [ ] M4 verified，存在有效静态/历史/预测批次。
- [ ] Analytics 和 CSV schema approved，golden CSV 可用。
- [ ] UI design token、i18n key、五页面四主题基线 approved。
- [ ] 部署硬件/浏览器和性能测试环境已记录。

## 输出不变量

- 筛选维度：区域、工艺、楼层、建筑、工厂；工艺与空间并列。
- Tabs 切换保持筛选，UI 与 CSV 共用 analytics 查询。
- CSV 每行是时间 × 实体 × cooling_type；TOTAL 不与分项再次相加。
- 功能区分项可输出原始系数；TOTAL/聚合只输出 effective combined coefficient。
- CSV 同时输出 UTC、本地时间和 IANA 时区，UTF-8。
- 失效批次禁止创建/下载有效导出。

## 测试矩阵

| 层级 | 必测行为 |
|---|---|
| Contract | analytics 筛选/分页、export estimate/task/download |
| Integration | UI/CSV 同查询、百万行阻断、重复任务复用、24h 清理 |
| E2E | 五 Tabs、五维筛选、3 次交互区域定位、权限和失效 |
| Visual | 5 页面 × 2 locale × 2 theme，1440×900 |
| Golden | CSV 列、行数、空值、浮点、BOM、checksum |
| Deployment | 空库/seed 启动、重启、备份恢复、日志和 health |

## 演示脚本

从结果首页打开区域筛选、选择 LDI 东区、打开详情，三次交互看到静态分项和逐时曲线；分别按五维查询；按 LDI 工艺导出 CSV 并核对 golden/checksum；另一工程师下载返回 403；切换中英/明暗无缺 key 或阻断错位。

## 质量门禁与 Definition of Done

- [ ] PRD 六个验收剧本全部通过。
- [ ] CSV golden、权限和临时文件清理通过。
- [ ] 四主题截图达到对比度且英文不遮挡主操作。
- [ ] 30/300 区域性能结果附环境，超门限有明确结论。
- [ ] 三个只读示例项目可演示，HDI 主链完整。
- [ ] 试开发部署/回滚/备份说明可执行。
- [ ] 软件验证和专家待验证标签清楚。
- [ ] M5 Acceptance Record 为 GO，创建 `trial-v0.6.0` 候选标签。

## 停止条件

任一越权、聚合/CSV 口径不一致、失效结果可导出、主题缺失键、干净部署失败或把经验模型宣称为专家验证均 NO-GO。
