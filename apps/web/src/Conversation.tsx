/**
 * M2 conversation workspace skeleton (A-industrial style, mock data).
 *
 * Three-column Codex-like layout per doc/对话设计原型/prototypes/A-industrial:
 * - Left rail: 8-stage navigation with completion state
 * - Center: message timeline (AGENT_PROMPT / USER_DRAFT / CONFIRMATION_CARD /
 *   TOOL_CARD) + bottom Composer
 * - Right: fixed HDI process chain (appears after stage 1 confirms HDI)
 *
 * Mock data only; M2 backend will drive real persistence. This skeleton
 * proves the visual contract and interaction model so the backend can be
 * built against a stable front-end shape.
 */

import {
  CheckCircleFilled,
  ClockCircleOutlined,
  LoadingOutlined,
  PlayCircleOutlined,
  SendOutlined,
  WarningFilled,
} from '@ant-design/icons'
import { Input, Tag, Tooltip, Typography } from 'antd'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { ActorContext, TaskEnvelope } from './api'
import { HDI_PROCESS_CHAIN, STAGES } from './conversationMock'
import './conversation.css'

const { Text } = Typography

interface ConversationProps {
  actor: ActorContext
  weatherTask: TaskEnvelope | null
}

const STAGE_STATUS = ['done', 'done', 'done', 'active', 'todo', 'todo', 'todo', 'todo'] as const

