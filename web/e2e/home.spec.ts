import { apiFetch, expect, test, type ApiInvoice, type ApiQuote } from './fixtures'

// The invoice list behind the home dashboard is global (no account_id
// filter - see HomePage.tsx), so other tests' invoices are visible here
// too. Nothing in this app can ever produce a genuinely overdue invoice
// (due_date is always computed server-side as today + a positive
// payment_terms_days - see CLAUDE.md), so "no overdue invoices" is a safe
// assertion regardless of what else is running in parallel.

test('the nav links to the home page', async ({ authenticatedPage: page }) => {
  await page.goto('/accounts')
  await page.getByRole('link', { name: 'Home' }).click()
  await expect(page).toHaveURL('/')
  await expect(page.getByRole('heading', { name: 'Home' })).toBeVisible()
})

test('a sent invoice not yet due appears under Outstanding, not Overdue', async ({
  authenticatedPage: page,
  sentInvoice,
  testAccount,
}) => {
  await page.goto('/')

  const overdueSection = page.locator('.dashboard-section', { hasText: 'Overdue' })
  await expect(overdueSection.getByText('No overdue invoices.')).toBeVisible()

  const outstandingSection = page.locator('.dashboard-section', { hasText: 'Outstanding' })
  const row = outstandingSection.getByRole('row', { name: new RegExp(sentInvoice.number ?? '') })
  await expect(row).toBeVisible()
  await expect(row.getByText(testAccount.business_name)).toBeVisible()
})

// The monthly-totals chart sums every invoice system-wide (see
// InvoiceService.monthly_totals) in the business profile's reporting
// currency, so it isn't isolated per test the way an account/quote/invoice
// is - concurrent tests contribute to the same buckets. That's why this
// only checks structure (12 months, correct currency in the group label)
// and that paying an invoice moves it out of Outstanding, rather than
// asserting an exact total - see web/README.md. Exact aggregation math is
// covered at the unit level (tests/core/test_invoice_service.py).
test('paying an invoice removes it from Outstanding and the chart reports the reporting currency', async ({
  authenticatedPage: page,
  apiToken,
  testAccount,
  reportingCurrency,
}) => {
  const quote = await apiFetch<ApiQuote>('/quotes', apiToken, {
    method: 'POST',
    body: JSON.stringify({ account_id: testAccount.id, currency: reportingCurrency }),
  })
  await apiFetch(`/quotes/${quote.id}/line-items`, apiToken, {
    method: 'POST',
    body: JSON.stringify({ description: 'Setup work', quantity: '1', unit_price: '100.00' }),
  })
  const sentQuote = await apiFetch<ApiQuote>(`/quotes/${quote.id}/send`, apiToken, { method: 'POST' })
  const invoice = await apiFetch<ApiInvoice>(`/quotes/${sentQuote.id}/convert`, apiToken, { method: 'POST' })
  const sent = await apiFetch<ApiInvoice>(`/invoices/${invoice.id}/send`, apiToken, { method: 'POST' })

  await page.goto(`/invoices/${sent.id}`)
  await page.getByRole('button', { name: 'Mark as paid' }).click()
  await expect(page.getByText('paid', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Mark as paid' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Void' })).toHaveCount(0)

  await page.goto('/')
  const outstandingSection = page.locator('.dashboard-section', { hasText: 'Outstanding' })
  await expect(outstandingSection.getByRole('row', { name: new RegExp(sent.number ?? '') })).toHaveCount(0)

  // Not asserting the exact currency here - `reportingCurrency` was read at
  // the start of this test, and a concurrent settings.spec.ts run on
  // another worker can change the shared profile's currency before this
  // assertion runs (a real race, caught by running the full suite, not
  // just this file in isolation - see the settings.spec.ts stress-testing
  // note in CLAUDE.md). Any currency in the group name proves the profile
  // wiring works; that's what's being checked.
  const chart = page.getByRole('group', { name: /^Invoice totals by month, in \w+$/ })
  await expect(chart).toBeVisible()
  await expect(page.locator('.monthly-chart-column')).toHaveCount(12)
})

// The account count is global (every account, not per-test), and other
// specs create accounts concurrently - so this only checks the count went
// up by *at least* one after creating an account, never an exact value
// (a concurrent worker creating its own account between the two reads
// would make an exact-delta assertion flaky, not wrong).
test('all-time stats reflects a newly created account', async ({ authenticatedPage: page, apiToken }, testInfo) => {
  await page.goto('/')
  const statValue = page.locator('.stat', { hasText: 'Accounts registered' }).locator('dd')
  await expect(statValue).toBeVisible()
  const before = Number(await statValue.textContent())

  await apiFetch('/accounts', apiToken, {
    method: 'POST',
    body: JSON.stringify({
      business_name: `Stats test ${testInfo.testId}`,
      email: `stats-${testInfo.testId}@example.test`,
      address_line1: '1 Test Street',
    }),
  })

  await page.reload()
  await expect(async () => {
    expect(Number(await statValue.textContent())).toBeGreaterThanOrEqual(before + 1)
  }).toPass()
})
