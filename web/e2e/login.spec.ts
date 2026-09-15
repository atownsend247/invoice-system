import { TEST_EMAIL, TEST_PASSWORD } from './constants'
import { expect, test } from './fixtures'

test('redirects to login when logged out', async ({ page }) => {
  await page.goto('/accounts')
  await expect(page.getByRole('heading', { name: 'Invoice System' })).toBeVisible()
  await expect(page.getByLabel('Email')).toBeVisible()
})

test('bad credentials show an error and stay on the login page', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('Email').fill(TEST_EMAIL)
  await page.getByLabel('Password').fill('wrong password')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('alert')).toContainText('incorrect email or password')
})

test('successful login lands on Home, and logout really ends the session', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('Email').fill(TEST_EMAIL)
  await page.getByLabel('Password').fill(TEST_PASSWORD)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('heading', { name: 'Home' })).toBeVisible()

  await page.getByRole('button', { name: 'Log out' }).click()
  await expect(page.getByRole('heading', { name: 'Invoice System' })).toBeVisible()

  // not just a client-side route change - the token itself must be gone
  await page.goto('/accounts')
  await expect(page.getByLabel('Email')).toBeVisible()
})
