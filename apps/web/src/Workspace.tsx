/**
 * Engineering workspace: project creation + task dock.
 *
 * M2 minimal viable surface:
 * - New-project form: name + HDI template + geo fields + Asia/Shanghai
 *   -> calls POST /projects with an idempotency key derived from timestamp
 * - Task dock: polls GET /tasks every 3s, shows persisted weather task
 *   status (M1 returns DISPATCH_PENDING until M4 implements real dispatch)
 * - Sign-out button clears tokens and returns to login
 *
 * The conversation flow (8-stage SOP) and data-collection cards are M2
 * later work; this file pins the API integration and task-dock pattern.
 */

import { LogoutOutlined, ReloadOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Form, Input, Select, Space, Tag, Typography, message } from 'antd'
import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Conversation } from './Conversation'
import {
  ApiError,
  type ActorContext,
  type TaskEnvelope,
  clearTokens,
  createProject,
  listTasks,
  logout as apiLogout,
} from './api'

const { Title, Text } = Typography

// Fixed HDI template version id. M1 contract exposes templates via seed;
// for the front-end demo we use a constant. M2/P0_03 will fetch the list.
const HDI_TEMPLATE_VERSION_ID = 'demo-hdi-v1-0000-0000-0000-000000000001'

const STAGE_LABEL_KEY: Record<TaskEnvelope['status'], string> = {
  DISPATCH_PENDING: 'stageDispatch',
  QUEUED: 'stageQueued',
  RUNNING: 'stageRunning',
  SUCCEEDED: 'stageSucceeded',
  FAILED: 'stageFailed',
  CANCELLED: 'stageCancelled',
  STALE: 'stageStale',
}

const STAGE_TAG_COLOR: Record<TaskEnvelope['status'], string> = {
  DISPATCH_PENDING: 'gold',
  QUEUED: 'blue',
  RUNNING: 'processing',
  SUCCEEDED: 'green',
  FAILED: 'red',
  CANCELLED: 'default',
  STALE: 'default',
}

interface ProjectFormValues {
  name: string
  countryCode: string
  adminArea: string
  city: string
  timezone: string
}

interface WorkspaceProps {
  actor: ActorContext
  onSignOut: () => void
}

