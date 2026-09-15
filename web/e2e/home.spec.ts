import { expect, test } from './fixtures'

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
