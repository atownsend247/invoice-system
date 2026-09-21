import { apiFetch, expect, test } from './fixtures'

// The shared test user's profile - not per-test isolated data like
// testAccount, since a business profile is a singleton per user rather
// than a created-per-test record. fullyParallel: false keeps this file's
// tests from running concurrently with each other *within* one run, but
// --repeat-each can still schedule separate repeats of this same file
// across different workers, which raced on the shared profile row and
// failed intermittently before this line was added. `serial` mode pins
// every test in this file (repeats included) to a single worker, run one
// after another - the actual guarantee a shared-mutable-state file needs.
test.describe.configure({ mode: 'serial' })

test('shows the five settings tabs and loads the current profile on visit', async ({
  authenticatedPage: page,
}) => {
  await page.goto('/settings')
  await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible()

  // User tab is active by default - grouped under <fieldset>/<legend>
  // ("group" is the accessible role for a legend) inside a hidden/visible
  // tabpanel, not every section visible at once.
  await expect(page.getByRole('tab', { name: 'User' })).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByRole('group', { name: 'User settings' })).toBeVisible()
  await expect(page.getByRole('group', { name: 'Business settings' })).not.toBeVisible()
  await expect(page.getByRole('group', { name: 'Payment and tax settings' })).not.toBeVisible()
  await expect(page.getByRole('group', { name: 'Document settings' })).not.toBeVisible()
  await expect(page.getByRole('group', { name: 'Registrars' })).not.toBeVisible()

  await page.getByRole('tab', { name: 'Business' }).click()
  await expect(page.getByRole('group', { name: 'Business settings' })).toBeVisible()
  await expect(page.getByRole('group', { name: 'User settings' })).not.toBeVisible()

  await page.getByRole('tab', { name: 'Payment and tax' }).click()
  await expect(page.getByRole('group', { name: 'Payment and tax settings' })).toBeVisible()
  await expect(page.getByRole('group', { name: 'Business settings' })).not.toBeVisible()

  await page.getByRole('tab', { name: 'Document' }).click()
  await expect(page.getByRole('group', { name: 'Document settings' })).toBeVisible()
  // The Document tab's three per-document-type sub-groups.
  await expect(page.getByRole('group', { name: 'Quotes' })).toBeVisible()
  await expect(page.getByRole('group', { name: 'Invoices' })).toBeVisible()
  await expect(page.getByRole('group', { name: 'Expenses' })).toBeVisible()
  await expect(page.getByRole('group', { name: 'Payment and tax settings' })).not.toBeVisible()

  // Registrars isn't a BusinessProfile field group like the other four -
  // it's a self-contained managed list, rendered outside the profile
  // <form> entirely (see SettingsPage.tsx) - but still switches via the
  // same tab bar.
  await page.getByRole('tab', { name: 'Registrars' }).click()
  await expect(page.getByRole('group', { name: 'Registrars' })).toBeVisible()
  await expect(page.getByRole('group', { name: 'Document settings' })).not.toBeVisible()

  // Not asserting a specific "default" value here - a business profile is a
  // singleton per user (see CLAUDE.md), and this spec shares its login user
  // with every other test in this file (and, under --repeat-each, with
  // earlier runs of itself), so "untouched" only holds the very first time
  // ever. What's actually being verified is that the GET wired up and the
  // form populated, not stuck empty/loading - found by stress-testing this
  // spec with --repeat-each before trusting it (same lesson as accounts.spec.ts).
  await page.getByRole('tab', { name: 'Payment and tax' }).click()
  await expect(page.getByLabel('Payment terms (days)')).not.toHaveValue('')
  await expect(page.getByLabel('Currency')).not.toHaveValue('')
})

