# M2 专家对话工作台测试计划

| 属性 | 值 |
|---|---|
| 状态 | approved |
| Spec | `docs/specs/m2/expert-conversation-workspace.md` v1.0.0 |
| Owner | M2 Test Agent / Acceptance Agent |
| Fixture Version | `fixtures/acceptance/M2/expert-conversation-workspace/1.0.0`，PLANNED / NOT_VERIFIED |

本计划冻结未来 M2 实现的可执行门禁。当前 PRD 重基线只交付规格和测试设计；下列运行时测试、fixture 与证据路径是计划目标，不表示文件已经存在、命令已经通过或 fixture 已经验证。

## 风险排序

| 风险 | 影响 | 概率 | 测试策略 | PR 门禁 |
|---|---|---|---|---|
| 自然语言绕过确认直写计算字段 | high | high | 数据库前后快照、状态机 property test、网络请求断言 | yes |
| 刷新/重登丢消息、问题游标、草稿或任务 | high | high | 服务器快照恢复 E2E，清空客户端缓存后重验 | yes |
| Tool Card 与任务坞拥有不同 task id/状态 | high | medium | API、DOM 和数据库三方同 id 对照 | yes |
| Task 运行阻断八阶段问答 | high | medium | 固定 RUNNING Task 并完成后续确认 | yes |
| 双 Tab 重复提交或旧 revision 覆盖 | high | high | 并发屏障、409、零部分写入和消息去重 | yes |
| 权限变化后仍显示或轮询他人资源 | high | medium | ENGINEER A/B 与 ADMIN 权限矩阵、日志脱敏 | yes |
| 轮询失败被误判为 Task 失败 | medium | medium | 401/403/404/网络/游标失效故障注入 | yes |
| 双语、明暗或键盘路径不可用 | high | medium | 四组合 visual/E2E、axe、键盘与 200% 缩放 | yes |

## 测试用例

每条命令均从仓库根目录执行；“证据”是未来 Acceptance Agent 成功执行后必须生成的目标路径。

