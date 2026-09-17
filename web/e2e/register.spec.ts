import { expect, test } from './fixtures'

test('visiting /register with no token shows an invalid-link message, not a form', async ({ page }) => {
  await page.goto('/register')
  await expect(page.getByText('This registration link is invalid or has expired.')).toBeVisible()
  await expect(page.getByLabel('Email')).toHaveCount(0)
})

test('visiting /register with an unknown token shows the same invalid-link message', async ({ page }) => {
  await page.goto('/register?token=not-a-real-token')
  await expect(page.getByText('This registration link is invalid or has expired.')).toBeVisible()
  await expect(page.getByLabel('Email')).toHaveCount(0)
})

test('a valid invite shows the form, and registering redirects to login where the new credentials work', async ({
  page,
  inviteToken,
}, testInfo) => {
  const email = `registered-${testInfo.testId}@example.test`
  const password = 'correct horse battery staple'

  await page.goto(`/register?token=${inviteToken}`)
  await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()

  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByLabel('Confirm password').fill(password)
  await page.getByRole('button', { name: 'Create account' }).click()

  // Redirect to login, not auto-login.
  await expect(page.getByLabel('Email')).toBeVisible()
  await expect(page).toHaveURL('/login')

  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('heading', { name: 'Home' })).toBeVisible()
})

test('mismatched passwords are rejected client-side without calling the API', async ({ page, inviteToken }) => {
  await page.goto(`/register?token=${inviteToken}`)
  await page.getByLabel('Email').fill('mismatch@example.test')
  await page.getByLabel('Password', { exact: true }).fill('correct horse battery staple')
  await page.getByLabel('Confirm password').fill('a different password')
  await page.getByRole('button', { name: 'Create account' }).click()
  await expect(page.getByText('Passwords do not match')).toBeVisible()

  // The invite is still unused - still shows the form on a fresh visit.
  await page.goto(`/register?token=${inviteToken}`)
  await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()
})

test('a consumed invite cannot be reused', async ({ page, inviteToken }, testInfo) => {
  const email = `consumed-${testInfo.testId}@example.test`
  const password = 'correct horse battery staple'

  await page.goto(`/register?token=${inviteToken}`)
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByLabel('Confirm password').fill(password)
  await page.getByRole('button', { name: 'Create account' }).click()
  await expect(page).toHaveURL('/login')

  await page.goto(`/register?token=${inviteToken}`)
  await expect(page.getByText('This registration link is invalid or has expired.')).toBeVisible()
})