test('adding, editing, and deleting a registrar', async ({ authenticatedPage: page }, testInfo) => {
  // Unique per test (same reasoning as testAccount's own business_name in
  // fixtures.ts) - registrars are a shared organisation-wide list, so a
  // fixed name would collide across repeated runs of this same spec.
  const name = `${testInfo.testId} 123-Reg`
  const renamed = `${testInfo.testId} GoDaddy`

  await page.goto('/settings')
  await page.getByRole('tab', { name: 'Registrars' }).click()

  await page.getByRole('button', { name: 'Add registrar' }).click()
  // exact: true - "Name" is otherwise a substring match against several
  // other (currently hidden, but still DOM-present) BusinessProfileForm
  // fields on this same page, e.g. "First name"/"Business name" - see
  // SettingsPage.tsx, where every tab's fields stay mounted across
  // switches, just hidden.
  await page.getByLabel('Name', { exact: true }).fill(name)
  await page.getByLabel('Notes (optional)').fill('https://123-reg.co.uk')
  await page.getByRole('button', { name: 'Add', exact: true }).click()

  const row = page.locator('tbody tr', { hasText: name })
  await expect(row).toContainText('https://123-reg.co.uk')

  await row.getByRole('button', { name: 'Edit' }).click()
  await page.getByLabel('Name', { exact: true }).fill(renamed)
  await page.getByLabel('Notes (optional)').fill('')
  await page.getByRole('button', { name: 'Save', exact: true }).click()

  const updatedRow = page.locator('tbody tr', { hasText: renamed })
  await expect(updatedRow).toBeVisible()
  await expect(page.getByText(name, { exact: true })).toHaveCount(0)

  await updatedRow.getByRole('button', { name: 'Delete' }).click()
  await expect(page.getByText(renamed)).toHaveCount(0)
})

