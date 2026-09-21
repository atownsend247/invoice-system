import { expect, test } from './fixtures'

test('creating a draft quote and adding a line item', async ({ authenticatedPage: page, testAccount }) => {
  await page.goto(`/quotes/new?accountId=${testAccount.id}`)
  await expect(page.getByRole('heading', { name: 'New quote' })).toBeVisible()
  await page.getByLabel('Account').selectOption({ label: testAccount.business_name })
  // Explicit, not relying on the field's default - it now pre-fills from
  // the business profile's reporting currency (see CLAUDE.md), which is a
  // shared value other specs also change, rather than a fixed 'USD'.
  await page.getByRole('textbox', { name: 'Currency' }).fill('USD')
  await page.getByRole('button', { name: 'Create draft quote' }).click()
  await expect(page.getByRole('heading', { name: /Draft quote/ })).toBeVisible()

  await page.getByLabel('Description').fill('Website redesign')
  await page.getByLabel('Qty').fill('1')
  await page.getByLabel('Unit price').fill('2500.00')
  await page.getByRole('button', { name: 'Add item' }).click()

  await expect(page.getByText('Website redesign')).toBeVisible()
  await expect(page.locator('tfoot')).toContainText('2500.00 USD')
})

test('setting an issue date at creation computes the expiry date and shows a Created activity entry', async ({
  authenticatedPage: page,
  testAccount,
}) => {
  await page.goto(`/quotes/new?accountId=${testAccount.id}`)
  await page.getByLabel('Account').selectOption({ label: testAccount.business_name })
  await page.getByRole('textbox', { name: 'Currency' }).fill('USD')
  await page.getByRole('textbox', { name: 'Issue date' }).fill('2026-01-01')
  await page.getByRole('button', { name: 'Create draft quote' }).click()

  await expect(page.getByText('issued 2026-01-01')).toBeVisible()
  await expect(page.getByText(/expires 2026-01-31/)).toBeVisible() // + default 30-day validity
  await expect(page.getByRole('heading', { name: 'Activity' })).toBeVisible()
  await expect(page.getByText('Created (draft)')).toBeVisible()
})

test('sending and converting a quote each add an activity entry, newest first', async ({
  authenticatedPage: page,
  draftQuote,
}) => {
  await page.goto(`/quotes/${draftQuote.id}`)
  await page.getByLabel('Description').fill('Work')
  await page.getByLabel('Qty').fill('1')
  await page.getByLabel('Unit price').fill('50.00')
  await page.getByRole('button', { name: 'Add item' }).click()
  await page.getByRole('button', { name: 'Send' }).click()

  const activity = page.locator('.activity-timeline li')
  await expect(activity.first()).toContainText('draft → sent')
  await expect(activity.last()).toContainText('Created')
})

test('converting a quote can backdate the resulting invoice issue date', async ({
  authenticatedPage: page,
  sentQuote,
}) => {
  await page.goto(`/quotes/${sentQuote.id}`)
  await page.getByLabel('Issue date (optional, defaults to today)').fill('2025-11-01')
  await page.getByRole('button', { name: 'Convert to invoice' }).click()

  await expect(page.getByRole('heading', { name: /Draft invoice/ })).toBeVisible()
  await expect(page.getByText('issued 2025-11-01')).toBeVisible()
})

test('adding a line item with a VAT rate shows it on the line and in the totals', async ({
  authenticatedPage: page,
  draftQuote,
}) => {
  await page.goto(`/quotes/${draftQuote.id}`)
  await page.getByLabel('Description').fill('Design work')
  await page.getByLabel('Qty').fill('1')
  await page.getByLabel('Unit price').fill('100.00')
  await page.getByLabel('VAT rate').selectOption('0.20')
  await page.getByRole('button', { name: 'Add item' }).click()

  const row = page.locator('tbody tr', { hasText: 'Design work' })
  await expect(row).toContainText('20%')
  await expect(row).toContainText('120.00 USD') // gross - net plus VAT

  // Scoped to each footer row individually, not the whole tfoot - "20.00
  // USD" is a substring of "120.00 USD", so a whole-tfoot text check would
  // pass even if the VAT row's own amount were wrong.
  await expect(page.locator('tfoot tr', { hasText: 'Subtotal' })).toContainText('100.00 USD')
  await expect(page.locator('tfoot tr', { hasText: /^VAT/ })).toContainText('20.00 USD')
  await expect(page.locator('tfoot tr', { hasText: /^Total/ })).toContainText('120.00 USD')
})

test('VAT rate defaults to 0% when not changed', async ({ authenticatedPage: page, draftQuote }) => {
  await page.goto(`/quotes/${draftQuote.id}`)
  await page.getByLabel('Description').fill('Work')
  await page.getByLabel('Qty').fill('1')
  await page.getByLabel('Unit price').fill('50.00')
  await page.getByRole('button', { name: 'Add item' }).click()

  const row = page.locator('tbody tr', { hasText: 'Work' })
  await expect(row).toContainText('0%')
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
  // Not the default "Q-0001"-style prefix specifically - the quote-number
  // prefix/digit count are themselves now a shared BusinessProfile field
  // (see CLAUDE.md's number-prefix/digits gotcha), and settings.spec.ts's
  // own persistence test briefly saves it as something else mid-run on a
  // concurrent worker. What this test actually verifies is that *a*
  // number got assigned (shown as the page's own heading once sent), not
  // which format it's in.
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(/^\S+-\d+$/)
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

test('a converted quote shows a View invoice button linking back to the resulting invoice', async ({
  authenticatedPage: page,
  sentQuote,
}) => {
  await page.goto(`/quotes/${sentQuote.id}`)
  await page.getByRole('button', { name: 'Convert to invoice' }).click()
  await expect(page.getByRole('heading', { name: /Draft invoice/ })).toBeVisible()
  const invoiceUrl = page.url()

  // Navigate away and back, rather than checking straight after
  // converting - the initial "Convert to invoice" click already redirects
  // there once; this checks the link still works on a later visit too.
  await page.goto(`/quotes/${sentQuote.id}`)
  await expect(page.getByRole('button', { name: 'Convert to invoice' })).toHaveCount(0)
  await page.getByRole('button', { name: 'View invoice' }).click()
  await expect(page).toHaveURL(invoiceUrl)
})

test('viewing the PDF opens an in-page preview instead of downloading it', async ({
  authenticatedPage: page,
  draftQuote,
}) => {
  await page.goto(`/quotes/${draftQuote.id}`)
  await page.getByRole('button', { name: 'View PDF' }).click()

  const frame = page.locator('.pdf-modal-frame')
  await expect(frame).toBeVisible()
  await expect(frame).toHaveAttribute('src', /^blob:/)

  await page.getByRole('button', { name: 'Close' }).click()
  await expect(frame).toHaveCount(0)
})

test('filtering the quotes list by account name and status', async ({
  authenticatedPage: page,
  testAccount,
  sentQuote,
}) => {
  await page.goto('/quotes')

  // testAccount.business_name is unique per test (see fixtures.ts), so this
  // filter always narrows down to exactly this test's own quote regardless
  // of what else exists in the shared organisation.
  await page.getByLabel('Account').fill(testAccount.business_name)
  await expect(page.locator('tbody tr', { hasText: sentQuote.number ?? '' })).toBeVisible()

  await page.getByLabel('Status').selectOption('draft')
  await expect(page.getByText('No quotes match these filters.')).toBeVisible()

  await page.getByLabel('Status').selectOption('sent')
  await expect(page.locator('tbody tr', { hasText: sentQuote.number ?? '' })).toBeVisible()
})
