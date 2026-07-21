import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'

import { App } from './App'
import { resetI18nForTests } from './i18n'

describe('M0 login shell', () => {
  beforeEach(async () => {
    localStorage.clear()
    document.documentElement.removeAttribute('data-theme')
    await resetI18nForTests()
  })

  it('starts in Chinese and does not expose a fake login flow', () => {
    render(<App />)

    expect(screen.getByRole('heading', { name: 'PCB 工厂冷源需求计算与仿真系统' })).toBeVisible()
    expect(screen.getByLabelText('邮箱')).toBeVisible()
    expect(screen.getByLabelText('密码')).toBeVisible()
    expect(screen.getByRole('button', { name: '登录' })).toBeDisabled()
    expect(screen.getByText('身份认证将在 M1 阶段启用')).toBeVisible()
  })

  it('switches to English and persists the locale', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: 'English' }))

    expect(screen.getByRole('heading', { name: 'PCB Factory Cooling Demand & Simulation' })).toBeVisible()
    expect(screen.getByLabelText('Email')).toBeVisible()
    expect(localStorage.getItem('pcb-cdso:locale:v1')).toBe('en-US')
  })

  it('switches to dark theme and persists the preference', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: '深色模式' }))

    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(localStorage.getItem('pcb-cdso:theme:v1')).toBe('dark')
    expect(screen.getByRole('button', { name: '浅色模式' })).toBeVisible()
  })
})