test('saving all fields persists them across a reload', async ({ authenticatedPage: page }) => {
  await page.goto('/settings')

  // User tab is active by default.
  await page.getByLabel('Title (optional)').fill('Dr')
  await page.getByLabel('First name').fill('Ada')
  await page.getByLabel('Last name').fill('Lovelace')

  await page.getByRole('tab', { name: 'Business' }).click()
  await page.getByLabel('Business name').fill('Contoso Consulting')
  await page.getByLabel('Address line 1 (optional)').fill('1 Market Street')
  await page.getByLabel('Address line 2 (optional)').fill('Suite 4')
  await page.getByLabel('Town or city (optional)').fill('London')
  await page.getByLabel('County (optional)').fill('Greater London')
  await page.getByLabel('Postcode (optional)').fill('SW1A 1AA')

  await page.getByRole('tab', { name: 'Payment and tax' }).click()
  await page.getByLabel('Payment terms (days)').fill('14')
  await page.getByLabel('Quote validity (days)').fill('45')
  await page.getByLabel('Currency').fill('usd')
  await page.getByLabel('UTR (optional)').fill('1234567890')
  await page.getByLabel('VAT number (optional)').fill('GB123456789')
  await page.getByLabel('Bank account name (optional)').fill('Contoso Consulting Ltd')
  await page.getByLabel('Bank sort code (optional)').fill('12-34-56')
  await page.getByLabel('Bank account number (optional)').fill('12345678')

  await page.getByRole('tab', { name: 'Document' }).click()
  await page.getByLabel('Accent colour').fill('#2563eb')
  const quoteGroup = page.getByRole('group', { name: 'Quotes' })
  await quoteGroup.getByLabel('Number prefix').fill('QUOTE-')
  await quoteGroup.getByLabel('Number digits').fill('6')
  await quoteGroup.getByLabel('Quote header (optional)').fill('Contoso Consulting')
  await quoteGroup.getByLabel('Quote footer (optional)').fill('Valid for 30 days.')
  const invoiceGroup = page.getByRole('group', { name: 'Invoices' })
  await invoiceGroup.getByLabel('Number prefix').fill('INVOICE-')
  await invoiceGroup.getByLabel('Number digits').fill('6')
  await invoiceGroup.getByLabel('Invoice header (optional)').fill('Contoso Consulting\nCompany no. 12345678')
  await invoiceGroup.getByLabel('Invoice footer (optional)').fill('Thank you for your business!')
  const expenseGroup = page.getByRole('group', { name: 'Expenses' })
  await expenseGroup.getByLabel('Number prefix').fill('EXPENSE-')
  await expenseGroup.getByLabel('Number digits').fill('6')
  await expenseGroup.getByLabel('Expense header (optional)').fill('Contoso Consulting')
  await expenseGroup.getByLabel('Expense footer (optional)').fill('Internal use only.')

  await page.getByRole('button', { name: 'Save settings' }).click()
  await expect(page.getByText('Saved.')).toBeVisible()

  await page.reload()
  await expect(page.getByLabel('Title (optional)')).toHaveValue('Dr')
  await expect(page.getByLabel('First name')).toHaveValue('Ada')
  await expect(page.getByLabel('Last name')).toHaveValue('Lovelace')

  await page.getByRole('tab', { name: 'Business' }).click()
  await expect(page.getByLabel('Business name')).toHaveValue('Contoso Consulting')
  await expect(page.getByLabel('Address line 1 (optional)')).toHaveValue('1 Market Street')
  await expect(page.getByLabel('Address line 2 (optional)')).toHaveValue('Suite 4')
  await expect(page.getByLabel('Town or city (optional)')).toHaveValue('London')
  await expect(page.getByLabel('County (optional)')).toHaveValue('Greater London')
  await expect(page.getByLabel('Postcode (optional)')).toHaveValue('SW1A 1AA')

  await page.getByRole('tab', { name: 'Payment and tax' }).click()
  await expect(page.getByLabel('Payment terms (days)')).toHaveValue('14')
  await expect(page.getByLabel('Quote validity (days)')).toHaveValue('45')
  await expect(page.getByLabel('Currency')).toHaveValue('USD') // normalised to uppercase
  await expect(page.getByLabel('UTR (optional)')).toHaveValue('1234567890')
  await expect(page.getByLabel('VAT number (optional)')).toHaveValue('GB123456789')
  await expect(page.getByLabel('Bank account name (optional)')).toHaveValue('Contoso Consulting Ltd')
  await expect(page.getByLabel('Bank sort code (optional)')).toHaveValue('12-34-56')
  await expect(page.getByLabel('Bank account number (optional)')).toHaveValue('12345678')

  await page.getByRole('tab', { name: 'Document' }).click()
  await expect(page.getByLabel('Accent colour')).toHaveValue('#2563eb')
  const reloadedQuoteGroup = page.getByRole('group', { name: 'Quotes' })
  await expect(reloadedQuoteGroup.getByLabel('Number prefix')).toHaveValue('QUOTE-')
  await expect(reloadedQuoteGroup.getByLabel('Number digits')).toHaveValue('6')
  await expect(reloadedQuoteGroup.getByLabel('Quote header (optional)')).toHaveValue('Contoso Consulting')
  await expect(reloadedQuoteGroup.getByLabel('Quote footer (optional)')).toHaveValue('Valid for 30 days.')
  const reloadedInvoiceGroup = page.getByRole('group', { name: 'Invoices' })
  await expect(reloadedInvoiceGroup.getByLabel('Number prefix')).toHaveValue('INVOICE-')
  await expect(reloadedInvoiceGroup.getByLabel('Number digits')).toHaveValue('6')
  await expect(reloadedInvoiceGroup.getByLabel('Invoice header (optional)')).toHaveValue(
    'Contoso Consulting\nCompany no. 12345678',
  )
  await expect(reloadedInvoiceGroup.getByLabel('Invoice footer (optional)')).toHaveValue(
    'Thank you for your business!',
  )
  const reloadedExpenseGroup = page.getByRole('group', { name: 'Expenses' })
  await expect(reloadedExpenseGroup.getByLabel('Number prefix')).toHaveValue('EXPENSE-')
  await expect(reloadedExpenseGroup.getByLabel('Number digits')).toHaveValue('6')
  await expect(reloadedExpenseGroup.getByLabel('Expense header (optional)')).toHaveValue('Contoso Consulting')
  await expect(reloadedExpenseGroup.getByLabel('Expense footer (optional)')).toHaveValue('Internal use only.')

  // Reset the number prefix/digits back to the app's own defaults before
  // finishing - quotes.spec.ts/invoices.spec.ts/expenses.spec.ts assert
  // exact default-format numbers (e.g. /^Q-\d{4}$/) against this same
  // shared demo organisation, and those files' workers can run
  // concurrently with (or after) this one - see CLAUDE.md's number-prefix
  // gotcha. Every other field this test touches isn't asserted exactly by
  // another spec file, so only these six need restoring.
  await reloadedQuoteGroup.getByLabel('Number prefix').fill('Q-')
  await reloadedQuoteGroup.getByLabel('Number digits').fill('4')
  await reloadedInvoiceGroup.getByLabel('Number prefix').fill('INV-')
  await reloadedInvoiceGroup.getByLabel('Number digits').fill('4')
  await reloadedExpenseGroup.getByLabel('Number prefix').fill('EXP-')
  await reloadedExpenseGroup.getByLabel('Number digits').fill('4')
  await page.getByRole('button', { name: 'Save settings' }).click()
  await expect(page.getByText('Saved.')).toBeVisible()
})

