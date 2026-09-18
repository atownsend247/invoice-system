import { expect, test } from './fixtures'

test('recording an expense from an account and adding a line item', async ({
  authenticatedPage: page,
  testAccount,
}) => {
  await page.goto(`/accounts/${testAccount.id}`)
  await page.getByRole('link', { name: 'New expense' }).click()
  await expect(page.getByRole('heading', { name: 'New expense' })).toBeVisible()
  await page.getByLabel('Account').selectOption({ label: testAccount.business_name })
  await page.getByRole('textbox', { name: 'Currency' }).fill('USD')
  await page.getByRole('button', { name: 'Record expense' }).click()

  // Unlike a quote, an expense gets its EXP-number immediately - no
  // draft state to move through first (see CLAUDE.md).
  await expect(page.getByRole('heading', { name: /^EXP-\d{4}$/ })).toBeVisible()

  await page.getByLabel('Description').fill('Domain renewal')
  await page.getByLabel('Qty').fill('1')
  await page.getByLabel('Unit price').fill('12.00')
  await page.getByRole('button', { name: 'Add item' }).click()

  await expect(page.getByText('Domain renewal')).toBeVisible()
  await expect(page.locator('tfoot')).toContainText('12.00 USD')
})

test('setting an explicit expense date at creation, then editing it afterward', async ({
  authenticatedPage: page,
  testAccount,
}) => {
  await page.goto(`/accounts/${testAccount.id}`)
  await page.getByRole('link', { name: 'New expense' }).click()
  await page.getByLabel('Account').selectOption({ label: testAccount.business_name })
  await page.getByRole('textbox', { name: 'Currency' }).fill('USD')
  // Recorded today, but the money was actually spent earlier - the whole
  // point of this field being distinct from the recorded date (see
  // CLAUDE.md/models.Expense). getByRole('textbox', ...), not getByLabel -
  // same reasoning as this file's existing Currency field just above.
  await page.getByRole('textbox', { name: 'Expense date' }).fill('2026-02-20')
  await page.getByRole('button', { name: 'Record expense' }).click()

  await expect(page.getByRole('heading', { name: /^EXP-\d{4}$/ })).toBeVisible()
  await expect(page.getByText('Expense date: 2026-02-20')).toBeVisible()

  await page.getByRole('button', { name: 'Edit' }).click()
  await page.getByRole('textbox', { name: 'Expense date', exact: true }).fill('2026-03-01')
  await page.getByRole('button', { name: 'Save' }).click()

  await expect(page.getByText('Expense date: 2026-03-01')).toBeVisible()
  await expect(page.getByText('Expense date: 2026-02-20')).toHaveCount(0)

  // Persists across a reload, not just held in local component state.
  await page.reload()
  await expect(page.getByText('Expense date: 2026-03-01')).toBeVisible()
})

test('adding a line item with a VAT rate shows it on the line and in the totals', async ({
  authenticatedPage: page,
  expense,
}) => {
  await page.goto(`/expenses/${expense.id}`)
  await page.getByLabel('Description').fill('Software subscription')
  await page.getByLabel('Qty').fill('1')
  await page.getByLabel('Unit price').fill('100.00')
  await page.getByLabel('VAT rate').selectOption('0.20')
  await page.getByRole('button', { name: 'Add item' }).click()

  const row = page.locator('tbody tr', { hasText: 'Software subscription' })
  await expect(row).toContainText('20%')
  await expect(row).toContainText('120.00 USD') // gross - net plus VAT

  await expect(page.locator('tfoot tr', { hasText: 'Subtotal' })).toContainText('100.00 USD')
  await expect(page.locator('tfoot tr', { hasText: /^VAT/ })).toContainText('20.00 USD')
  await expect(page.locator('tfoot tr', { hasText: /^Total/ })).toContainText('120.00 USD')
})

test('line items can be added more than once - there is no draft/sent lifecycle', async ({
  authenticatedPage: page,
  expense,
}) => {
  await page.goto(`/expenses/${expense.id}`)
  await page.getByLabel('Description').fill('First charge')
  await page.getByLabel('Qty').fill('1')
  await page.getByLabel('Unit price').fill('10.00')
  await page.getByRole('button', { name: 'Add item' }).click()
  await expect(page.getByText('First charge')).toBeVisible()

  // Still there and still addable - unlike a quote, nothing here ever
  // becomes non-draft and locks the add-item form away.
  await page.getByLabel('Description').fill('Second charge')
  await page.getByLabel('Qty').fill('1')
  await page.getByLabel('Unit price').fill('5.00')
  await page.getByRole('button', { name: 'Add item' }).click()

  await expect(page.getByText('First charge')).toBeVisible()
  await expect(page.getByText('Second charge')).toBeVisible()
  await expect(page.locator('tfoot')).toContainText('15.00 USD')
})

