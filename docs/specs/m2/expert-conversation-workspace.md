# M2 专家对话工作台 Feature Spec

| 属性 | 值 |
|---|---|
| 状态 | approved |
| 版本 | 1.0.0 |
| Owner | Domain + Web + API |
| Milestone | M2 |
| Issue | PRD v0.6 rebaseline Task 4 |
| PRD 追踪 | P0_04；P0_05/P0_06 交互依赖；P0_07 跨里程碑依赖；3.3、4.1、4.2、5.2、7 |

## 用户结果

工程师在一个可恢复的类 Codex 桌面对话工作台中完成八阶段受控采集；所有计算字段只有在结构化确认、校验和 revision 检查成功后才原子写入，后台任务不阻断继续问答。

## 范围与非目标

### 包含

- 连续消息时间线、固定底部 Composer、结构化确认卡、系统校验卡和工具执行卡。
- 八阶段导航、首个未完成问题定位、右侧固定 PCB 工艺链和阶段门禁反馈。
- 消息、卡片、阶段游标、未完成问题、Composer 草稿和用户界面偏好的持久化与恢复。
- 由持久化 `GET /tasks` 数据驱动的对话 Tool Card 与右下角全局任务坞。
- revision、一次性 impact token、阻断、警告确认、冲突、权限、轮询失效和错误恢复。
- `zh-CN` / `en-US`、明/暗主题、键盘和桌面可访问性。

### 不包含

- 传统自由表单、Excel 导入、2D 画布、任意流程 DSL 和设备级 PCW 推导。
- 真实气象 Provider、六阶段下载实现、CSV 解析、气象批次 current 发布；这些由 M4 拥有。
- Task 生命周期的创建或权威状态管理。M1 创建首轮持久化 Task；后续里程碑执行 Task。
- 静态计算、历史仿真、预测算法和结果图表。

## 领域词汇与不变量

### 四类持久化消息

消息时间线只允许以下四个 `messageType`；卡片是消息的结构化呈现，不增加第五类消息。

| `messageType` | 语义 | 允许载荷 | 禁止行为 |
|---|---|---|---|
| `AGENT_PROMPT` | 当前问题、帮助、示例或下一步说明 | `questionKey`、字段路径、阶段、选项引用 | 写业务字段或伪造用户确认 |
| `USER_DRAFT` | 用户原始回答及结构化候选值的持久化审计记录 | 原始显示值、结构化候选值、来源、基于 revision、关联确认卡 id | 未经确认直接成为计算输入；确认后删除或改写原始回答 |
| `CONFIRMATION_CARD` | 候选答案、系统校验和提交结果的结构化卡片 | `presentationState`、规范化值、单位、影响、错误 key、确认 token | 将校验状态编码成另一种消息类型 |
| `TOOL_CARD` | 按 `taskId` 对持久化 Task 的镜像 | task id、名称、阶段、状态、进度、错误、恢复能力 | 拥有、推测或推进 Task 状态 |

所有消息和卡片都具有稳定 `messageId`、`conversationId`、`projectId`、`inputRevision`、创建时间和排序游标。重放使用稳定 id 去重；同一消息不得因刷新、轮询或双 Tab 重复出现。`USER_DRAFT` 在确认前后都保留为不可变审计记录：确认卡和最终审计通过关联 id 指向它，确认不会把它改名为另一种消息或用规范化值覆盖原始回答。

`CONFIRMATION_CARD.presentationState` 的封闭枚举为 `PENDING`、`VALIDATING`、`BLOCKED`、`WARNING_CONFIRMATION`、`COMMITTED`、`REVISION_CONFLICT`。系统校验结果全部由该字段及卡片载荷表达；这些状态不是新的 `messageType`。`TOOL_CARD` 以 `taskId` 关联后端 Task，并只显示后端持久化事实。

### 唯一业务写入路径

下图混合表示消息节点与确认卡 `presentationState` 的生命周期，不定义额外 `messageType`：