test('setting the next quote number takes effect on the following quote', async ({
  authenticatedPage: page,
  testAccount,
  apiToken,
}) => {
  // Quote numbering is organisation-scoped, and every e2e test shares one
  // demo login/organisation (see fixtures.ts) - a *different* spec file's
  // worker can send its own quote at any moment, including right between
  // this test's own "read the current highest number" and "send a new
  // quote" steps below, so this deliberately doesn't assert an exact
  // number (same "Deliberately not exact" reasoning as home.spec.ts's
  // monthly chart, see CLAUDE.md). The jump target is "the highest
  // existing quote number plus a five-hundred buffer" (read via the API
  // just below), not a fixed constant and not something unboundedly
  // large - three failure modes were each caught by actually rerunning
  // the suite against already-seeded data before trusting this test, not
  // by reasoning about it up front:
  //   - A fixed constant (e.g. 5000) collides with itself the *second*
  //     time this test runs against the same persisted local demo
  //     database (a normal `npm run test:e2e` re-run, not just
  //     `--repeat-each` - `reuseExistingServer` keeps that database
  //     around between separate invocations).
  //   - An unboundedly-growing value (e.g. Date.now()) avoids that but
  //     permanently inflates the organisation's quote-number *width*
  //     past what `quotes.spec.ts`'s own assertions assume - "set next
  //     number" is a genuinely irreversible jump (see CLAUDE.md), so
  //     that pollution never un-happens for the rest of a suite run.
  //   - Jumping to exactly one past the current highest number sounds
  //     safest, but the "read current highest" step is itself a snapshot
  //     that can go stale before the "Set" call lands - a concurrent
  //     worker's own quote-send in that window claims that same number
  //     first, and this test's `next-number` call then *rewinds* the
  //     counter behind it, so the following send() collides with that
  //     quote (sqlite3.IntegrityError: UNIQUE constraint failed on a
  //     completely fresh database, not just a repeated one). A few
  //     hundred quotes get sent by the rest of the suite in the seconds
  //     this test's own window is open, so a five-hundred buffer keeps
  //     that realistically out of reach while still advancing the
  //     counter only modestly relative to organic growth.
  // page_size=200 (not 1) and taking the max, not items[0] - GET /quotes
  // sorts newest-*created*-first, not by assigned number, so the most
  // recently created row could easily be an as-yet-unsent draft
  // (`number: null`) rather than the highest-numbered quote.
  const recent = await apiFetch<{ items: { number: string | null }[] }>(
    '/quotes?page_size=200',
    apiToken,
  )
  const latestNumber = Math.max(
    0,
    ...recent.items.map((quote) => Number(quote.number?.replace(/^\D+/, '') ?? '0')),
  )
  const nextNumber = latestNumber + 500

  await page.goto('/settings')
  await page.getByRole('tab', { name: 'Document' }).click()

  // Reset the prefix/digits to known values first - an earlier test in
  // this same serial-mode file (or a previous run) may have left the
  // shared profile's quote prefix as something other than "Q-".
  const quoteGroup = page.getByRole('group', { name: 'Quotes' })
  await quoteGroup.getByLabel('Number prefix').fill('Q-')
  await quoteGroup.getByLabel('Number digits').fill('4')
  await page.getByRole('button', { name: 'Save settings' }).click()
  await expect(page.getByText('Saved.')).toBeVisible()

  await quoteGroup.getByLabel('Next quote number').fill(String(nextNumber))
  await quoteGroup.getByRole('button', { name: 'Set' }).click()
  await expect(quoteGroup.getByText('Set.')).toBeVisible()

  await page.goto(`/quotes/new?accountId=${testAccount.id}`)
  await page.getByLabel('Account').selectOption({ label: testAccount.business_name })
  await page.getByRole('button', { name: 'Create draft quote' }).click()
  await page.getByLabel('Description').fill('Work')
  await page.getByLabel('Qty').fill('1')
  await page.getByLabel('Unit price').fill('100.00')
  await page.getByRole('button', { name: 'Add item' }).click()
  await page.getByRole('button', { name: 'Send' }).click()

  const numberText = await page.getByText(/^Q-\d{4,}$/).textContent()
  const number = Number(numberText?.replace('Q-', ''))
  expect(number).toBeGreaterThanOrEqual(nextNumber)
})

