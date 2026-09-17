import { expect, test } from './fixtures'

// The toggle button's accessible name flips between the two ("Switch to
// dark/light mode") rather than staying fixed, so it always describes the
// action a click will take, not the current state.

test('the theme toggle switches between light and dark and persists across a reload', async ({
  authenticatedPage: page,
}) => {
  await page.goto('/')
  // Wait for the app to mount (and its theme effect to run) before reading
  // the attribute - evaluate() can otherwise run ahead of React rendering,
  // finding no data-theme attribute set yet (caught by --repeat-each
  // stress-testing, not a single run - same race as the reload check below).
  const toggle = page.getByRole('button', { name: /Switch to (dark|light) mode/ })
  await toggle.waitFor()

  const initialTheme = await page.evaluate(() => document.documentElement.dataset.theme)
  expect(['light', 'dark']).toContain(initialTheme)

  await toggle.click()

  const toggledTheme = await page.evaluate(() => document.documentElement.dataset.theme)
  expect(toggledTheme).not.toBe(initialTheme)

  await page.reload()
  // Wait for the app to mount (and its theme effect to run) before reading
  // the attribute back - evaluate() runs immediately on the fresh document,
  // ahead of React rendering.
  await page.getByRole('button', { name: /Switch to (dark|light) mode/ }).waitFor()
  await expect(page.evaluate(() => document.documentElement.dataset.theme)).resolves.toBe(toggledTheme)
})

test('the settings icon button still links to the settings page', async ({ authenticatedPage: page }) => {
  await page.goto('/')
  await page.getByRole('link', { name: 'Settings' }).click()
  await expect(page).toHaveURL('/settings')
})
