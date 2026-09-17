import { execFile } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { promisify } from 'node:util'
import { test as base, expect, type Page } from '@playwright/test'
import { TOKEN_STORAGE_KEY } from '../src/auth/tokenStorageKey'
import { BACKEND_PORT, TEST_EMAIL, TEST_PASSWORD } from './constants'

export const API_BASE_URL = `http://127.0.0.1:${BACKEND_PORT}`

const execFileAsync = promisify(execFile)

// Same repo-root/.tmp-storage-dir layout start-backend.sh computes from its
// own location (see that file) - registration invites are deliberately
// CLI-only, not an API route (see CLAUDE.md), so this is the only way to
// hand a test a valid one: shell out to the real CLI against the same
// storage this worker's backend is already running against, the same
// "set up state the HTTP API doesn't expose" pattern start-backend.sh
// itself uses (a `uv run python -c "..."` subprocess to seed the e2e login
// user, not an API call). No __dirname - this file is loaded as an ESM
// module, not CommonJS.
const dirname = path.dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = path.resolve(dirname, '../..')
const DATA_DIR = path.join(dirname, '.tmp')

async function createInviteToken(): Promise<string> {
  const { stdout } = await execFileAsync(
    'uv',
    ['run', 'invoice-system-cli', '--storage-dir', DATA_DIR, 'invite', 'create'],
    { cwd: REPO_ROOT },
  )
  const match = stdout.match(/Created invite (\S+)/)
  if (!match) throw new Error(`could not parse invite token from CLI output: ${stdout}`)
  return match[1]
}

export interface ApiAccount {
  id: string
  business_name: string
}

export interface ApiQuote {
  id: string
  number: string | null
  account_id: string
}

export interface ApiInvoice {
  id: string
  number: string | null
  quote_id: string | null
}

export interface ApiExpense {
  id: string
  number: string
  account_id: string
}

// Plain fetch, not Playwright's `request` fixture - these calls happen from
// a worker-scoped fixture (apiToken), which can't depend on a test-scoped
// one, and Node has fetch natively (see CLAUDE.md's Node version gotchas).
export async function apiFetch<T>(path: string, token: string | null, init: RequestInit = {}): Promise<T> {
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
  expense: ApiExpense
  reportingCurrency: string
  inviteToken: string
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
        address_line1: '1 Test Street',
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

  expense: async ({ apiToken, testAccount }, use) => {
    const expense = await apiFetch<ApiExpense>('/expenses', apiToken, {
      method: 'POST',
      body: JSON.stringify({ account_id: testAccount.id, currency: 'USD' }),
    })
    await use(expense)
  },

  // Read-only (GET, never PUT) deliberately - the business profile is a
  // singleton shared with settings.spec.ts (see CLAUDE.md), and a write
  // here would race with that file's own writes across workers. Tests that
  // need an invoice the monthly-totals chart will actually count use this
  // to learn the currency to create it in, rather than assuming one.
  reportingCurrency: async ({ apiToken }, use) => {
    const profile = await apiFetch<{ currency: string }>('/settings/business-profile', apiToken)
    await use(profile.currency)
  },

  // No `apiToken` dependency - creating an invite needs no login at all
  // (see CLAUDE.md), just the CLI against this worker's backend storage.
  inviteToken: async ({}, use) => {
    await use(await createInviteToken())
  },
})

export { expect }