export function Conversation({ actor, weatherTask }: ConversationProps) {
  const { t, i18n } = useTranslation()
  const isZh = i18n.language === 'zh-CN'
  const [composer, setComposer] = useState('')

  return (
    <main className="conv-app" data-theme="dark">
      <header className="conv-top">
        <div className="conv-brand">
          <span className="conv-brand-mark" />
          <span>PCB <strong>CDSO</strong></span>
          <small>{isZh ? '深圳 HDI 工厂 · 采集' : 'Shenzhen HDI · Collection'}</small>
        </div>
        <div className="conv-spacer" />
        <span className="conv-actor">
          {actor.role} · {actor.actor_id.slice(0, 8)}
        </span>
      </header>

      <div className="conv-layout">
        {/* Left rail: 8 stages */}
        <aside className="conv-rail">
          <div className="conv-rail-title">{isZh ? '采集阶段' : 'Stages'}</div>
          <ol className="conv-stages">
            {STAGES.map((stage, idx) => {
              const status = STAGE_STATUS[idx]
              return (
                <li key={stage.id} className={`conv-stage conv-stage-${status}`}>
                  <span className="conv-stage-num">
                    {status === 'done' ? (
                      <CheckCircleFilled style={{ color: '#3dd6c6' }} />
                    ) : status === 'active' ? (
                      <LoadingOutlined style={{ color: '#f0b429' }} />
                    ) : (
                      <span className="conv-stage-dot">{stage.id}</span>
                    )}
                  </span>
                  <span className="conv-stage-label">{isZh ? stage.titleZh : stage.titleEn}</span>
                </li>
              )
            })}
          </ol>
        </aside>

        {/* Center: timeline + composer */}
        <section className="conv-main">
          <div className="conv-timeline">
            {/* Stage 1: AGENT_PROMPT */}
            <article className="conv-msg conv-msg-agent">
              <div className="conv-msg-avatar">A</div>
              <div className="conv-msg-body">
                <div className="conv-msg-meta">
                  <span>Agent</span>
                  <span className="conv-msg-stage">阶段 1 · 产品/模板</span>
                </div>
                <div className="conv-msg-text">
                  {isZh
                    ? '欢迎。本系统以 PCB 产品工艺为起点。请选择产品类型。'
                    : 'Welcome. This system starts from PCB product process. Select a product type.'}
                </div>
                <div className="conv-chips">
                  <span className="conv-chip conv-chip-active">HDI 多层板</span>
                  <span className="conv-chip">普通多层板</span>
                  <span className="conv-chip">IC 载板</span>
                </div>
              </div>
            </article>

            {/* Stage 1: USER_DRAFT */}
            <article className="conv-msg conv-msg-user">
              <div className="conv-msg-avatar">U</div>
              <div className="conv-msg-body">
                <div className="conv-msg-meta">
                  <span>{isZh ? '用户草稿' : 'User draft'}</span>
                </div>
                <div className="conv-msg-text">HDI 多层板</div>
              </div>
            </article>

            {/* Stage 1: CONFIRMATION_CARD (COMMITTED) */}
            <article className="conv-card">
              <header className="conv-card-head">
                <span className="conv-card-title">{isZh ? '确认卡 · 产品' : 'Confirmation · Product'}</span>
                <Tag color="green">COMMITTED</Tag>
              </header>
              <div className="conv-card-row">
                <span>{isZh ? '产品模板' : 'Template'}</span>
                <strong>HDI v1.0.0</strong>
              </div>
              <div className="conv-card-row">
                <span>{isZh ? '国家' : 'Country'}</span>
                <strong>CN</strong>
              </div>
              <div className="conv-card-row">
                <span>{isZh ? '城市' : 'City'}</span>
                <strong>{isZh ? '广东省 深圳市' : 'Shenzhen, Guangdong'}</strong>
              </div>
              <div className="conv-card-row">
                <span>{isZh ? '时区' : 'Timezone'}</span>
                <strong>Asia/Shanghai</strong>
              </div>
              <div className="conv-card-foot">
                <span>inputRevision: 1</span>
                <span>impactToken: consumed</span>
              </div>
            </article>

            {/* Stage 2: TOOL_CARD (weather task) */}
            {weatherTask && (
              <article className="conv-card conv-card-tool">
                <header className="conv-card-head">
                  <span className="conv-card-title">
                    <PlayCircleOutlined /> {isZh ? '气象任务' : 'Weather task'}
                  </span>
                  <Tag color={weatherTask.status === 'DISPATCH_PENDING' ? 'gold' : 'blue'}>
                    {weatherTask.status}
                  </Tag>
                </header>
                <div className="conv-card-row">
                  <span>taskId</span>
                  <code>{weatherTask.task_id.slice(0, 13)}</code>
                </div>
                <div className="conv-card-row">
                  <span>{isZh ? '阶段' : 'Stage'}</span>
                  <strong>{isZh ? '等待调度' : 'Awaiting dispatch'}</strong>
                </div>
                <div className="conv-card-foot">
                  <span>{isZh ? 'M1 已派发，M4 落地真实 Provider' : 'M1 dispatched; M4 implements real provider'}</span>
                </div>
              </article>
            )}

            {/* Stage 4: AGENT_PROMPT (active) */}
            <article className="conv-msg conv-msg-agent">
              <div className="conv-msg-avatar">A</div>
              <div className="conv-msg-body">
                <div className="conv-msg-meta">
                  <span>Agent</span>
                  <span className="conv-msg-stage">阶段 4 · 区域/工序</span>
                </div>
                <div className="conv-msg-text">
                  {isZh
                    ? '为每道主要工序建立功能区域。当前未覆盖：钻孔填孔。请补齐该工序区域。'
                    : 'Bind each major process to a zone. Uncovered: Drill & Fill. Add a zone for it.'}
                </div>
              </div>
            </article>
          </div>

          {/* Composer */}
          <div className="conv-composer">
            <Input.TextArea
              value={composer}
              onChange={(e) => setComposer(e.target.value)}
              placeholder={isZh ? '输入回答，或选择上方候选…' : 'Type an answer, or pick a chip above…'}
              autoSize={{ minRows: 1, maxRows: 4 }}
              variant="borderless"
              aria-label={isZh ? '回答输入框' : 'Answer composer'}
            />
            <button
              className="conv-send"
              aria-label={isZh ? '发送' : 'Send'}
              disabled={!composer.trim()}
              onClick={() => {
                /* mock: no-op until backend conversation API */
                setComposer('')
              }}
            >
              <SendOutlined />
            </button>
          </div>
        </section>

        {/* Right: HDI process chain */}
        <aside className="conv-side">
          <div className="conv-side-title">
            {isZh ? 'HDI 工艺链' : 'HDI process chain'}
          </div>
          <ul className="conv-process">
            {HDI_PROCESS_CHAIN.map((p) => (
              <li key={p.code} className={`conv-process-item ${p.major ? 'conv-process-major' : ''}`}>
                <span className="conv-process-name">{isZh ? p.nameZh : p.nameEn}</span>
                {p.major && (
                  <Tooltip title={isZh ? '主要工序，必须全覆盖' : 'Major process; full coverage required'}>
                    <Tag color="cyan" bordered={false} style={{ marginInlineStart: 'auto', fontSize: 10 }}>
                      {isZh ? '主要' : 'major'}
                    </Tag>
                  </Tooltip>
                )}
              </li>
            ))}
          </ul>
          <div className="conv-side-foot">
            <Text type="secondary" style={{ color: '#8b9bb0', fontSize: 11 }}>
              {isZh
                ? '主要工序 6/6 已覆盖；1 个区域待补齐'
                : 'Major 6/6 covered; 1 zone pending'}
            </Text>
          </div>
        </aside>
      </div>
    </main>
  )
}
