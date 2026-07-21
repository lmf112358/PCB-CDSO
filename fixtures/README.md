# Fixture 规则

本目录只存放可重复、版本化、无敏感信息的测试数据。

## 目录

- `acceptance/`：按 milestone 组织的端到端验收包。
- `calculation/`：静态和动态公式输入、中间值与预期结果。
- `weather/`：历史、预测和无效气象样例。
- `export/`：CSV golden 与 manifest。
- `visual/`：固定视口截图基线。

## 每个版本必须包含

1. `manifest.json`；seed 符合 `contracts/seeds/seed-manifest.schema.json`，fixture 符合 `contracts/fixtures/fixture-manifest.schema.json`。
2. 数据文件或确定性生成器。
3. 预期结果与数值容差。
4. SHA-256 checksum。
5. `producer`、独立的 `softwareVerifier`、可空的 `expertApprover`、verification status 与 verification evidence。

Golden fixture 审批后不可覆盖。任何变化都创建新版本目录、关联 Issue，并由受影响领域 Reviewer 批准。临时生成物写入 `fixtures/.scratch/`，该目录不得提交。

不得提交真实账号密码、Provider 密钥、客户名称、生产坐标、未脱敏设备清单或其他敏感数据。
