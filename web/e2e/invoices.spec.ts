import { expect, test } from './fixtures'

// No "updating an invoice" spec - line items are fixed at conversion time,
// there is no add-line-item route for invoices (see docs/api.md). What can
// change after creation is status (send/void) and that's what these cover.

test('shows the line items copied from its quote, with a link back to it', async ({
  authenticatedPage: page,
  draftInvoice,
  sentQuote,
}) => {
  await page.goto(`/invoices/${draftInvoice.id}`)
  await expect(page.getByText('Setup work')).toBeVisible()
  await expect(page.getByText(`converted from quote #${sentQuote.id}`)).toBeVisible()
})

test('downloading the PDF works even before the invoice is sent', async ({
  authenticatedPage: page,
  draftInvoice,
}) => {
  await page.goto(`/invoices/${draftInvoice.id}`)
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: 'Download PDF' }).click(),
  ])
  expect(download.suggestedFilename()).toMatch(/^invoice-\d+\.pdf$/)
})

test('sending an invoice assigns a number and a due date', async ({ authenticatedPage: page, draftInvoice }) => {
  await page.goto(`/invoices/${draftInvoice.id}`)
  await page.getByRole('button', { name: 'Send' }).click()
  await expect(page.getByText(/^INV-\d{4}$/)).toBeVisible()
  await expect(page.getByText(/due \d{4}-\d{2}-\d{2}/)).toBeVisible()
})

test('voiding an invoice updates its status and removes further actions', async ({
  authenticatedPage: page,
  draftInvoice,
}) => {
  await page.goto(`/invoices/${draftInvoice.id}`)
  await page.getByRole('button', { name: 'Void' }).click()

  await expect(page.getByText('void', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Send' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Void' })).toHaveCount(0)
})