```text
AGENT_PROMPT -> USER_DRAFT -> CONFIRMATION_CARD -> VALIDATING
VALIDATING -> COMMITTED | BLOCKED | WARNING_CONFIRMATION | REVISION_CONFLICT
WARNING_CONFIRMATION -> VALIDATING
REVISION_CONFLICT -> USER_DRAFT
BLOCKED -> USER_DRAFT
```

- `USER_DRAFT` 可来自自然语言解析或结构化控件，但只保存草稿/候选答案，不写计算字段业务表。
- `CONFIRMATION_CARD` 必须展示规范化值、SI 存储单位、字段来源、校验摘要和影响；首次确认请求携带 `expectedInputRevision`、一次性 `impactToken` 和幂等键。服务端收到首次确认即在同一事务原子消费 `impactToken`，无论结果是提交、阻断还是警告都不能再次使用。
- `VALIDATING` 在服务端重新执行字段类型、单位、条件必填、范围、工艺覆盖、权限、token 和 revision 校验。
- `COMMITTED` 是唯一允许原子写入答案、审计、revision 及失效标记的终态；相同幂等键与相同 canonical payload 重放返回原结果。
- `BLOCKED` 与 `REVISION_CONFLICT` 零业务字段写入。首次确认若返回 `WARNING_CONFIRMATION`，服务端原子消费 `impactToken` 并签发 `warningChallengeId`；challenge 绑定 `actorId`、`projectId`、`questionKey`、canonical payload、`inputRevision`、warning codes 和 expiry，但不绑定尚未提交的 reason。
- 用户通过明确的 `SubmitWarningReasons` command/端点向 `warningChallengeId` 提交每个 warning code 对应的非空 reason。服务端校验 challenge 绑定、revision、expiry、warning code 集合和 reason 文本；reason 文本可使用 `zh-CN` 或 `en-US`，但请求中的 code 必须是稳定双语资源 code，不能提交显示文案代替 code。校验成功时原子生成绑定上述 challenge 全部字段及规范化 reasons 的一次性 `warningConfirmationToken`。
- 最终确认只接受 `warningConfirmationToken`，并在同一事务原子消费后进入 `VALIDATING`，成功才 `COMMITTED`。确认 command 必须先查幂等记录：同一幂等键与相同 canonical request hash 返回原响应（包括服务端已完成但网络响应丢失的重放）；同一键不同 hash 返回 `409 IDEMPOTENCY_CONFLICT`；仅在没有匹配幂等记录时，不同键复用已消费 token 才返回 `409 TOKEN_ALREADY_USED`。绑定 revision 已变化返回 `409 REVISION_CONFLICT`，所有冲突均零业务写入。
- 自然语言可以产生 `USER_DRAFT` 和解释，但不存在自然语言直写计算字段的端点、旁路或管理员开关。

### 八阶段与工艺链

阶段编码及顺序固定为：`PROJECT_TEMPLATE`、`GEOGRAPHY_WEATHER`、`BUILDING_FLOOR`、`AREA_PROCESS`、`PROCESS_ENVIRONMENT`、`COOLING_INPUT`、`SCHEDULE_STORAGE`、`REVIEW`。消息和阶段游标即时保存；恢复时定位第一个未完成且当前可见的问题。已完成阶段可回看；修改已提交答案必须先展示影响分析并走同一确认路径。

首轮产品确认后，右侧固定工艺链按项目不可变模板快照呈现，并驱动区域覆盖、环境问题、生产负荷计划和结果聚合。工艺链在八阶段导航和消息滚动时保持可见；不得允许先自由建区再补工艺。主要工序缺失为 `BLOCKED`，区域唯一绑定和面积容差遵循 M2 Milestone：0–3% 为需原因警告，超过 3% 阻断。

### Task 镜像不变量

`TOOL_CARD` 和任务坞只消费 `GET /tasks/{taskId}` 或 `GET /tasks?projectId=&activeOnly=` 返回的持久化 Task。二者必须显示与 M1 `POST /projects` 响应相同的 task id、状态、阶段和颜色语义；前端缓存、广播消息或动画不得成为状态权威。`TOOL_CARD` 不创建 Task、不执行状态转换，也不拥有重试结果。