| Test ID | 层级 | 前置条件 | 输入/动作 | 预期结果 | 精确命令 | 证据路径 |
|---|---|---|---|---|---|---|
| M2-U-001 | unit/property | 已实现 Answer 状态机 | 生成合法/非法转换及重复事件 | messageType 封闭枚举精确等于 `AGENT_PROMPT`、`USER_DRAFT`、`CONFIRMATION_CARD`、`TOOL_CARD`；状态机仅改变确认卡 `presentationState`，非法转换零写入且不产生新消息类型 | `python -m pytest tests/unit/conversation/test_answer_state_machine.py::test_message_types_and_confirmation_states_are_closed_enums -q` | `artifacts/acceptance/M2/M2-U-001.txt` |
| M2-U-002 | unit | 字段 registry 与自然语言解析器 | 输入“面积 586 平方米”等自然语言，不点击确认 | 仅形成 `USER_DRAFT` 和 Confirmation Card；计算字段 repository 调用数为 0 | `python -m pytest tests/unit/conversation/test_answer_state_machine.py::test_natural_language_never_persists_before_confirmation -q` | `artifacts/acceptance/M2/M2-U-002.txt` |
| M2-U-003 | unit/property | 八阶段 registry | 随机完成/回退阶段并含不可见条件问题 | 顺序编码固定；恢复总定位首个可见未完成问题；已完成答案不丢失 | `python -m pytest tests/unit/conversation/test_stage_cursor.py -q` | `artifacts/acceptance/M2/M2-U-003.txt` |
| M2-U-004 | unit/property | HDI 工艺与区域 fixture | 遗漏主要工序；面积偏差 0%、2%、3%、大于 3%；区域双绑定 | 漏主要工序/大于 3%/双绑定阻断；0–3% 警告需原因后放行 | `python -m pytest tests/unit/domain/test_process_coverage_and_area_tolerance.py -q` | `artifacts/acceptance/M2/M2-U-004.txt` |
| M2-U-005 | unit | i18n 资源与消息 registry | 枚举四消息、八阶段、选项、帮助、错误和 aria key | `zh-CN`/`en-US` 均存在非空值，缺任一 key 测试失败 | `python -m pytest tests/unit/web/test_conversation_i18n.py -q` | `artifacts/acceptance/M2/M2-U-005.txt` |
| M2-C-001 | contract | 对话 OpenAPI/Schema 已批准并实现 | 提交原始回答、生成 impact、确认；缺字段/非法单位；读取确认前后时间线 | messageType 集合精确为四枚举；原始回答始终为不可变 `USER_DRAFT`；系统校验由 `CONFIRMATION_CARD.presentationState` 六状态表达；Tool Card 仅为 `TOOL_CARD` 且含后端 `taskId`；非法输入为稳定 `422` 且零业务写入 | `python -m pytest tests/contracts/test_conversation_contract.py::test_exact_message_enum_and_presentation_mapping -q` | `artifacts/acceptance/M2/M2-C-001.txt` |
| M2-C-002 | contract | 两个有效会话基于同 revision | A 先确认，B 以旧 `expectedInputRevision`/token 确认 | B 得到 `409 REVISION_CONFLICT` 标准错误体；token 不可复用；无部分写入 | `python -m pytest tests/contracts/test_conversation_contract.py::test_stale_revision_and_token_return_409 -q` | `artifacts/acceptance/M2/M2-C-002.txt` |
| M2-C-003 | contract | 同 actor；可控幂等键/hash 和响应丢包 | 首次 confirm 完成但丢失响应；同 key/hash 重放；同 key/different hash；不同 key 复用已消费 token | 判定顺序先查幂等记录：同 key/hash 返回原响应且仅一次 commit；同 key/different hash 为 `409 IDEMPOTENCY_CONFLICT`；不同 key 重用 token 才为 `409 TOKEN_ALREADY_USED` | `python -m pytest tests/contracts/test_conversation_contract.py::test_confirmation_idempotency_precedes_token_replay_check -q` | `artifacts/acceptance/M2/M2-C-003.txt` |
| M2-C-004 | contract | 可放行 warning；有效 revision/impact token | 首次确认；检查 challenge 绑定；分别提交空 reason、显示文案 code、合法双语 code/reason；最终确认；重放与改变 revision | 首次 token 原子消费并返回未绑定 reason 的 challenge；非法原因 `422`；合法原因原子签发 reason-bound token；最终只接受新 token并 commit；幂等重放返回原响应，不同 key token 重放 `TOKEN_ALREADY_USED`，revision 变化 `REVISION_CONFLICT` | `python -m pytest tests/contracts/test_conversation_contract.py::test_warning_challenge_reasons_and_final_token_contract -q` | `artifacts/acceptance/M2/M2-C-004.txt` |
| M2-I-001 | integration/real-MySQL | 空测试 schema；有效 draft/token/revision | 在答案、审计、revision、失效标记各写点注入 pre-commit 失败 | 每例整体回滚；成功例原子写入且 revision 只加 1 | `python -m pytest tests/integration/test_answer_command.py::test_answer_commit_is_atomic_at_every_write_point -q` | `artifacts/acceptance/M2/M2-I-001.txt` |
| M2-I-002 | integration | static/historical/forecast 结果均存在 | 分别修改只影响一个或多个域的已提交字段 | 按影响分析精确标记对应域失效；未影响域不变；审计记录前后 revision | `python -m pytest tests/integration/test_answer_command.py::test_committed_answer_propagates_domain_invalidation -q` | `artifacts/acceptance/M2/M2-I-002.txt` |
| M2-I-003 | integration/security | ENGINEER A/B、ADMIN；A 项目和对话/Task；固定随机不存在 task id | B 写 A 资源、列表查询、单查 A 的存在 task id 与随机 id；ADMIN 查授权资源 | 越权写为 `403` 且零写入；列表 `200` 并过滤；B 两种单项 GET 均为不可区分 `404` envelope/message/timing class；响应/日志不泄露内容；ADMIN 按授权可见 | `python -m pytest tests/integration/test_conversation_authorization.py -q` | `artifacts/acceptance/M2/M2-I-003.txt` |
| M2-I-004 | integration/real-MySQL | warning challenge/token 故障注入；幂等与答案表 | 在首次 token 消费+challenge、原因验证+reason-bound token、最终 token 消费+commit 各事务写点故障并模拟响应丢失 | 三段各自原子；网络丢包同 key/hash 返回原响应；不同 key 无 token 可重复使用窗口；成功后至多一次答案/revision/audit | `python -m pytest tests/integration/test_answer_command.py::test_warning_challenge_reason_token_transactions_are_atomic -q` | `artifacts/acceptance/M2/M2-I-004.txt` |
| M2-I-005 | integration/concurrency | 同问题 Tab A/B 各有稳定 draftId；可控制请求顺序 | A/B 交错 autosave，制造同 draftId CAS 冲突；A commit；随后送达旧 save 与旧 clear 的全部顺序排列 | draftVersion 单调；冲突 `409` 且两版本可选；A commit 只条件清 A 的匹配版本；B 和较新 A 草稿不被清；迟到 save/clear 不覆盖或删除新版本 | `python -m pytest tests/integration/test_composer_draft_concurrency.py -q` | `artifacts/acceptance/M2/M2-I-005.txt` |
| M2-E-001 | e2e/API/performance | Docker Compose M2；ENGINEER；已发布 HDI 模板；M1 fake dispatcher | 创建“深圳 HDI 工厂”，选择 `CN/广东省/深圳市/Asia/Shanghai` 并确认 | 2 秒内时间线 Tool Card 与 360px 任务坞显示 API/数据库同一持久化 task id；无第二 Task | `python -m pytest tests/e2e/test_expert_conversation_workspace.py::test_shenzhen_hdi_tool_card_and_dock_share_persisted_task_id -q` | `artifacts/acceptance/M2/M2-E-001.json` |
| M2-E-002 | e2e | M2-E-001；Task 固定为 `RUNNING` | 不结束 Task，继续回答建筑/楼层问题并确认 | Composer/发送/确认均可用；问题推进并提交；Task id/状态不被对话修改 | `python -m pytest tests/e2e/test_expert_conversation_workspace.py::test_running_weather_task_does_not_block_questions -q` | `artifacts/acceptance/M2/M2-E-002.zip` |
| M2-E-003 | e2e/performance | 300 区域项目；时间线、未完成问题、未提交草稿、RUNNING Task 已持久化 | 清空可替代客户端缓存并刷新页面 | 恢复完整有序时间线、首个未完成问题、原 Composer 草稿和同 id 任务坞；首个问题可操作 `<=2.0s`，超过 `4.0s` 失败 | `python -m pytest tests/e2e/test_expert_conversation_workspace.py::test_refresh_restores_timeline_question_draft_and_dock -q` | `artifacts/acceptance/M2/M2-E-003.json` |
| M2-E-004 | e2e | M2-E-003；有效账号 | 登出并重新登录后打开项目 | 从服务端恢复阶段、时间线、草稿、偏好和任务坞；不依赖旧前端内存 | `python -m pytest tests/e2e/test_expert_conversation_workspace.py::test_relogin_restores_server_state -q` | `artifacts/acceptance/M2/M2-E-004.zip` |
| M2-E-005 | e2e/concurrency | 同一工程师两个浏览器 Tab，均为 revision 12 | A 提交至 13；B 用 revision 12 确认；切换 Tab 并轮询 | B 为 `409`、零部分写入且草稿保留；两 Tab 最终 revision 13；无重复消息、Task 或进度重置 | `python -m pytest tests/e2e/test_expert_conversation_workspace.py::test_two_tabs_conflict_without_duplicate_task_or_message -q` | `artifacts/acceptance/M2/M2-E-005.zip` |
| M2-E-006 | e2e | 当前面积字段未提交 | 在 Composer 输入自然语言答案并发送，检查卡片和数据库，再点击确认 | 确认前只出现结构化 Confirmation Card 且业务值不变；确认后才原子写入规范化 SI 值 | `python -m pytest tests/e2e/test_expert_conversation_workspace.py::test_natural_language_only_creates_confirmation_card -q` | `artifacts/acceptance/M2/M2-E-006.zip` |
| M2-E-007 | e2e/recovery | 活动 Task；可控制 GET 响应与时钟 | 注入网络失败、401、403、404、过期游标；恢复网络/登录/权限 | 网络失败显示陈旧而非 FAILED；401 停轮询并重登恢复；403/404 移除不可见项；游标失效全量重取；始终同 task id | `python -m pytest tests/e2e/test_task_dock_recovery.py::test_polling_auth_and_cursor_failures_recover_from_server -q` | `artifacts/acceptance/M2/M2-E-007.zip` |
| M2-E-008 | e2e/layout | 至少 4 个活动 Task；支持的最小桌面视口 | 展开/折叠任务坞，按 `Ctrl/Cmd+J`，滚动到确认卡并聚焦 Composer | 展开宽 360px、只露 3 摘要并显示更多数量；快捷键不抢 Composer 焦点；不遮挡发送按钮/当前确认卡 | `python -m pytest tests/e2e/test_task_dock_layout.py -q` | `artifacts/acceptance/M2/M2-E-008.zip` |
| M2-E-009 | e2e/keyboard | Composer 未聚焦；另备普通输入框、contenteditable 和输入法 composition 场景 | 在非输入控件焦点按 `/`；分别在已有输入控件焦点及 composition 中按 `/` | 仅第一种聚焦 Composer 且不插入 `/`；已有输入焦点和 composition 均不被抢占，原输入保持 | `python -m pytest tests/e2e/test_conversation_keyboard.py::test_slash_focuses_composer_only_outside_editable_or_ime -q` | `artifacts/acceptance/M2/M2-E-009.zip` |
| M2-E-010 | e2e/keyboard | Composer 含未提交文本；覆盖 Windows/Linux Control 与 macOS Meta；输入法可控 | 按 `Ctrl/Cmd+Enter`；在 composition 中按同键并结束 composition | 正常场景恰发送一次并形成 `USER_DRAFT`；composition 中零发送，结束后必须再次按键才发送 | `python -m pytest tests/e2e/test_conversation_keyboard.py::test_ctrl_or_cmd_enter_sends_once_outside_ime -q` | `artifacts/acceptance/M2/M2-E-010.zip` |
| M2-E-011 | e2e/keyboard | 阶段 1/2 已完成、阶段 3 当前；Composer 有未提交草稿 | 按 `Alt+↑`，再返回阶段 3 | 到最近已完成阶段 2；导航前草稿已保存，返回后文本、结构化值和目标问题完全保留；无业务提交 | `python -m pytest tests/e2e/test_conversation_keyboard.py::test_alt_up_moves_to_latest_completed_stage_and_preserves_draft -q` | `artifacts/acceptance/M2/M2-E-011.zip` |
| M2-E-012 | e2e/keyboard | 阶段 2 当前、阶段 3 已解锁、阶段 4 锁定；Composer 有未提交草稿 | 按 `Alt+↓`；在阶段 3 再按一次 | 首次仅到下一已解锁阶段 3并保存草稿；第二次因无可用目标保持阶段 3；返回阶段 2 草稿完整且无业务提交 | `python -m pytest tests/e2e/test_conversation_keyboard.py::test_alt_down_moves_only_to_next_unlocked_and_preserves_draft -q` | `artifacts/acceptance/M2/M2-E-012.zip` |
| M2-E-013 | e2e/keyboard/layout | 任务坞可折叠；Composer、普通输入框分别持有焦点 | 在两种焦点下按 `Ctrl/Cmd+J` 两次 | 每次只切换任务坞展开态；焦点、选择区和输入内容不变；不触发 Composer 发送 | `python -m pytest tests/e2e/test_conversation_keyboard.py::test_ctrl_or_cmd_j_toggles_dock_without_stealing_input_focus -q` | `artifacts/acceptance/M2/M2-E-013.zip` |
| M2-E-014 | e2e/concurrency/recovery | 同 task id；可控制 list/detail 响应顺序、version、activeOnly、认证和网络 | 先返回终态再迟到 RUNNING；让已知活动项从 activeOnly 消失；detail 依次覆盖 200 active、200 terminal、401、404、网络错误及达到最大退避 | sequence/version 丢弃迟到 RUNNING；200 active 下一轮补查、200 terminal 缓存 5 秒、401 停全部轮询且登录后恢复、404 立即移除不推断终态、网络错误保留 last-known 并指数退避，到上限仍重试且不假成功 | `python -m pytest tests/e2e/test_task_dock_recovery.py::test_out_of_order_poll_and_active_terminal_race_all_branches -q` | `artifacts/acceptance/M2/M2-E-014.zip` |
| M2-E-015 | e2e/recovery | Tab A 已保存草稿；可刷新、重登、开 Tab B/换设备 | 刷新 A；打开 B；分别以单草稿和多草稿状态重登/换设备 | A 复用 sessionStorage draftId；B 生成新 id 并发现 A；无本地 id 时单项自动恢复，多项按 updatedAt desc/draftId asc 展示且必须选择/合并/丢弃，无静默选择 | `python -m pytest tests/e2e/test_composer_draft_recovery.py -q` | `artifacts/acceptance/M2/M2-E-015.zip` |
| M2-V-001 | visual/e2e | 固定 Chromium、DPR 1、字体已加载、动画关闭；视口 1440x900 与 1280x720；批准 golden | 四主题组合各在两个视口截整个应用及 Composer/确认卡/任务坞，mask 动态 Task 时间与进度 | 每张 pixel diff `<=0.2%`，关键控件 bbox 偏移 `<=2px`；无缺 key/截断/仅颜色状态 | `python -m pytest tests/visual/test_conversation_four_theme_matrix.py -q` | `artifacts/acceptance/M2/M2-V-001/manifest.json` |
| M2-A-001 | accessibility/e2e | Chromium；键盘；200% 缩放 | 仅键盘遍历阶段导航、消息、Composer、确认卡、任务坞；运行 axe | 零 serious/critical axe 问题；可见焦点/顺序/名称/live region/焦点归还正确；缩放后无遮挡和二维滚动陷阱 | `python -m pytest tests/accessibility/test_conversation_workspace_a11y.py -q` | `artifacts/acceptance/M2/M2-A-001.zip` |
| M2-G-001 | governance | 工作树含本规格与计划 | 执行治理、21 单测、占位扫描和 Markdown diff 检查 | 治理有效；21/21 单测通过；扫描无匹配；diff check 零错误 | `python -m unittest tests.governance.test_check_governance -v` | `artifacts/acceptance/M2/M2-G-001.txt` |

