import { apiFetch, expect, test } from './fixtures'

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
  await page.getByLabel('Address line 1').fill('221B Baker Street')
  await page.getByLabel('Town or city (optional)').fill('London')
  await page.getByLabel('Postcode (optional)').fill('NW1 6XE')
  await page.getByLabel('Contact name').fill('Sarah Chen')
  await page.getByRole('button', { name: 'Create account' }).click()

  await expect(page).toHaveURL(/\/accounts\/[^/]+$/)
  await expect(page.getByRole('heading', { name: businessName })).toBeVisible()
  await expect(page.getByText('Sarah Chen')).toBeVisible()
  await expect(page.getByText('billing@acme-widgets.test')).toBeVisible()
  await expect(page.getByText('221B Baker Street')).toBeVisible()
  await expect(page.getByText('London')).toBeVisible()
  await expect(page.getByText('NW1 6XE')).toBeVisible()

  // Search first - the accounts list is paginated, and this account could
  // otherwise land on a later page once enough other tests/workers have
  // created accounts of their own in the same shared organisation.
  await page.goto('/accounts')
  await page.getByLabel('Search accounts').fill(businessName)
  await expect(page.locator('tr', { hasText: businessName })).toBeVisible()
})

test('accounts created outside the UI (e.g. via the API) still show up', async ({
  authenticatedPage: page,
  testAccount,
}) => {
  await page.goto('/accounts')
  await page.getByLabel('Search accounts').fill(testAccount.business_name)
  await expect(page.locator('tr', { hasText: testAccount.business_name })).toBeVisible()
})

test('clicking a row in the accounts list opens its detail page', async ({
  authenticatedPage: page,
  testAccount,
}) => {
  await page.goto('/accounts')
  await page.getByLabel('Search accounts').fill(testAccount.business_name)
  await page.locator('tr', { hasText: testAccount.business_name }).click()

  await expect(page).toHaveURL(`/accounts/${testAccount.id}`)
  await expect(page.getByRole('heading', { name: testAccount.business_name })).toBeVisible()
})

test('the search box filters the accounts list', async ({ authenticatedPage: page, testAccount }) => {
  await page.goto('/accounts')
  await expect(page.locator('tr', { hasText: testAccount.business_name })).toBeVisible()

  await page.getByLabel('Search accounts').fill(testAccount.business_name)
  await expect(page.locator('tr', { hasText: testAccount.business_name })).toBeVisible()
  await expect(page.locator('tbody tr')).toHaveCount(1)

  await page.getByLabel('Search accounts').fill('a business name that does not exist anywhere')
  await expect(page.getByText(/No accounts match/)).toBeVisible()
  await expect(page.locator('tbody tr')).toHaveCount(0)
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
  await expect(page.getByLabel('Address line 1')).toHaveValue('1 Test Street')

  await page.getByLabel('Business name').fill(updatedName)
  await page.getByLabel('Contact name').fill('Priya Patel')
  await page.getByLabel('Town or city (optional)').fill('Bristol')
  await page.getByRole('button', { name: 'Save' }).click()

  await expect(page.getByRole('heading', { name: updatedName })).toBeVisible()
  await expect(page.getByText('Priya Patel')).toBeVisible()
  await expect(page.getByText('Bristol')).toBeVisible()
})

test('cancelling an edit discards changes', async ({ authenticatedPage: page, testAccount }) => {
  await page.goto(`/accounts/${testAccount.id}`)
  await page.getByRole('button', { name: 'Edit' }).click()

  await page.getByLabel('Business name').fill('Should not be saved')
  await page.getByRole('button', { name: 'Cancel' }).click()

  await expect(page.getByRole('heading', { name: testAccount.business_name })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Should not be saved' })).toHaveCount(0)
})

test('the accounts list paginates when there are enough accounts', async ({
  authenticatedPage: page,
  apiToken,
}, testInfo) => {
  // Only needs to exceed one page's worth (20) - other tests/workers only
  // ever add more accounts to this shared organisation, never remove them,
  // so this comfortably guarantees a second page regardless of run order.
  await Promise.all(
    Array.from({ length: 25 }, (_, i) =>
      apiFetch('/accounts', apiToken, {
        method: 'POST',
        body: JSON.stringify({
          business_name: `${testInfo.testId} Pagination Co ${i}`,
          email: `e2e-pagination-${testInfo.testId}-${i}@example.test`,
          address_line1: '1 Test Street',
        }),
      }),
    ),
  )

  await page.goto('/accounts')
  await expect(page.getByText(/Page 1 of \d+/)).toBeVisible()
  await expect(page.getByRole('button', { name: 'Previous' })).toBeDisabled()

  await page.getByRole('button', { name: 'Next' }).click()
  await expect(page.getByText(/Page 2 of \d+/)).toBeVisible()
  await expect(page.getByRole('button', { name: 'Previous' })).toBeEnabled()
})