## 正常流程

1. 打开项目时，客户端按服务端排序游标恢复八阶段状态、消息/卡片、首个未完成问题和保存的 Composer 草稿；同时查询当前用户可见的持久化 Task。
2. `AGENT_PROMPT` 呈现当前字段的双语问题、帮助、示例、选项和单位；右侧显示固定工艺链及覆盖状态。
3. 用户通过自然语言或结构化控件形成 `USER_DRAFT`。Composer 使用 `Ctrl/Cmd+Enter` 提交候选答案，未通过客户端基础校验时不发请求。
4. 服务端解析候选答案并返回 `presentationState=PENDING` 的 `CONFIRMATION_CARD`；此时业务计算字段保持不变，原 `USER_DRAFT` 已作为原始回答审计记录保存。
5. 用户确认后进入 `VALIDATING`。成功时原子提交答案、审计、`inputRevision + 1` 和受影响结果的分域失效标记，时间线追加或更新 `messageType=CONFIRMATION_CARD, presentationState=COMMITTED` 的卡片并进入下一问题；不得创建第五种系统消息。
6. 若有可放行警告，首次 `impactToken` 已消费，卡片进入 `WARNING_CONFIRMATION` 并获得未绑定原因的 `warningChallengeId`；用户提交非空 reasons 后服务端原子签发 reason-bound `warningConfirmationToken`，最终确认以该 token 提交。硬规则失败进入 `BLOCKED`。
7. 首轮项目/地理确认返回 `weatherTaskId` 后，时间线插入同 id 的 `TOOL_CARD`，任务坞在 2 秒可见目标内显示该持久化 Task；任务处于 `RUNNING` 时 Composer 和下一道建筑问题仍可操作。
8. 离开页面、切换浏览器 Tab、刷新或重新登录后，客户端重新读取服务端状态；不得创建新 Task、重复消息或重置进度。

## 持久化、恢复与同步

