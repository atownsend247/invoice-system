import { expect, test } from './fixtures'

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
  await page.getByLabel('Quote header (optional)').fill('Contoso Consulting')
  await page.getByLabel('Quote footer (optional)').fill('Valid for 30 days.')
  await page.getByLabel('Invoice header (optional)').fill('Contoso Consulting\nCompany no. 12345678')
  await page.getByLabel('Invoice footer (optional)').fill('Thank you for your business!')
  await page.getByLabel('Expense header (optional)').fill('Contoso Consulting')
  await page.getByLabel('Expense footer (optional)').fill('Internal use only.')

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
  await expect(page.getByLabel('Quote header (optional)')).toHaveValue('Contoso Consulting')
  await expect(page.getByLabel('Quote footer (optional)')).toHaveValue('Valid for 30 days.')
  await expect(page.getByLabel('Invoice header (optional)')).toHaveValue(
    'Contoso Consulting\nCompany no. 12345678',
  )
  await expect(page.getByLabel('Invoice footer (optional)')).toHaveValue('Thank you for your business!')
  await expect(page.getByLabel('Expense header (optional)')).toHaveValue('Contoso Consulting')
  await expect(page.getByLabel('Expense footer (optional)')).toHaveValue('Internal use only.')
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