export function Workspace({ actor, onSignOut }: WorkspaceProps) {
  const { t } = useTranslation()
  const [form] = Form.useForm<ProjectFormValues>()
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [tasks, setTasks] = useState<TaskEnvelope[]>([])
  const [tasksLoading, setTasksLoading] = useState(false)
  const [lastCreatedTask, setLastCreatedTask] = useState<TaskEnvelope | null>(null)
  const [lastCreatedProjectId, setLastCreatedProjectId] = useState<string | null>(null)
  const [view, setView] = useState<'workspace' | 'conversation'>('workspace')

  const refreshTasks = useCallback(async () => {
    setTasksLoading(true)
    try {
      const result = await listTasks()
      setTasks(result.items)
      if (lastCreatedTask) {
        const updated = result.items.find((t) => t.task_id === lastCreatedTask.task_id)
        if (updated) setLastCreatedTask(updated)
      }
    } catch (error) {
      // Silently ignore list errors; surface in UI as empty.
      setTasks([])
    } finally {
      setTasksLoading(false)
    }
  }, [lastCreatedTask])

  // Poll every 3 seconds for task updates (M1 weather tasks stay
  // DISPATCH_PENDING; M4 will drive real progress).
  useEffect(() => {
    void refreshTasks()
    const interval = setInterval(() => void refreshTasks(), 3000)
    return () => clearInterval(interval)
  }, [refreshTasks])

  const handleCreate = async (values: ProjectFormValues) => {
    setCreating(true)
    setCreateError(null)
    try {
      const idempotencyKey = `web-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
      const result = await createProject(
        {
          name: values.name,
          templateVersionId: HDI_TEMPLATE_VERSION_ID,
          countryCode: values.countryCode.toUpperCase(),
          adminArea: values.adminArea,
          city: values.city,
          timezone: values.timezone,
        },
        idempotencyKey,
      )
      void message.success(t('createSucceeded'))
      setLastCreatedProjectId(result.project.id)
      setLastCreatedTask({
        task_id: result.weatherTaskId,
        status: 'DISPATCH_PENDING',
        progress: 0,
        stage: '',
        processed: 0,
        total: 0,
        error: null,
        retryable: false,
      })
      void refreshTasks()
      form.resetFields()
    } catch (error) {
      const msg = error instanceof ApiError ? `${t('createFailed')} (${error.envelope.code})` : t('createFailed')
      setCreateError(msg)
    } finally {
      setCreating(false)
    }
  }

  const handleSignOut = async () => {
    try {
      await apiLogout()
    } catch {
      // Even if server logout fails, clear local tokens.
    }
    clearTokens()
    onSignOut()
  }

  if (view === 'conversation') {
    return (
      <Conversation actor={actor} weatherTask={lastCreatedTask} projectId={lastCreatedProjectId} />
    )
  }

  return (
    <main className="page-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />
      <header className="topbar">
        <a className="brand" href="/" aria-label="PCB CDSO">
          <span className="brand-mark"><ThunderboltOutlined /></span>
          <span>PCB <strong>CDSO</strong></span>
        </a>
        <div className="toolbar">
          <Text type="secondary">
            {t('welcomeUser')}: {actor.actor_id.slice(0, 8)} · {actor.role}
          </Text>
          <Button type="primary" onClick={() => setView('conversation')}>
            {t('workspaceTitle')}
          </Button>
          <Button type="text" aria-label={t('logout')} icon={<LogoutOutlined />} onClick={() => void handleSignOut()}>
            {t('logout')}
          </Button>
        </div>
      </header>

      <section className="content-grid">
        <div className="product-story">
          <Title level={3}>{t('workspaceTitle')}</Title>
          <Card title={t('newProject')} bordered>
            <Form
              form={form}
              layout="vertical"
              requiredMark={false}
              onFinish={(values) => void handleCreate(values)}
              initialValues={{
                countryCode: 'CN',
                timezone: 'Asia/Shanghai',
              }}
            >
              <Form.Item name="name" label={t('projectName')} rules={[{ required: true, min: 1, max: 120 }]}>
                <Input placeholder="深圳 HDI 工厂" />
              </Form.Item>
              <Space style={{ display: 'flex' }} size="middle">
                <Form.Item name="countryCode" label={t('projectCountry')} rules={[{ required: true, pattern: /^[A-Za-z]{2}$/ }]}>
                  <Input maxLength={2} style={{ width: 90 }} />
                </Form.Item>
                <Form.Item name="adminArea" label={t('projectAdminArea')} rules={[{ required: true }]} style={{ flex: 1 }}>
                  <Input />
                </Form.Item>
              </Space>
              <Space style={{ display: 'flex' }} size="middle">
                <Form.Item name="city" label={t('projectCity')} rules={[{ required: true }]} style={{ flex: 1 }}>
                  <Input />
                </Form.Item>
                <Form.Item name="timezone" label={t('projectTimezone')} rules={[{ required: true }]}>
                  <Select
                    style={{ width: 220 }}
                    options={[
                      { value: 'Asia/Shanghai', label: 'Asia/Shanghai' },
                      { value: 'Asia/Hong_Kong', label: 'Asia/Hong_Kong' },
                      { value: 'Asia/Tokyo', label: 'Asia/Tokyo' },
                      { value: 'America/Los_Angeles', label: 'America/Los_Angeles' },
                      { value: 'Europe/Berlin', label: 'Europe/Berlin' },
                    ]}
                  />
                </Form.Item>
              </Space>
              {createError && <Alert type="error" title={createError} showIcon style={{ marginBottom: 12 }} />}
              <Button type="primary" htmlType="submit" loading={creating} aria-label={t('create')} block>
                {creating ? t('creating') : t('create')}
              </Button>
            </Form>
          </Card>
        </div>

        <section className="login-card" aria-labelledby="task-dock-title">
          <div className="status"><span />{t('authEnabled')}</div>
          <h2 id="task-dock-title">{t('taskDock')}</h2>
          <Space style={{ marginBottom: 12, width: '100%', justifyContent: 'space-between' }}>
            <Text type="secondary">{tasks.length > 0 ? `${tasks.length}` : t('noTasks')}</Text>
            <Button
              size="small"
              icon={<ReloadOutlined />}
              onClick={() => void refreshTasks()}
              loading={tasksLoading}
              aria-label={t('refresh')}
            >
              {t('refresh')}
            </Button>
          </Space>
          <div role="list" aria-live="polite">
            {lastCreatedTask && (
              <Card key={lastCreatedTask.task_id} size="small" style={{ marginBottom: 8 }} role="listitem">
                <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                  <Text code>{lastCreatedTask.task_id.slice(0, 13)}</Text>
                  <Tag color={STAGE_TAG_COLOR[lastCreatedTask.status]}>
                    {t(STAGE_LABEL_KEY[lastCreatedTask.status])}
                  </Tag>
                </Space>
                <div style={{ marginTop: 6 }}>
                  <Text type="secondary">{t('weatherTask')}</Text>
                </div>
              </Card>
            )}
            {tasks
              .filter((t) => !lastCreatedTask || t.task_id !== lastCreatedTask.task_id)
              .map((task) => (
                <Card key={task.task_id} size="small" style={{ marginBottom: 8 }} role="listitem">
                  <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                    <Text code>{task.task_id.slice(0, 13)}</Text>
                    <Tag color={STAGE_TAG_COLOR[task.status]}>{t(STAGE_LABEL_KEY[task.status])}</Tag>
                  </Space>
                </Card>
              ))}
          </div>
        </section>
      </section>
      <footer>PCB CDSO · Preview 0.6 · M2 workspace</footer>
    </main>
  )
}