- 服务端持久化消息、结构化卡片载荷、阶段完成状态、问题游标、答案 revision、警告原因、审计和关联 task id。客户端仅持有可丢弃缓存。
- 每个浏览器 Tab 首次打开会话时生成 `draftId` 并写入该 Tab 的 `sessionStorage`，刷新复用该 id，Tab 关闭后浏览器可丢弃本地 id；新 Tab 必须生成不同 id。Composer 草稿键为 `draftId + actorId + projectId + conversationId + questionKey`，包含文本/结构化控件值、canonical payload、base answer revision 和单调 `draftVersion`。每次 autosave 携带期望 `draftVersion` 并以 CAS 更新。
- 服务端恢复响应返回当前 `actorId + projectId + conversationId + questionKey` 的 draft collection；每项至少含 `draftId`、`draftVersion`、`updatedAt`、安全 `preview` 和 `sourceDevice`。刷新时匹配 `sessionStorage.draftId` 并恢复该项。重登或换设备没有本地 id 时，collection 恰一项则自动恢复；多项则按 `updatedAt desc, draftId asc` 确定性展示并要求用户明确选择、合并或丢弃，禁止静默选择。新 Tab 生成新 id，同时能发现并提示其他已有草稿。
- autosave CAS 冲突返回 `409 DRAFT_CONFLICT`，服务端保留提交版本与当前版本，界面展示两版本并要求用户选择保留、合并或另存；禁止静默 last-write-wins。迟到 autosave 不得覆盖较新版本。
- `COMMITTED` 只可条件清除与本次 `questionKey + canonical payload + base draftVersion` 匹配的同 `draftId` 草稿。另一 Tab 的不同 `draftId`、已更新版本或迟到保存内容不得被清除；clear 本身也使用 CAS，迟到 clear 为无操作或冲突而非删除新版本。
- 恢复响应必须以一个一致的服务端快照给出时间线排序游标、阶段状态、首个未完成问题和草稿版本，避免消息恢复后问题游标倒退。
- 多 Tab 使用持久化 revision 和稳定消息 id 收敛。可使用 BroadcastChannel 提示刷新，但仍以服务端响应为准；同一确认幂等重放不产生重复提交、消息或 Task。
- Task 响应必须携带单调 `version`；若既有契约只能提供 `updatedAt`，则以 `updatedAt + statusRank` 构成严格可比较版本，终态 rank 高于任何活动态。客户端对每个 project 串行发起轮询，或为请求分配递增 sequence 并丢弃迟到响应；任何较旧响应和 `RUNNING` 都不得覆盖已观察到的终态。
- Task 活跃时轮询 `GET /tasks`；建议活动态 2 秒、后台 Tab 退避但不超过 10 秒，恢复前台立即查询。若 `activeOnly=true` 响应中一个已知活动 task id 消失，客户端以 `GET /tasks/{taskId}` 补查并按以下封闭分支处理：`200` 活动态保留 last-known 并在下一轮按退避继续；`200` 终态缓存 5 秒；`401` 停止该用户全部 Task 轮询并在登录成功后恢复；`404` 立即移除镜像且不推断终态；网络错误保留 last-known、显示陈旧标记并指数退避。退避必须有实现冻结的最大间隔，到达上限后继续以该间隔重试，不得假定成功或失败。
- `401` 停止轮询并在重新认证后恢复；Task 单项查询继承 M1 scoped lookup，跨 owner 的存在 id 与随机不存在 id 都返回不可区分的 `404`，列表始终 `200` 且过滤不可见项；写接口越权返回 `403`。网络失败保留最后已确认状态并显示陈旧标记，禁止将本地超时推断为 Task 失败。
- Task 进入终态后停止活动轮询；`SUCCEEDED` 在任务坞缓存 5 秒后进入最近任务，`FAILED` 持续显示服务端允许的恢复动作。取消、重试和 CSV 能力只按 Task 响应声明显示；M2 不实现 M4 的 CSV 行为。

## 布局、主题与可访问性

- 桌面主区由左侧八阶段导航、中间连续消息流/底部 Composer、右侧固定工艺链组成。Composer 发送按钮和当前确认卡始终可见、可点击。
- 全局任务坞固定在视口右下角，展开宽度 `360px`，最多展示 3 个活动任务摘要；更多任务通过数量和综合进度表达。折叠态为带数量的悬浮入口。
- `/` 仅在焦点不位于输入框、文本域、可编辑控件或输入法组合会话时聚焦 Composer；快捷键事件不得向 Composer 插入 `/`。已有输入控件焦点和输入法 composition 期间不抢焦点、不发送。
- `Ctrl/Cmd+Enter` 发送当前候选答案；输入法 composition 期间不得发送，组合结束后需新的快捷键事件才发送。
- `Alt+↑` 导航到最近一个已完成阶段；`Alt+↓` 导航到下一个已解锁阶段。不存在目标时保持当前阶段。两种阶段导航都必须先保存并保留当前未提交 Composer 草稿，返回该阶段时内容和目标问题不变。
- `Ctrl/Cmd+J` 展开或折叠任务坞且不抢占 Composer 或其他已有输入控件焦点。所有操作均有键盘等价路径，焦点顺序、可见焦点、Escape 关闭和关闭后的焦点归还可预测。
- 任务坞通过避让/重排保证不遮挡 Composer 发送按钮和当前确认卡；在最低支持桌面视口及 200% 缩放下仍成立。
- Agent、用户、系统校验、工具执行不仅靠颜色区分，必须同时使用文本标签/图标/状态文案；进度具有可访问名称和值，动态更新使用非打断式 live region，阻断错误与字段关联。
- `zh-CN` / `en-US` 的问题、选项、帮助、示例、错误和 aria 文案都来自资源 key；缺 key 阻断构建。中/英 × 明/暗四种组合使用同一组件和设计令牌，英文最长文案不造成关键控件跳位，主题/语言偏好保存到账户并在重登恢复。
- 视觉门禁固定 Chromium、DPR 1、`1440x900` 标准桌面与 `1280x720` 最低桌面；批准字体必须完成加载、动画/过渡/光标闪烁关闭。截图区域固定为整个应用视口，并另截 Composer 发送区、当前确认卡和展开任务坞；动态 Task 时间戳与进度数值使用固定 mask。四种语言/主题组合在两个视口均要求 pixel diff `<=0.2%` 且关键控件 bounding box 相对 golden 偏移 `<=2px`。

