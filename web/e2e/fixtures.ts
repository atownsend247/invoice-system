import { test as base, expect, type Page } from '@playwright/test'
import { TOKEN_STORAGE_KEY } from '../src/auth/tokenStorageKey'
import { BACKEND_PORT, TEST_EMAIL, TEST_PASSWORD } from './constants'

export const API_BASE_URL = `http://127.0.0.1:${BACKEND_PORT}`

export interface ApiAccount {
  id: number
  business_name: string
}

export interface ApiQuote {
  id: number
  number: string | null
  account_id: number
}

export interface ApiInvoice {
  id: number
  number: string | null
  quote_id: number | null
}

// Plain fetch, not Playwright's `request` fixture - these calls happen from
// a worker-scoped fixture (apiToken), which can't depend on a test-scoped
// one, and Node has fetch natively (see CLAUDE.md's Node version gotchas).
async function apiFetch<T>(path: string, token: string | null, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body !== undefined) headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers })
  if (!response.ok) {
    throw new Error(`${init.method ?? 'GET'} ${path} -> ${response.status}: ${await response.text()}`)
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T)
}

interface TestFixtures {
  authenticatedPage: Page
  testAccount: ApiAccount
  draftQuote: ApiQuote
  sentQuote: ApiQuote
  draftInvoice: ApiInvoice
  sentInvoice: ApiInvoice
}

interface WorkerFixtures {
  apiToken: string
}

/**
 * Each fixture below sets up backend state directly through the API, not
 * the UI - a spec only drives the UI for the feature it's actually testing
 * (e.g. quotes.spec.ts exercises the send/convert UI starting from a
 * `draftQuote`; invoices.spec.ts doesn't re-do that pipeline, it starts
 * from `draftInvoice`). This also means every test gets its own account/
 * quote, so specs don't depend on each other or on execution order.
 */
export const test = base.extend<TestFixtures, WorkerFixtures>({
  // One login per worker (Argon2 verification isn't free), not per test -
  // a session token is safe to reuse across this worker's tests.
  apiToken: [
    async ({}, use) => {
      const { token } = await apiFetch<{ token: string }>('/auth/login', null, {
        method: 'POST',
        body: JSON.stringify({ email: TEST_EMAIL, password: TEST_PASSWORD }),
      })
      await use(token)
    },
    { scope: 'worker' },
  ],

  authenticatedPage: async ({ page, apiToken }, use) => {
    await page.addInitScript(
      ({ key, token }) => window.localStorage.setItem(key, token),
      { key: TOKEN_STORAGE_KEY, token: apiToken },
    )
    await use(page)
  },

  testAccount: async ({ apiToken }, use, testInfo) => {
    // testId first, not appended - a long test title would otherwise push it
    // past any length cap and two repeat/retry runs of the same test would
    // collide on an identical, truncated business_name (found by stress-
    // testing this fixture with --repeat-each before trusting it).
    const suffix = testInfo.testId
    const account = await apiFetch<ApiAccount>('/accounts', apiToken, {
      method: 'POST',
      body: JSON.stringify({
        business_name: `${suffix} ${testInfo.title}`,
        email: `e2e-${suffix}@example.test`,
        address: '1 Test Street',
      }),
    })
    await use(account)
  },

  draftQuote: async ({ apiToken, testAccount }, use) => {
    const quote = await apiFetch<ApiQuote>('/quotes', apiToken, {
      method: 'POST',
      body: JSON.stringify({ account_id: testAccount.id, currency: 'USD' }),
    })
    await use(quote)
  },

  sentQuote: async ({ apiToken, draftQuote }, use) => {
    await apiFetch(`/quotes/${draftQuote.id}/line-items`, apiToken, {
      method: 'POST',
      body: JSON.stringify({ description: 'Setup work', quantity: '1', unit_price: '100.00' }),
    })
    const sent = await apiFetch<ApiQuote>(`/quotes/${draftQuote.id}/send`, apiToken, { method: 'POST' })
    await use(sent)
  },

  draftInvoice: async ({ apiToken, sentQuote }, use) => {
    const invoice = await apiFetch<ApiInvoice>(`/quotes/${sentQuote.id}/convert`, apiToken, {
      method: 'POST',
    })
    await use(invoice)
  },

  sentInvoice: async ({ apiToken, draftInvoice }, use) => {
    const sent = await apiFetch<ApiInvoice>(`/invoices/${draftInvoice.id}/send`, apiToken, {
      method: 'POST',
    })
    await use(sent)
  },
})

export { expect }