## Fixture

| Dataset ID | 版本 | 状态 | 计划内容与来源 | 校验条件 |
|---|---|---|---|---|
| `m2-expert-conversation-workspace` | 1.0.0 | PLANNED / NOT_VERIFIED | 固定 ENGINEER A/B、ADMIN、深圳 HDI 项目、八阶段消息、首个未完成问题和 Composer 草稿；基于批准 PRD/Spec | 文件尚不存在，不声明 checksum、签名或验证结果 |
| `m2-process-validation` | 1.0.0 | PLANNED / NOT_VERIFIED | HDI 固定工艺链、填孔电镀覆盖、0/2/3/>3% 面积边界、规则来源 | 专家未签认的规则保持 `UNVERIFIED`，软件测试不升级为 `EXPERT_VERIFIED` |
| `m2-task-polling-faults` | 1.0.0 | PLANNED / NOT_VERIFIED | 同一 task id 的活动/终态、401/403/404、网络中断、过期游标和轮询时钟 | 不依赖真实 Provider、外网、生产账号或非确定当前时间 |
| `m2-four-theme-golden` | 1.0.0 | PLANNED / NOT_VERIFIED | 中/英 × 明/暗；Chromium/DPR 1；1440x900 与 1280x720；固定字体、截图区域、mask、主流程及错误恢复截图 | 仅在固定环境生成、checksum 匹配并由独立 Visual Reviewer 批准后从 `NOT_VERIFIED` 升级；阈值 pixel diff `<=0.2%`、关键控件 bbox 偏移 `<=2px` |