## 失败与恢复

| 触发 | 状态/错误 | 用户提示语义 | 业务字段写入 | 恢复动作 |
|---|---|---|---|---|
| 自然语言无法解析 | `422 VALIDATION_FAILED` / `BLOCKED` | 指明字段、允许格式和单位 | 否 | 保留草稿，改用结构化控件或修订文本 |
| 强规则或主要工序覆盖失败 | `422 VALIDATION_FAILED` / `BLOCKED` | 展示规则来源与缺失项 | 否 | 修订草稿后重新确认 |
| 可放行经验规则超限 | `WARNING_CONFIRMATION` | 展示来源、风险及原因必填 | 否 | 填写原因并显式再次确认 |
| 任一确认 token 已消费 | `409 TOKEN_ALREADY_USED` | 确认已处理 | 否 | 读取最新卡片，不重放写入 |
| 任一确认 token 已过期 | `409 TOKEN_EXPIRED` | 确认已过期 | 否 | 重新生成影响分析和确认卡 |
| token 绑定 revision 已变化 | `409 REVISION_CONFLICT` | 影响分析已失效 | 否 | 拉取最新 revision，重新生成确认卡 |
| 草稿 CAS 失败 | `409 DRAFT_CONFLICT` | 草稿有并发版本 | 否 | 同时展示两版本，由用户选择保留、合并或另存 |
| 另一 Tab 已提交 | `409 REVISION_CONFLICT` | 当前答案基于旧 revision | 否 | 恢复最新时间线，将未提交内容保留为新草稿 |
| 写接口无项目访问权 | `403 FORBIDDEN` | 无权执行操作 | 否 | 停止写入，返回有权页面；不泄露他人数据 |
| Task 单项 GET 跨 owner 或不存在 | 相同 `404` | 资源不可用 | 否 | 从镜像移除；两类 id 的外部响应与日志不可区分 |
| Task 查询暂时失败 | 陈旧镜像状态 | 进度暂不可更新 | 否 | 指数退避并手动重试，恢复后按同 task id 收敛 |
| 会话过期 | `401` | 需要重新登录 | 否 | 登录后恢复消息、草稿、阶段和任务坞 |
| 恢复快照不完整/游标失效 | `409` 或重新取全量快照 | 正在重新同步 | 否 | 丢弃可替代缓存，按服务端全量快照恢复 |

## API、数据与版本

- 本规格冻结行为，不声称运行时端点或 schema 已存在。实现前须按契约优先流程批准 OpenAPI、Schema 和迁移。
- 对话读取需要返回一致快照：conversation、四类消息、卡片载荷、八阶段状态、首个未完成问题、Composer 草稿和当前 `inputRevision`。
- 草稿保存不得写计算字段；草稿接口接收稳定 `draftId`、scope key、期望 `draftVersion` 和内容，以 CAS 返回新版本或 `409 DRAFT_CONFLICT`，读取接口返回 scope 内 draft collection。首次确认接口接收 `expectedInputRevision`、一次性 `impactToken`、canonical answer 和幂等键；警告响应返回 `warningChallengeId`，原因 command 验证非空 reason/稳定双语 code 后签发 reason-bound `warningConfirmationToken`，最终确认消费该 token。统一错误体包含 `code`、`message_key`、`field_path`、`details`、`request_id`。
- Task 镜像复用 M1 已冻结的 `GET /tasks/{taskId}` 与 `GET /tasks?projectId=&activeOnly=`，不建立第二套前端任务状态库。
- 每次 `COMMITTED` 生成不可变审计记录，记录 actor、字段路径、旧/新规范化值、单位、规则版本、来源、警告原因、前后 revision 和 request id；不得记录 token、凭据或不必要的自然语言敏感内容。
- 结果失效按 `static`、`historical`、`forecast` 分域记录。仅影响相应域，不得笼统伪造“全部有效”或由前端自行清除失效。

