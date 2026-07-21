import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { App } from './App'
import { resetI18nForTests } from './i18n'

describe('M1 login shell', () => {
  beforeEach(async () => {
    localStorage.clear()
    sessionStorage.clear()
    document.documentElement.removeAttribute('data-theme')
    await resetI18nForTests()
  })

  it('starts in Chinese with authentication enabled', () => {
    render(<App />)

    expect(screen.getByRole('heading', { name: 'PCB 工厂冷源需求计算与仿真系统' })).toBeVisible()
    expect(screen.getByLabelText('邮箱')).toBeVisible()
    expect(screen.getByLabelText('密码')).toBeVisible()
    // Login is now ENABLED (M1 auth implemented), no longer disabled.
    const loginButton = screen.getByRole('button', { name: '登录' })
    expect(loginButton).not.toBeDisabled()
    expect(screen.getByText('身份认证已启用')).toBeVisible()
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

  it('shows a login error when credentials are rejected', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        status: 401,
        text: () =>
          Promise.resolve(
            JSON.stringify({
              code: 'UNAUTHENTICATED',
              message_key: 'auth.login.invalid_credentials',
              field_path: null,
              details: {},
              request_id: 'req-test-1234567890',
            }),
          ),
      }),
    )

    const user = userEvent.setup()
    render(<App />)

    await user.type(screen.getByLabelText('邮箱'), 'nobody@example.com')
    await user.type(screen.getByLabelText('密码'), 'wrong-password-xx')
    await user.click(screen.getByRole('button', { name: '登录' }))

    expect(await screen.findByText('登录失败，请检查邮箱与密码')).toBeVisible()

    vi.unstubAllGlobals()
  })
})
