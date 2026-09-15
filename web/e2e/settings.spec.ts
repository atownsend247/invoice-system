import { expect, test } from './fixtures'

// The shared test user's profile - not per-test isolated data like
// testAccount, since a business profile is a singleton per user rather
// than a created-per-test record. Tests within this file run in one worker
// (fullyParallel: false), so they don't race each other; each still sets
// its own known values up front rather than assuming a starting state.

test('loads the current profile into the form on visit', async ({ authenticatedPage: page }) => {
  // Not asserting a specific "default" value here - a business profile is a
  // singleton per user (see CLAUDE.md), and this spec shares its login user
  // with every other test in this file (and, under --repeat-each, with
  // earlier runs of itself), so "untouched" only holds the very first time
  // ever. What's actually being verified is that the GET wired up and the
  // form populated, not stuck empty/loading - found by stress-testing this
  // spec with --repeat-each before trusting it (same lesson as accounts.spec.ts).
  await page.goto('/settings')
  await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible()
  await expect(page.getByLabel('Payment terms (days)')).not.toHaveValue('')
})

test('saving all fields persists them across a reload', async ({ authenticatedPage: page }) => {
  await page.goto('/settings')

  await page.getByLabel('Title (optional)').fill('Dr')
  await page.getByLabel('First name').fill('Ada')
  await page.getByLabel('Last name').fill('Lovelace')
  await page.getByLabel('Business name').fill('Contoso Consulting')
  await page.getByLabel('Business address (optional)').fill('1 Market Street, London')
  await page.getByLabel('Payment terms (days)').fill('14')
  await page.getByLabel('UTR (optional)').fill('1234567890')
  await page.getByLabel('VAT number (optional)').fill('GB123456789')
  await page.getByRole('button', { name: 'Save settings' }).click()

  await expect(page.getByText('Saved.')).toBeVisible()

  await page.reload()
  await expect(page.getByLabel('Title (optional)')).toHaveValue('Dr')
  await expect(page.getByLabel('First name')).toHaveValue('Ada')
  await expect(page.getByLabel('Last name')).toHaveValue('Lovelace')
  await expect(page.getByLabel('Business name')).toHaveValue('Contoso Consulting')
  await expect(page.getByLabel('Business address (optional)')).toHaveValue('1 Market Street, London')
  await expect(page.getByLabel('Payment terms (days)')).toHaveValue('14')
  await expect(page.getByLabel('UTR (optional)')).toHaveValue('1234567890')
  await expect(page.getByLabel('VAT number (optional)')).toHaveValue('GB123456789')
})

test('title, business address, UTR and VAT number can all be left blank', async ({
  authenticatedPage: page,
}) => {
  await page.goto('/settings')

  await page.getByLabel('First name').fill('Ada')
  await page.getByLabel('Last name').fill('Lovelace')
  await page.getByLabel('Business name').fill('Sole Trader Co')
  await page.getByLabel('Title (optional)').fill('')
  await page.getByLabel('Business address (optional)').fill('')
  await page.getByLabel('UTR (optional)').fill('')
  await page.getByLabel('VAT number (optional)').fill('')
  await page.getByRole('button', { name: 'Save settings' }).click()

  await expect(page.getByText('Saved.')).toBeVisible()
  await expect(page.getByLabel('Title (optional)')).toHaveValue('')
  await expect(page.getByLabel('Business address (optional)')).toHaveValue('')
  await expect(page.getByLabel('UTR (optional)')).toHaveValue('')
  await expect(page.getByLabel('VAT number (optional)')).toHaveValue('')
})

test('rejects a blank business name', async ({ authenticatedPage: page }) => {
  await page.goto('/settings')

  await page.getByLabel('First name').fill('Ada')
  await page.getByLabel('Last name').fill('Lovelace')
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
  await page.getByLabel('Business name').fill('Temp Co')
  await page.getByRole('button', { name: 'Save settings' }).click()
  await expect(page.getByText('Saved.')).toBeVisible()

  await page.getByLabel('First name').fill('   ')
  await page.getByRole('button', { name: 'Save settings' }).click()
  await expect(page.getByRole('alert')).toContainText('first_name')
})
