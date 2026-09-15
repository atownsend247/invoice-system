import { expect, test } from '@playwright/test'
import { TEST_EMAIL, TEST_PASSWORD } from './constants'

test('redirects to login when logged out', async ({ page }) => {
  await page.goto('/accounts')
  await expect(page.getByRole('heading', { name: 'Invoice System' })).toBeVisible()
  await expect(page.getByLabel('Email')).toBeVisible()
})

test('login with bad credentials shows an error and stays put', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('Email').fill(TEST_EMAIL)
  await page.getByLabel('Password').fill('wrong password')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('alert')).toContainText('incorrect email or password')
})

test('account -> quote -> invoice, with PDFs, end to end', async ({ page }) => {
  const consoleErrors: string[] = []
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text())
  })
  page.on('pageerror', (err) => consoleErrors.push(String(err)))

  await page.goto('/login')
  await page.getByLabel('Email').fill(TEST_EMAIL)
  await page.getByLabel('Password').fill(TEST_PASSWORD)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('heading', { name: 'Accounts' })).toBeVisible()

  await page.getByRole('button', { name: 'New account' }).click()
  await page.getByLabel('Business name').fill('Acme Widgets Ltd')
  await page.getByLabel('Email').fill('billing@acme-widgets.test')
  await page.getByLabel('Address').fill('221B Baker Street')
  await page.getByRole('button', { name: 'Create account' }).click()
  await expect(page.getByText('Acme Widgets Ltd')).toBeVisible()

  await page.getByRole('link', { name: 'New quote' }).click()
  await expect(page.getByRole('heading', { name: 'New quote' })).toBeVisible()
  await page.getByLabel('Account').selectOption({ label: 'Acme Widgets Ltd' })
  await page.getByRole('button', { name: 'Create draft quote' }).click()
  await expect(page.getByRole('heading', { name: /Draft quote/ })).toBeVisible()

  await page.getByLabel('Description').fill('Website redesign')
  await page.getByLabel('Qty').fill('1')
  await page.getByLabel('Unit price').fill('2500.00')
  await page.getByRole('button', { name: 'Add item' }).click()
  await expect(page.getByText('Website redesign')).toBeVisible()

  const quoteDownload = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Download PDF' }).click()
  expect((await quoteDownload).suggestedFilename()).toMatch(/^quote-\d+\.pdf$/)

  await page.getByRole('button', { name: 'Send' }).click()
  await expect(page.getByText('Q-0001')).toBeVisible()

  await page.getByRole('button', { name: 'Convert to invoice' }).click()
  await expect(page.getByRole('heading', { name: /Draft invoice/ })).toBeVisible()
  await expect(page.getByText('converted from quote #')).toBeVisible()

  await page.getByRole('button', { name: 'Send' }).click()
  await expect(page.getByText('INV-0001')).toBeVisible()

  const invoiceDownload = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Download PDF' }).click()
  expect((await invoiceDownload).suggestedFilename()).toBe('INV-0001.pdf')

  expect(consoleErrors, `unexpected browser console errors: ${consoleErrors.join('; ')}`).toHaveLength(0)
})