## 可观察性

- 指标：草稿保存/恢复成功率、确认结果分布、revision 冲突数、消息去重数、恢复耗时、Task 轮询延迟/错误率、任务坞可见耗时。
- 日志关联：`request_id`、`actorId`、`projectId`、`conversationId`、`messageId`、`taskId`、前后 revision；权限失败日志不得泄露资源内容。
- 恢复性能：300 区域项目从打开到首个未完成问题可操作目标 `<=2.0s`，超过 `4.0s` 为验收失败；首轮 Task 同 id 可见目标 `<=2.0s`。

## 验收场景

1. **深圳 HDI 同 task id：** Given 工程师确认深圳 HDI 项目，When M1 返回持久化 `weatherTaskId`，Then 2 秒内 Tool Card 与任务坞显示完全相同的 task id，且均可由 `GET /tasks` 查询。
2. **任务不阻断问答：** Given 气象 Task 为 `RUNNING`，When 工程师继续回答建筑/楼层问题，Then Composer 可用、答案仍走确认路径，Task 无重复或状态倒退。
3. **完整恢复：** Given 时间线、首个未完成问题、未提交 Composer 草稿和活动 Task，When 刷新或重新登录，Then四者从服务端恢复，排序、revision 和 task id 不变。
4. **双 Tab 收敛：** Given 两个 Tab 打开同一 revision，When Tab A 提交后 Tab B 用旧 revision 确认，Then B 得到 `409 REVISION_CONFLICT`、零部分写入、草稿保留；两 Tab 均无重复消息或 Task。
5. **自然语言隔离：** Given 用户自然语言回答面积，When 解析成功但未确认，Then 只出现 Confirmation Card，计算字段业务表保持原值。
6. **工艺覆盖与警告：** Given HDI 固定工艺链，When 遗漏填孔电镀区域或面积超 3%，Then 阻断；偏差 2% 且填写原因并确认后才允许提交。
7. **权限与重登：** Given工程师失去项目权限或会话过期，When 轮询/写入发生，Then 数据不泄露、不写入；合法重新认证后仅恢复仍有权资源。
8. **四主题组合：** Given 中/英与明/暗四组合，When 完成主流程与任务错误恢复，Then 无缺 key、文本截断、仅颜色状态或关键控件位移。
9. **键盘与缩放：** Given 键盘用户和 200% 缩放，When 使用 `/`、`Ctrl/Cmd+Enter`、`Alt+↑`、`Alt+↓`、`Ctrl/Cmd+J` 操作 Composer、阶段与任务坞，Then 焦点/输入法边界正确、阶段导航保留草稿、焦点可见且任务坞不遮挡提交操作。

## 测试映射

| 验收条件 | 测试层级 | 计划测试文件/fixture | 门禁 |
|---|---|---|---|
| 唯一写路径、状态转换、警告和冲突 | unit / property | `tests/unit/conversation/test_answer_state_machine.py` | required |
| 四个 messageType、确认卡状态映射、409/422、幂等 | contract | `tests/contracts/test_conversation_contract.py` | required |
| 原子写入、审计、revision、分域失效 | integration | `tests/integration/test_answer_command.py` | required |
| 恢复、双 Tab、任务镜像、四主题、键盘 | e2e / accessibility / visual | `tests/e2e/test_expert_conversation_workspace.py` | required |
| 双语资源完整性 | unit / i18n | `tests/unit/web/test_conversation_i18n.py` | required |

## 阻断审批的问题

无。
