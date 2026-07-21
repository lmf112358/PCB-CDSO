import { expect, test } from '@playwright/test'

test('serves the bilingual themed M0 login shell', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByRole('heading', { name: 'PCB 工厂冷源需求计算与仿真系统' })).toBeVisible()
  await expect(page.getByRole('button', { name: '登录' })).toBeDisabled()

  await page.getByRole('button', { name: 'English' }).click()
  await expect(page.getByRole('heading', { name: 'PCB Factory Cooling Demand & Simulation' })).toBeVisible()

  await page.getByRole('button', { name: 'Dark mode' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
})
