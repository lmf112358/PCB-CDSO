import { BulbOutlined, GlobalOutlined, LockOutlined, MailOutlined, MoonOutlined, SunOutlined } from '@ant-design/icons'
import { Button, ConfigProvider, Form, Input, Tag, theme as antdTheme } from 'antd'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { LOCALE_STORAGE_KEY } from './i18n'
import { applyTheme, initialTheme, type ThemeMode } from './theme'
import './styles.css'

const signals = [
  ['processDriven', 'processDrivenDetail'],
  ['simulation', 'simulationDetail'],
  ['traceable', 'traceableDetail'],
] as const

export function App() {
  const { t, i18n } = useTranslation()
  const [mode, setMode] = useState<ThemeMode>(() => {
    const selected = initialTheme()
    applyTheme(selected)
    return selected
  })

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
            <div className="status"><span />{t('foundation')}</div>
            <h2 id="login-title">{t('signIn')}</h2>
            <p className="card-intro">{t('welcome')}</p>
            <Form layout="vertical" requiredMark={false}>
              <Form.Item label={t('email')}>
                <Input size="large" prefix={<MailOutlined />} placeholder={t('emailPlaceholder')} aria-label={t('email')} />
              </Form.Item>
              <Form.Item label={t('password')}>
                <Input.Password size="large" prefix={<LockOutlined />} placeholder={t('passwordPlaceholder')} aria-label={t('password')} />
              </Form.Item>
              <Button type="primary" size="large" aria-label={t('login')} block disabled>{t('login')}</Button>
            </Form>
            <p className="pending-note">{t('pending')}</p>
          </section>
        </section>
        <footer>PCB CDSO · Preview 0.6</footer>
      </main>
    </ConfigProvider>
  )
}
