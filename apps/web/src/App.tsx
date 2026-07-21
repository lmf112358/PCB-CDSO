import { BulbOutlined, GlobalOutlined, LockOutlined, MailOutlined, MoonOutlined, SunOutlined } from '@ant-design/icons'
import { Alert, Button, ConfigProvider, Form, Input, Tag, theme as antdTheme } from 'antd'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { ApiError, type ActorContext, getAccessToken, login } from './api'
import { LOCALE_STORAGE_KEY } from './i18n'
import { applyTheme, initialTheme, type ThemeMode } from './theme'
import { Workspace } from './Workspace'
import './styles.css'

const signals = [
  ['processDriven', 'processDrivenDetail'],
  ['simulation', 'simulationDetail'],
  ['traceable', 'traceableDetail'],
] as const

interface LoginValues {
  email: string
  password: string
}

export function App() {
  const { t, i18n } = useTranslation()
  const [mode, setMode] = useState<ThemeMode>(() => {
    const selected = initialTheme()
    applyTheme(selected)
    return selected
  })
  const [actor, setActor] = useState<ActorContext | null>(null)
  const [signingIn, setSigningIn] = useState(false)
  const [loginError, setLoginError] = useState<string | null>(null)
  const [form] = Form.useForm<LoginValues>()

  const toggleLanguage = async () => {
    const nextLocale = i18n.language === 'en-US' ? 'zh-CN' : 'en-US'
    localStorage.setItem(LOCALE_STORAGE_KEY, nextLocale)
    document.documentElement.lang = nextLocale
    await i18n.changeLanguage(nextLocale)
  }

  const toggleTheme = () => {
    const nextMode = mode === 'dark' ? 'light' : 'dark'
    applyTheme(nextMode)
    setMode(nextMode)
  }

  const handleLogin = async (values: LoginValues) => {
    setSigningIn(true)
    setLoginError(null)
    try {
      const session = await login(values.email, values.password)
      setActor({
        actor_id: session.user.id,
        role: session.user.role,
        locale: session.locale,
        theme: session.theme,
      })
    } catch (error) {
      const msg = error instanceof ApiError ? t('loginFailed') : t('loginFailed')
      setLoginError(msg)
    } finally {
      setSigningIn(false)
    }
  }

  // If we already have a token (e.g. page refresh), try to restore the actor.
  useState(() => {
    const token = getAccessToken()
    if (token && !actor) {
      import('./api')
        .then(({ getCurrentActor }) => getCurrentActor())
        .then(setActor)
        .catch(() => {
          /* token expired or invalid; stay on login */
        })
    }
  })

  if (actor) {
    return (
      <ConfigProvider
        theme={{
          algorithm: mode === 'dark' ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
          token: { colorPrimary: '#12a594', borderRadius: 10, fontFamily: 'Inter, "Noto Sans SC", sans-serif' },
        }}
      >
        <Workspace actor={actor} onSignOut={() => setActor(null)} />
      </ConfigProvider>
    )
  }

  return (
    <ConfigProvider
      theme={{
        algorithm: mode === 'dark' ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
        token: { colorPrimary: '#12a594', borderRadius: 10, fontFamily: 'Inter, "Noto Sans SC", sans-serif' },
      }}
    >
      <main className="page-shell">
        <div className="ambient ambient-one" />
        <div className="ambient ambient-two" />
        <header className="topbar">
          <a className="brand" href="/" aria-label="PCB CDSO">
            <span className="brand-mark"><BulbOutlined /></span>
            <span>PCB <strong>CDSO</strong></span>
          </a>
          <div className="toolbar">
            <Button type="text" aria-label={t('language')} icon={<GlobalOutlined />} onClick={() => void toggleLanguage()}>{t('language')}</Button>
            <Button type="text" aria-label={t(mode === 'dark' ? 'light' : 'dark')} icon={mode === 'dark' ? <SunOutlined /> : <MoonOutlined />} onClick={toggleTheme}>
              {t(mode === 'dark' ? 'light' : 'dark')}
            </Button>
          </div>
        </header>

        <section className="content-grid">
          <div className="product-story">
            <Tag className="version-tag" variant="filled">{t('eyebrow')}</Tag>
            <h1>{t('title')}</h1>
            <p className="lead">{t('subtitle')}</p>
            <div className="signal-list">
              {signals.map(([title, detail], index) => (
                <article className="signal" key={title}>
                  <span className="signal-index">0{index + 1}</span>
                  <div><h2>{t(title)}</h2><p>{t(detail)}</p></div>
                </article>
              ))}
            </div>
          </div>

          <section className="login-card" aria-labelledby="login-title">
            <div className="status"><span />{t('authEnabled')}</div>
            <h2 id="login-title">{t('signIn')}</h2>
            <p className="card-intro">{t('welcome')}</p>
            <Form
              form={form}
              layout="vertical"
              requiredMark={false}
              onFinish={(values) => void handleLogin(values)}
            >
              <Form.Item label={t('email')} name="email" rules={[{ required: true, type: 'email' }]}>
                <Input size="large" prefix={<MailOutlined />} placeholder={t('emailPlaceholder')} aria-label={t('email')} />
              </Form.Item>
              <Form.Item label={t('password')} name="password" rules={[{ required: true }]}>
                <Input.Password size="large" prefix={<LockOutlined />} placeholder={t('passwordPlaceholder')} aria-label={t('password')} />
              </Form.Item>
              {loginError && <Alert type="error" title={loginError} showIcon style={{ marginBottom: 12 }} />}
              <Button type="primary" size="large" aria-label={t('login')} htmlType="submit" block loading={signingIn}>
                {signingIn ? t('signingIn') : t('login')}
              </Button>
            </Form>
          </section>
        </section>
        <footer>PCB CDSO · Preview 0.6</footer>
      </main>
    </ConfigProvider>
  )
}
