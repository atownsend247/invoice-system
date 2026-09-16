import { expect, test } from './fixtures'

// Each test navigates itself rather than sharing a beforeEach - a fixture
// referenced only by the test body (like testAccount below) is resolved
// when the test body starts, not before an earlier beforeEach hook runs, so
// a shared "goto before each test" hook would race the account's creation.

test('creating an account through the form lands on its detail page', async ({
  authenticatedPage: page,
}, testInfo) => {
  // Unique per run, not a fixed "Acme Widgets Ltd" - a CI retry of this same
  // test would otherwise find its own earlier, still-present row and fail
  // the strict-mode single-match assertion below (see fixtures.ts).
  const businessName = `Acme Widgets Ltd ${testInfo.testId}`

  await page.goto('/accounts')
  await page.getByRole('button', { name: 'New account' }).click()
  await page.getByLabel('Business name').fill(businessName)
  await page.getByLabel('Email').fill('billing@acme-widgets.test')
  await page.getByLabel('Address').fill('221B Baker Street')
  await page.getByLabel('Contact name').fill('Sarah Chen')
  await page.getByRole('button', { name: 'Create account' }).click()

  await expect(page).toHaveURL(/\/accounts\/\d+$/)
  await expect(page.getByRole('heading', { name: businessName })).toBeVisible()
  await expect(page.getByText('Sarah Chen')).toBeVisible()
  await expect(page.getByText('billing@acme-widgets.test')).toBeVisible()
  await expect(page.getByText('221B Baker Street')).toBeVisible()

  await page.goto('/accounts')
  await expect(page.locator('tr', { hasText: businessName })).toBeVisible()
})

test('accounts created outside the UI (e.g. via the API) still show up', async ({
  authenticatedPage: page,
  testAccount,
}) => {
  await page.goto('/accounts')
  await expect(page.locator('tr', { hasText: testAccount.business_name })).toBeVisible()
})

test('the account detail page lists its quotes and invoices newest first', async ({
  authenticatedPage: page,
  testAccount,
  sentQuote,
  sentInvoice,
}) => {
  await page.goto(`/accounts/${testAccount.id}`)

  await expect(page.getByRole('heading', { name: testAccount.business_name })).toBeVisible()
  await expect(page.getByRole('row', { name: new RegExp(sentQuote.number ?? '') })).toBeVisible()
  await expect(page.getByRole('row', { name: new RegExp(sentInvoice.number ?? '') })).toBeVisible()
})

test('editing an account through the form pre-fills its current values and persists changes', async ({
  authenticatedPage: page,
  testAccount,
}, testInfo) => {
  const updatedName = `${testAccount.business_name} (updated)`

  await page.goto(`/accounts/${testAccount.id}`)
  await page.getByRole('button', { name: 'Edit' }).click()

  // Pre-filled from the account being edited, not blank like "New account".
  await expect(page.getByLabel('Business name')).toHaveValue(testAccount.business_name)
  await expect(page.getByLabel('Email')).toHaveValue(`e2e-${testInfo.testId}@example.test`)
  await expect(page.getByLabel('Address')).toHaveValue('1 Test Street')

  await page.getByLabel('Business name').fill(updatedName)
  await page.getByLabel('Contact name').fill('Priya Patel')
  await page.getByRole('button', { name: 'Save' }).click()

  await expect(page.getByRole('heading', { name: updatedName })).toBeVisible()
  await expect(page.getByText('Priya Patel')).toBeVisible()
})

test('cancelling an edit discards changes', async ({ authenticatedPage: page, testAccount }) => {
  await page.goto(`/accounts/${testAccount.id}`)
  await page.getByRole('button', { name: 'Edit' }).click()

  await page.getByLabel('Business name').fill('Should not be saved')
  await page.getByRole('button', { name: 'Cancel' }).click()

  await expect(page.getByRole('heading', { name: testAccount.business_name })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Should not be saved' })).toHaveCount(0)
})