计划 manifest 路径为 `fixtures/acceptance/M2/expert-conversation-workspace/1.0.0/manifest.json`。只有 fixture 文件实际创建、manifest schema 与 checksum 通过、producer 和独立 verifier 不同、验证记录存在且对应测试通过后，才可升级为 `SOFTWARE_VERIFIED`；领域规则还需独立专家签认才能标记 `EXPERT_VERIFIED`。

## 环境

- Windows 或 Linux Docker host；至少 8 核 CPU、16 GB 内存、SSD；记录实际 OS/CPU/内存。
- 仓库锁文件对应的 Python 3.12、Node/browser runtime；MySQL、Redis 和浏览器镜像记录 sha256 摘要。
- Chromium 为 required；Firefox/WebKit 作为兼容证据；时区固定 `Asia/Shanghai`，测试时钟可冻结。
- visual 固定 Chromium、DPR 1、`1440x900` 和最低 `1280x720`；等待批准字体加载完成，关闭动画/过渡/光标闪烁，固定全应用及 Composer/确认卡/任务坞截图区域，并 mask 动态 Task 时间戳和进度数值。可访问性另测 200% 缩放。
- 外部气象网络 deny，M1 fake dispatcher/Task fixture 为唯一后台来源；不宣称 M4 Provider、CSV 或六阶段运行时存在。