test('viewing the PDF opens an in-page preview instead of downloading it', async ({
  authenticatedPage: page,
  expense,
}) => {
  await page.goto(`/expenses/${expense.id}`)
  await page.getByRole('button', { name: 'View PDF' }).click()

  const frame = page.locator('.pdf-modal-frame')
  await expect(frame).toBeVisible()
  await expect(frame).toHaveAttribute('src', /^blob:/)

  await page.getByRole('button', { name: 'Close' }).click()
  await expect(frame).toHaveCount(0)
})

test('downloading the PDF works', async ({ authenticatedPage: page, expense }) => {
  await page.goto(`/expenses/${expense.id}`)
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: 'Download PDF' }).click(),
  ])
  expect(download.suggestedFilename()).toMatch(/^EXP-\d{4}\.pdf$/)
})

test('the account detail page lists its expenses', async ({
  authenticatedPage: page,
  testAccount,
  expense,
}) => {
  await page.goto(`/accounts/${testAccount.id}`)
  await expect(page.getByRole('row', { name: new RegExp(expense.number) })).toBeVisible()
})

test('uploading a supplementary PDF shows it in the attachments list', async ({
  authenticatedPage: page,
  expense,
}) => {
  await page.goto(`/expenses/${expense.id}`)
  await expect(page.getByText('No supplementary PDFs uploaded yet.')).toBeVisible()

  await page
    .getByLabel('Upload a PDF')
    .setInputFiles({ name: 'receipt.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4 fake') })
  await page.getByRole('button', { name: 'Upload', exact: true }).click()

  const row = page.locator('tbody tr', { hasText: 'receipt.pdf' })
  await expect(row).toBeVisible()
  await expect(page.getByText('No supplementary PDFs uploaded yet.')).toHaveCount(0)
})

test('an upload that is not a PDF is rejected with an error', async ({
  authenticatedPage: page,
  expense,
}) => {
  await page.goto(`/expenses/${expense.id}`)
  await page
    .getByLabel('Upload a PDF')
    .setInputFiles({ name: 'notes.txt', mimeType: 'text/plain', buffer: Buffer.from('not a pdf') })
  await page.getByRole('button', { name: 'Upload', exact: true }).click()

  await expect(page.getByRole('alert')).toBeVisible()
  await expect(page.getByText('No supplementary PDFs uploaded yet.')).toBeVisible()
})

test('viewing an uploaded attachment opens an in-page preview', async ({
  authenticatedPage: page,
  expense,
}) => {
  await page.goto(`/expenses/${expense.id}`)
  await page
    .getByLabel('Upload a PDF')
    .setInputFiles({ name: 'receipt.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4 fake') })
  await page.getByRole('button', { name: 'Upload', exact: true }).click()
  await expect(page.locator('tbody tr', { hasText: 'receipt.pdf' })).toBeVisible()

  await page.locator('tbody tr', { hasText: 'receipt.pdf' }).getByRole('button', { name: 'View' }).click()

  const frame = page.locator('.pdf-modal-frame')
  await expect(frame).toBeVisible()
  await expect(frame).toHaveAttribute('src', /^blob:/)

  await page.getByRole('button', { name: 'Close' }).click()
  await expect(frame).toHaveCount(0)
})

test('downloading an uploaded attachment works', async ({ authenticatedPage: page, expense }) => {
  await page.goto(`/expenses/${expense.id}`)
  await page
    .getByLabel('Upload a PDF')
    .setInputFiles({ name: 'receipt.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4 fake') })
  await page.getByRole('button', { name: 'Upload', exact: true }).click()
  const row = page.locator('tbody tr', { hasText: 'receipt.pdf' })
  await expect(row).toBeVisible()

  const [download] = await Promise.all([
    page.waitForEvent('download'),
    row.getByRole('button', { name: 'Download' }).click(),
  ])
  expect(download.suggestedFilename()).toBe('receipt.pdf')
})

test('deleting an uploaded attachment removes it from the list', async ({
  authenticatedPage: page,
  expense,
}) => {
  await page.goto(`/expenses/${expense.id}`)
  await page
    .getByLabel('Upload a PDF')
    .setInputFiles({ name: 'receipt.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4 fake') })
  await page.getByRole('button', { name: 'Upload', exact: true }).click()
  const row = page.locator('tbody tr', { hasText: 'receipt.pdf' })
  await expect(row).toBeVisible()

  await row.getByRole('button', { name: 'Delete' }).click()

  await expect(row).toHaveCount(0)
  await expect(page.getByText('No supplementary PDFs uploaded yet.')).toBeVisible()
})
