import { expect, test } from './fixtures'

test('creating a draft quote and adding a line item', async ({ authenticatedPage: page, testAccount }) => {
  await page.goto(`/quotes/new?accountId=${testAccount.id}`)
  await expect(page.getByRole('heading', { name: 'New quote' })).toBeVisible()
  await page.getByLabel('Account').selectOption({ label: testAccount.business_name })
  await page.getByRole('button', { name: 'Create draft quote' }).click()
  await expect(page.getByRole('heading', { name: /Draft quote/ })).toBeVisible()

  await page.getByLabel('Description').fill('Website redesign')
  await page.getByLabel('Qty').fill('1')
  await page.getByLabel('Unit price').fill('2500.00')
  await page.getByRole('button', { name: 'Add item' }).click()

  await expect(page.getByText('Website redesign')).toBeVisible()
  await expect(page.locator('tfoot')).toContainText('2500.00 USD')
})

test('Send is disabled until the quote has at least one line item', async ({
  authenticatedPage: page,
  draftQuote,
}) => {
  await page.goto(`/quotes/${draftQuote.id}`)
  await expect(page.getByRole('button', { name: 'Send' })).toBeDisabled()

  await page.getByLabel('Description').fill('Work')
  await page.getByLabel('Qty').fill('1')
  await page.getByLabel('Unit price').fill('50.00')
  await page.getByRole('button', { name: 'Add item' }).click()

  await expect(page.getByRole('button', { name: 'Send' })).toBeEnabled()
})

test('sending a quote assigns a number and freezes its line items', async ({
  authenticatedPage: page,
  draftQuote,
}) => {
  await page.goto(`/quotes/${draftQuote.id}`)
  await page.getByLabel('Description').fill('Work')
  await page.getByLabel('Qty').fill('1')
  await page.getByLabel('Unit price').fill('50.00')
  await page.getByRole('button', { name: 'Add item' }).click()

  await page.getByRole('button', { name: 'Send' }).click()
  await expect(page.getByText(/^Q-\d{4}$/)).toBeVisible()
  await expect(page.getByLabel('Description')).toHaveCount(0) // add-item form is gone
})

test('converting a sent quote creates a matching draft invoice', async ({
  authenticatedPage: page,
  sentQuote,
}) => {
  await page.goto(`/quotes/${sentQuote.id}`)
  await page.getByRole('button', { name: 'Convert to invoice' }).click()
  await expect(page.getByRole('heading', { name: /Draft invoice/ })).toBeVisible()
  await expect(page.getByText(`converted from quote #${sentQuote.id}`)).toBeVisible()
})
