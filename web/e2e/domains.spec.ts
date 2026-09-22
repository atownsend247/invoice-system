import { apiFetch, expect, test } from './fixtures'

test('adding, editing, and deleting a domain', async ({ authenticatedPage: page, apiToken }, testInfo) => {
  // The Registrar field is a strict <select> sourced from the managed
  // Registrar list (see CLAUDE.md/DomainForm.tsx), not free text - create
  // two via the API first, uniquely named per test run (registrars are a
  // shared organisation-wide list, same reasoning as testAccount's own
  // business_name in fixtures.ts).
  const registrarA = `${testInfo.testId} 123-Reg`
  const registrarB = `${testInfo.testId} GoDaddy`
  await apiFetch('/registrars', apiToken, { method: 'POST', body: JSON.stringify({ name: registrarA }) })
  await apiFetch('/registrars', apiToken, { method: 'POST', body: JSON.stringify({ name: registrarB }) })

  const domainName = `${testInfo.testId}-example.test`
  const renamedDomain = `${testInfo.testId}-example.co.uk`

  await page.goto('/domains')
  await expect(page.getByRole('heading', { name: 'Domains' })).toBeVisible()

  await page.getByRole('button', { name: 'Add domain' }).click()
  await page.getByLabel('Domain name').fill(domainName)
  await page.getByLabel('Expiry date').fill('2027-06-15')
  await page.getByLabel('Registrar').selectOption(registrarA)
  await page.getByLabel('Auto-renew').check()
  // exact: true - otherwise a substring match against "Add registrar"
  // too (the Registrars section's own button, on the same page).
  await page.getByRole('button', { name: 'Add', exact: true }).click()

  const row = page.locator('tbody tr', { hasText: domainName })
  await expect(row).toContainText('2027-06-15')
  await expect(row).toContainText(registrarA)
  await expect(row).toContainText('Yes')
  // Created here, not linked from an account - unlinked by default (see
  // CLAUDE.md).
  await expect(row).toContainText('Unlinked')

  await row.getByRole('button', { name: 'Edit' }).click()
  await page.getByLabel('Domain name').fill(renamedDomain)
  await page.getByLabel('Registrar').selectOption(registrarB)
  await page.getByLabel('Auto-renew').uncheck()
  await page.getByRole('button', { name: 'Save' }).click()

  const updatedRow = page.locator('tbody tr', { hasText: renamedDomain })
  await expect(updatedRow).toContainText(registrarB)
  await expect(updatedRow).toContainText('No')
  await expect(page.getByText(domainName, { exact: true })).toHaveCount(0)

  await updatedRow.getByRole('button', { name: 'Delete' }).click()
  await expect(page.getByText(renamedDomain)).toHaveCount(0)
})

test('the Domains page shows and links to the account a domain is linked to', async ({
  authenticatedPage: page,
  testAccount,
  apiToken,
}, testInfo) => {
  const domainName = `${testInfo.testId}-example.test`
  const domainId = await apiFetch<{ id: string }>('/domains', apiToken, {
    method: 'POST',
    body: JSON.stringify({ domain_name: domainName, expiry_date: '2027-01-01', registrar: '123-Reg' }),
  }).then((d) => d.id)
  await apiFetch(`/domains/${domainId}/link`, apiToken, {
    method: 'POST',
    body: JSON.stringify({ account_id: testAccount.id }),
  })

  await page.goto('/domains')
  const row = page.locator('tbody tr', { hasText: domainName })
  const link = row.getByRole('link', { name: testAccount.business_name })
  await expect(link).toBeVisible()
  await link.click()
  await expect(page).toHaveURL(`/accounts/${testAccount.id}`)
})

test('adding, editing, and deleting a registrar', async ({ authenticatedPage: page }, testInfo) => {
  // Unique per test (same reasoning as testAccount's own business_name in
  // fixtures.ts) - registrars are a shared organisation-wide list, so a
  // fixed name would collide across repeated runs of this same spec.
  const name = `${testInfo.testId} 123-Reg`
  const renamed = `${testInfo.testId} GoDaddy`

  await page.goto('/domains')

  await page.getByRole('button', { name: 'Add registrar' }).click()
  // exact: true - "Name" is otherwise a substring match against "Domain
  // name" in the Domains section's own add form above.
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

test('registrar list shows domain/account counts and blocks deleting one still in use', async ({
  authenticatedPage: page,
  testAccount,
  apiToken,
}, testInfo) => {
  const name = `${testInfo.testId} GoDaddy`

  await page.goto('/domains')
  await page.getByRole('button', { name: 'Add registrar' }).click()
  await page.getByLabel('Name', { exact: true }).fill(name)
  await page.getByRole('button', { name: 'Add', exact: true }).click()

  // Scoped to the Registrars group specifically - once the domain below
  // exists, its own row also contains this registrar's name (in its
  // "Registrar" column), which would otherwise make an unscoped
  // page-wide row lookup ambiguous.
  const registrarsGroup = page.getByRole('group', { name: 'Registrars' })
  const row = registrarsGroup.locator('tbody tr', { hasText: name })
  await expect(row).toContainText('No domains')
  await expect(row.getByRole('button', { name: 'Delete' })).toBeEnabled()

  await apiFetch('/domains', apiToken, {
    method: 'POST',
    body: JSON.stringify({
      domain_name: 'example.test',
      expiry_date: '2027-01-01',
      registrar: name,
      account_id: testAccount.id,
    }),
  })

  await page.reload()
  const rowAfter = registrarsGroup.locator('tbody tr', { hasText: name })
  await expect(rowAfter).toContainText('1 domain (1 account)')

  // Blocked client-side (a disabled button with an explanatory title),
  // not just server-side - see CLAUDE.md's RegistrarService.delete_registrar.
  const deleteButton = rowAfter.getByRole('button', { name: 'Delete' })
  await expect(deleteButton).toBeDisabled()
  await expect(deleteButton).toHaveAttribute('title', /still used by 1 domain/i)
})