## 执行顺序与门禁

实现完成后从仓库根目录依次执行，所有命令退出码必须为 0：

```powershell
python scripts/quality/check_governance.py
python -m unittest tests.governance.test_check_governance -v
python -m pytest tests/unit/conversation tests/unit/domain/test_process_coverage_and_area_tolerance.py tests/unit/web/test_conversation_i18n.py -q
python -m pytest tests/contracts/test_conversation_contract.py -q
python -m pytest tests/integration/test_answer_command.py tests/integration/test_conversation_authorization.py tests/integration/test_composer_draft_concurrency.py -q
python -m pytest tests/e2e/test_expert_conversation_workspace.py tests/e2e/test_task_dock_recovery.py tests/e2e/test_task_dock_layout.py tests/e2e/test_conversation_keyboard.py tests/e2e/test_composer_draft_recovery.py -q
python -m pytest tests/visual/test_conversation_four_theme_matrix.py tests/accessibility/test_conversation_workspace_a11y.py -q
git diff --check -- docs/specs/m2 docs/testing/plans/M2-test-plan.md
```

占位扫描的合格结果是无匹配（`rg` 因无匹配可返回 1，该结果本身不表示缺陷）。通过标准还包括：自然语言确认前业务写入数为 0；并发/幂等仅一次 commit；双 Tab 无重复消息/Task；深圳 HDI Tool Card、任务坞、API 与数据库 task id 一致；Task RUNNING 不阻断问答；刷新与重登恢复时间线、问题、草稿和任务坞；四主题组合无阻断级缺陷；required 可访问性断言全部通过。