test('title, every address line, UTR and VAT number can all be left blank', async ({
  authenticatedPage: page,
}) => {
  await page.goto('/settings')

  await page.getByLabel('First name').fill('Ada')
  await page.getByLabel('Last name').fill('Lovelace')
  await page.getByLabel('Title (optional)').fill('')

  await page.getByRole('tab', { name: 'Business' }).click()
  await page.getByLabel('Business name').fill('Sole Trader Co')
  await page.getByLabel('Address line 1 (optional)').fill('')
  await page.getByLabel('Address line 2 (optional)').fill('')
  await page.getByLabel('Town or city (optional)').fill('')
  await page.getByLabel('County (optional)').fill('')
  await page.getByLabel('Postcode (optional)').fill('')

  await page.getByRole('tab', { name: 'Payment and tax' }).click()
  await page.getByLabel('UTR (optional)').fill('')
  await page.getByLabel('VAT number (optional)').fill('')
  await page.getByLabel('Bank account name (optional)').fill('')
  await page.getByLabel('Bank sort code (optional)').fill('')
  await page.getByLabel('Bank account number (optional)').fill('')

  await page.getByRole('tab', { name: 'Document' }).click()
  await page.getByLabel('Quote header (optional)').fill('')
  await page.getByLabel('Quote footer (optional)').fill('')
  await page.getByLabel('Invoice header (optional)').fill('')
  await page.getByLabel('Invoice footer (optional)').fill('')
  await page.getByLabel('Expense header (optional)').fill('')
  await page.getByLabel('Expense footer (optional)').fill('')

  await page.getByRole('button', { name: 'Save settings' }).click()
  await expect(page.getByText('Saved.')).toBeVisible()

  await expect(page.getByLabel('Quote header (optional)')).toHaveValue('')

  await page.getByRole('tab', { name: 'User' }).click()
  await expect(page.getByLabel('Title (optional)')).toHaveValue('')

  await page.getByRole('tab', { name: 'Business' }).click()
  await expect(page.getByLabel('Address line 1 (optional)')).toHaveValue('')
  await expect(page.getByLabel('Postcode (optional)')).toHaveValue('')

  await page.getByRole('tab', { name: 'Payment and tax' }).click()
  await expect(page.getByLabel('UTR (optional)')).toHaveValue('')
  await expect(page.getByLabel('VAT number (optional)')).toHaveValue('')
  await expect(page.getByLabel('Bank account name (optional)')).toHaveValue('')
})

test('an address can be saved with only some lines filled in', async ({ authenticatedPage: page }) => {
  await page.goto('/settings')

  await page.getByLabel('First name').fill('Ada')
  await page.getByLabel('Last name').fill('Lovelace')

  await page.getByRole('tab', { name: 'Business' }).click()
  await page.getByLabel('Business name').fill('Partial Address Co')
  await page.getByLabel('Address line 1 (optional)').fill('1 Main St')
  await page.getByLabel('Address line 2 (optional)').fill('')
  await page.getByLabel('Town or city (optional)').fill('')
  await page.getByLabel('Postcode (optional)').fill('SW1A 1AA')
  await page.getByRole('button', { name: 'Save settings' }).click()

  await expect(page.getByText('Saved.')).toBeVisible()
  await expect(page.getByLabel('Address line 1 (optional)')).toHaveValue('1 Main St')
  await expect(page.getByLabel('Town or city (optional)')).toHaveValue('')
  await expect(page.getByLabel('Postcode (optional)')).toHaveValue('SW1A 1AA')
})

test('rejects a blank business name', async ({ authenticatedPage: page }) => {
  await page.goto('/settings')

  await page.getByLabel('First name').fill('Ada')
  await page.getByLabel('Last name').fill('Lovelace')
  await page.getByRole('tab', { name: 'Business' }).click()
  await page.getByLabel('Business name').fill('Temp Co')
  await page.getByRole('button', { name: 'Save settings' }).click()
  await expect(page.getByText('Saved.')).toBeVisible()

  // whitespace, not empty - the input has `required`, so an empty value
  // would never reach the server at all (blocked by browser validation);
  // this exercises the server's own non-blank-after-strip check instead.
  await page.getByLabel('Business name').fill('   ')
  await page.getByRole('button', { name: 'Save settings' }).click()
  await expect(page.getByRole('alert')).toContainText('business_name')
})

test('rejects a blank first name', async ({ authenticatedPage: page }) => {
  await page.goto('/settings')

  await page.getByLabel('First name').fill('Ada')
  await page.getByLabel('Last name').fill('Lovelace')
  await page.getByRole('tab', { name: 'Business' }).click()
  await page.getByLabel('Business name').fill('Temp Co')
  await page.getByRole('button', { name: 'Save settings' }).click()
  await expect(page.getByText('Saved.')).toBeVisible()

  await page.getByRole('tab', { name: 'User' }).click()
  await page.getByLabel('First name').fill('   ')
  await page.getByRole('button', { name: 'Save settings' }).click()
  await expect(page.getByRole('alert')).toContainText('first_name')
})
