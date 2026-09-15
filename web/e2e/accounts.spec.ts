import { expect, test } from './fixtures'

// No "updating an account" spec here - there is no edit route/endpoint yet
// (see docs/api.md); these cover what actually exists: create and list.
//
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