## 失败分类

| 分类 | 判定 | 处理人 | 门禁行为 |
|---|---|---|---|
| 产品缺陷 | 状态机、持久化、权限、revision、Task 镜像或 UI 不变量违反批准规格 | M2 Implementer | 阻断合并，修复后全量重跑 |
| 测试缺陷 | 测试与规格不一致、非确定或错误依赖未实现能力 | M2 Test Owner | 修复测试并保留前后证据，不放宽产品断言 |
| Fixture 缺陷 | manifest、checksum、来源、独立验证或预期不一致 | Fixture Producer + Verifier | 阻断所有引用该 fixture 的结论 |
| 环境缺陷 | 浏览器、字体、容器、硬件或时钟不符合已记录基线 | Acceptance Agent | 记录证据并重建环境，不标记 pass |
| 专家确认缺口 | 仅领域规则来源/阈值尚未签认 | Domain Owner | 保持 `UNVERIFIED`，不得以软件测试冒充专家签认 |

## 结果与证据保留

每个 Test ID 保存原始 stdout/stderr、JUnit/Playwright 报告、必要的数据库断言快照、axe 结果和截图/trace；总索引目标为 `artifacts/acceptance/M2/index.json`，记录 commit SHA、环境摘要、命令、退出码、起止时间及证据 checksum。M2 Acceptance Record 只能引用当前 Candidate SHA 上实际存在且 checksum 匹配的证据，所有 required 用例通过后方可判定 GO。
