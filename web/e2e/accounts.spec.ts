import { expect, test } from './fixtures'

// Each test navigates itself rather than sharing a beforeEach - a fixture
// referenced only by the test body (like testAccount below) is resolved
// when the test body starts, not before an earlier beforeEach hook runs, so
// a shared "goto before each test" hook would race the account's creation.

test('creating an account through the form adds it to the list', async ({ authenticatedPage: page }, testInfo) => {
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

  const row = page.locator('tr', { hasText: businessName })
  await expect(row).toBeVisible()
  await expect(row).toContainText('Sarah Chen')
  await expect(row).toContainText('billing@acme-widgets.test')
  await expect(row).toContainText('221B Baker Street')
})

test('accounts created outside the UI (e.g. via the API) still show up', async ({
  authenticatedPage: page,
  testAccount,
}) => {
  await page.goto('/accounts')
  await expect(page.locator('tr', { hasText: testAccount.business_name })).toBeVisible()
})

test('editing an account through the form pre-fills its current values and persists changes', async ({
  authenticatedPage: page,
  testAccount,
}, testInfo) => {
  const updatedName = `${testAccount.business_name} (updated)`

  await page.goto('/accounts')
  const row = page.locator('tr', { hasText: testAccount.business_name })
  await row.getByRole('button', { name: 'Edit' }).click()

  // Pre-filled from the account being edited, not blank like "New account".
  await expect(page.getByLabel('Business name')).toHaveValue(testAccount.business_name)
  await expect(page.getByLabel('Email')).toHaveValue(`e2e-${testInfo.testId}@example.test`)
  await expect(page.getByLabel('Address')).toHaveValue('1 Test Street')

  await page.getByLabel('Business name').fill(updatedName)
  await page.getByLabel('Contact name').fill('Priya Patel')
  await page.getByRole('button', { name: 'Save' }).click()

  // Not asserting the old row is gone by locating it separately - the
  // accounts list is global (see CLAUDE.md), so other tests' rows are
  // visible here too, and this update is in-place (one row, new values),
  // not a second row appearing alongside an untouched original.
  const updatedRow = page.locator('tr', { hasText: updatedName })
  await expect(updatedRow).toBeVisible()
  await expect(updatedRow).toContainText('Priya Patel')
})

test('cancelling an edit discards changes', async ({ authenticatedPage: page, testAccount }) => {
  await page.goto('/accounts')
  const row = page.locator('tr', { hasText: testAccount.business_name })
  await row.getByRole('button', { name: 'Edit' }).click()

  await page.getByLabel('Business name').fill('Should not be saved')
  await page.getByRole('button', { name: 'Cancel' }).click()

  await expect(page.locator('tr', { hasText: testAccount.business_name })).toBeVisible()
  await expect(page.locator('tr', { hasText: 'Should not be saved' })).toHaveCount(0)
})
