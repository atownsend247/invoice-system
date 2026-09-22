import type {
  Account,
  BusinessProfile,
  Domain,
  Expense,
  ExpenseAttachment,
  Invoice,
  InvoiceStatus,
  LoginResult,
  MonthlyExpenseTotalsReport,
  MonthlyTotalsReport,
  PagedResult,
  Quote,
  QuoteStatus,
  Registrar,
  Stats,
  User,
} from './types'

const DEFAULT_API_PORT = 8000

/** Same host the page itself was loaded from, not a hardcoded loopback -
 * so `npm run dev:lan` (see CLAUDE.md) works from another device on the
 * network without also having to set VITE_API_BASE_URL by hand: loading
 * the app from http://192.168.1.23:5173 talks to the API at
 * http://192.168.1.23:8000 automatically (as long as the API was also
 * started with --host 0.0.0.0). localhost/127.0.0.1 keep the literal
 * 127.0.0.1 default rather than window.location.hostname, since
 * "localhost" can resolve to the IPv6 loopback first on some systems (see
 * CLAUDE.md gotchas) and uvicorn's own default only binds the IPv4 one. */
export function defaultApiBaseUrl(): string {
  const { hostname, protocol } = window.location
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return `http://127.0.0.1:${DEFAULT_API_PORT}`
  }
  return `${protocol}//${hostname}:${DEFAULT_API_PORT}`
}

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? defaultApiBaseUrl()

export class ApiError extends Error {
  status: number

  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
  }
}

let authToken: string | null = null
let onUnauthorized: (() => void) | null = null

/** Called by AuthContext once, after reading/writing the token to localStorage. */
export function setAuthToken(token: string | null): void {
  authToken = token
}

/** Called by AuthContext to react to any 401 from any call, in one place. */
export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body !== undefined) headers.set('Content-Type', 'application/json')
  if (authToken) headers.set('Authorization', `Bearer ${authToken}`)

  const response = await fetch(`${BASE_URL}${path}`, { ...options, headers })

  if (response.status === 401 && path !== '/auth/login') {
    onUnauthorized?.()
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string }
    throw new ApiError(response.status, body.detail ?? response.statusText)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

async function requestBlob(path: string): Promise<Blob> {
  const headers = new Headers()
  if (authToken) headers.set('Authorization', `Bearer ${authToken}`)
  const response = await fetch(`${BASE_URL}${path}`, { headers })
  if (response.status === 401) onUnauthorized?.()
  if (!response.ok) throw new ApiError(response.status, response.statusText)
  return response.blob()
}

/** Uploads a file as multipart/form-data - deliberately not `request()`,
 * which always sets Content-Type: application/json for any request with a
 * body. A multipart request needs the browser to set its own Content-Type
 * (with the boundary it generates for this exact FormData), so this never
 * touches that header itself, only Authorization. */
async function uploadFile<T>(path: string, file: File): Promise<T> {
  const headers = new Headers()
  if (authToken) headers.set('Authorization', `Bearer ${authToken}`)
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(`${BASE_URL}${path}`, { method: 'POST', body: formData, headers })
  if (response.status === 401) onUnauthorized?.()
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string }
    throw new ApiError(response.status, body.detail ?? response.statusText)
  }
  return (await response.json()) as T
}

/** Fetches a PDF and hands it to the browser as a download - a plain <a href>
 * can't carry the Authorization header these routes require. */
export async function downloadPdf(path: string, filename: string): Promise<void> {
  const blob = await requestBlob(path)
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

/** Builds a query string from a set of optional params, dropping any that
 * are undefined/blank - shared by the paginated/filterable list endpoints
 * below so each one only has to say which params it has, not repeat the
 * "skip absent ones" logic three times. */
function buildQuery(params: Record<string, string | number | undefined>): string {
  const entries = Object.entries(params).filter(
    (entry): entry is [string, string | number] => entry[1] !== undefined && entry[1] !== '',
  )
  if (entries.length === 0) return ''
  return `?${new URLSearchParams(entries.map(([key, value]) => [key, String(value)])).toString()}`
}

/** Fetches a PDF and returns an object URL for it, for PdfViewerModal to
 * show in an in-page <iframe> - not a new browser tab. A new tab was the
 * first approach tried here, but modern Chromium refuses to top-level-
 * navigate a *different* browsing context (a new tab/window, via
 * window.open or a target="_blank" click, with or without 'noopener') to a
 * blob: URL created by another one - confirmed by testing window.open with
 * a synchronous reservation + deferred `location.href`, and a synthetic
 * <a target="_blank"> click; both leave the new tab stuck on about:blank
 * (or a blank page entirely) forever, not a popup-blocker or timing issue.
 * A blob: URL works perfectly fine as an <iframe src> *within the same
 * document* that created it, which is what PdfViewerModal relies on -
 * revoke the URL (via URL.revokeObjectURL) once the modal closes. */
export async function getPdfObjectUrl(path: string): Promise<string> {
  const blob = await requestBlob(path)
  return URL.createObjectURL(blob)
}

// -- auth --------------------------------------------------------------

export function login(email: string, password: string, otp?: string): Promise<LoginResult> {
  return request('/auth/login', { method: 'POST', body: JSON.stringify({ email, password, otp }) })
}

export function me(): Promise<User> {
  return request('/auth/me')
}

export function logout(): Promise<void> {
  return request('/auth/logout', { method: 'POST' })
}

/** Checks an invite token from a `/register?token=` link is still valid
 * (unknown/expired/already-used all fail the same way, deliberately - see
 * CLAUDE.md) - called on page load so RegisterPage can show an error
 * immediately rather than only at submit time. */
export function checkRegistrationInvite(token: string): Promise<{ valid: boolean }> {
  return request(`/auth/register/validate?${new URLSearchParams({ token }).toString()}`)
}

/** Registration itself always re-validates the token server-side
 * regardless of the check above - a token could expire or get consumed
 * by someone else in between. No auto-login on success - the caller
 * redirects to /login instead (see RegisterPage.tsx). */
export function register(token: string, email: string, password: string): Promise<User> {
  return request('/auth/register', { method: 'POST', body: JSON.stringify({ token, email, password }) })
}

// -- accounts ------------------------------------------------------------

export interface ListAccountsOptions {
  query?: string
  page?: number
  pageSize?: number
}

export function listAccounts(options: ListAccountsOptions = {}): Promise<PagedResult<Account>> {
  const search = buildQuery({ query: options.query, page: options.page, page_size: options.pageSize })
  return request(`/accounts${search}`)
}

export function getAccount(id: string): Promise<Account> {
  return request(`/accounts/${id}`)
}

export interface CreateAccountInput {
  business_name: string
  email: string
  address_line1: string
  contact_name?: string
  phone?: string
  address_line2?: string
  town_or_city?: string
  county?: string
  postcode?: string
}

export function createAccount(input: CreateAccountInput): Promise<Account> {
  return request('/accounts', { method: 'POST', body: JSON.stringify(input) })
}

export function updateAccount(id: string, input: CreateAccountInput): Promise<Account> {
  return request(`/accounts/${id}`, { method: 'PUT', body: JSON.stringify(input) })
}

// -- domains -----------------------------------------------------------------

export interface SaveDomainInput {
  domain_name: string
  expiry_date: string
  registrar: string
  auto_renew: boolean
}

// Only meaningful on create - a domain can be created unlinked (omit this)
// and linked later via linkDomain. Editing (updateDomain) never touches
// the link - see CLAUDE.md.
export interface CreateDomainInput extends SaveDomainInput {
  account_id?: string
}

export function listDomains(params?: { accountId?: string }): Promise<Domain[]> {
  const query = params?.accountId ? `?account_id=${params.accountId}` : ''
  return request(`/domains${query}`)
}

export function createDomain(input: CreateDomainInput): Promise<Domain> {
  return request('/domains', { method: 'POST', body: JSON.stringify(input) })
}

export function updateDomain(domainId: string, input: SaveDomainInput): Promise<Domain> {
  return request(`/domains/${domainId}`, { method: 'PUT', body: JSON.stringify(input) })
}

export function deleteDomain(domainId: string): Promise<void> {
  return request(`/domains/${domainId}`, { method: 'DELETE' })
}

export function linkDomain(domainId: string, accountId: string): Promise<Domain> {
  return request(`/domains/${domainId}/link`, {
    method: 'POST',
    body: JSON.stringify({ account_id: accountId }),
  })
}

export function unlinkDomain(domainId: string): Promise<Domain> {
  return request(`/domains/${domainId}/unlink`, { method: 'POST' })
}

// -- registrars ----------------------------------------------------------------

export interface SaveRegistrarInput {
  name: string
  notes?: string
}

export function listRegistrars(): Promise<Registrar[]> {
  return request('/registrars')
}

export function createRegistrar(input: SaveRegistrarInput): Promise<Registrar> {
  return request('/registrars', { method: 'POST', body: JSON.stringify(input) })
}

export function updateRegistrar(id: string, input: SaveRegistrarInput): Promise<Registrar> {
  return request(`/registrars/${id}`, { method: 'PUT', body: JSON.stringify(input) })
}

export function deleteRegistrar(id: string): Promise<void> {
  return request(`/registrars/${id}`, { method: 'DELETE' })
}

// -- quotes ----------------------------------------------------------------

export interface ListQuotesOptions {
  accountId?: string
  accountName?: string
  status?: QuoteStatus
  page?: number
  pageSize?: number
}

export function listQuotes(options: ListQuotesOptions = {}): Promise<PagedResult<Quote>> {
  const search = buildQuery({
    account_id: options.accountId,
    account_name: options.accountName,
    status: options.status,
    page: options.page,
    page_size: options.pageSize,
  })
  return request(`/quotes${search}`)
}

export function getQuote(id: string): Promise<Quote> {
  return request(`/quotes/${id}`)
}

export function createQuote(accountId: string, currency = 'USD', issueDate?: string): Promise<Quote> {
  return request('/quotes', {
    method: 'POST',
    body: JSON.stringify({ account_id: accountId, currency, issue_date: issueDate || undefined }),
  })
}

export function updateQuote(
  quoteId: string,
  input: { currency: string; issue_date: string },
): Promise<Quote> {
  return request(`/quotes/${quoteId}`, { method: 'PUT', body: JSON.stringify(input) })
}

export function addQuoteLineItem(
  quoteId: string,
  input: { description: string; quantity: string; unit_price: string; tax_rate?: string },
): Promise<Quote> {
  return request(`/quotes/${quoteId}/line-items`, { method: 'POST', body: JSON.stringify(input) })
}

export function updateQuoteLineItem(
  quoteId: string,
  itemId: string,
  input: { description: string; quantity: string; unit_price: string; tax_rate?: string },
): Promise<Quote> {
  return request(`/quotes/${quoteId}/line-items/${itemId}`, { method: 'PUT', body: JSON.stringify(input) })
}

export function deleteQuoteLineItem(quoteId: string, itemId: string): Promise<Quote> {
  return request(`/quotes/${quoteId}/line-items/${itemId}`, { method: 'DELETE' })
}

export function sendQuote(id: string): Promise<Quote> {
  return request(`/quotes/${id}/send`, { method: 'POST' })
}

export function convertQuote(id: string, issueDate?: string): Promise<Invoice> {
  return request(`/quotes/${id}/convert`, {
    method: 'POST',
    body: JSON.stringify({ issue_date: issueDate || undefined }),
  })
}

export function downloadQuotePdf(quote: Quote): Promise<void> {
  return downloadPdf(`/quotes/${quote.id}/pdf`, `${quote.number ?? `quote-${quote.id}`}.pdf`)
}

export function getQuotePdfUrl(quote: Quote): Promise<string> {
  return getPdfObjectUrl(`/quotes/${quote.id}/pdf`)
}

// -- invoices --------------------------------------------------------------

export interface ListInvoicesOptions {
  accountId?: string
  accountName?: string
  status?: InvoiceStatus
  quoteId?: string
  page?: number
  pageSize?: number
}

export function listInvoices(options: ListInvoicesOptions = {}): Promise<PagedResult<Invoice>> {
  const search = buildQuery({
    account_id: options.accountId,
    account_name: options.accountName,
    status: options.status,
    quote_id: options.quoteId,
    page: options.page,
    page_size: options.pageSize,
  })
  return request(`/invoices${search}`)
}

export function getInvoice(id: string): Promise<Invoice> {
  return request(`/invoices/${id}`)
}

export function sendInvoice(id: string): Promise<Invoice> {
  return request(`/invoices/${id}/send`, { method: 'POST' })
}

export function voidInvoice(id: string): Promise<Invoice> {
  return request(`/invoices/${id}/void`, { method: 'POST' })
}

export function payInvoice(id: string): Promise<Invoice> {
  return request(`/invoices/${id}/pay`, { method: 'POST' })
}

export function getMonthlyInvoiceTotals(): Promise<MonthlyTotalsReport> {
  return request('/invoices/monthly-totals')
}

export function downloadInvoicePdf(invoice: Invoice): Promise<void> {
  return downloadPdf(`/invoices/${invoice.id}/pdf`, `${invoice.number ?? `invoice-${invoice.id}`}.pdf`)
}

export function getInvoicePdfUrl(invoice: Invoice): Promise<string> {
  return getPdfObjectUrl(`/invoices/${invoice.id}/pdf`)
}

// -- expenses ----------------------------------------------------------------

export function listExpenses(accountId?: string): Promise<Expense[]> {
  const query = accountId ? `?account_id=${accountId}` : ''
  return request(`/expenses${query}`)
}

export function getExpense(id: string): Promise<Expense> {
  return request(`/expenses/${id}`)
}

export function createExpense(
  accountId: string,
  currency = 'USD',
  expenseDate?: string,
): Promise<Expense> {
  return request('/expenses', {
    method: 'POST',
    body: JSON.stringify({ account_id: accountId, currency, expense_date: expenseDate || undefined }),
  })
}

export function updateExpenseDate(expenseId: string, expenseDate: string): Promise<Expense> {
  return request(`/expenses/${expenseId}/expense-date`, {
    method: 'PUT',
    body: JSON.stringify({ expense_date: expenseDate }),
  })
}

export function addExpenseLineItem(
  expenseId: string,
  input: { description: string; quantity: string; unit_price: string; tax_rate?: string },
): Promise<Expense> {
  return request(`/expenses/${expenseId}/line-items`, { method: 'POST', body: JSON.stringify(input) })
}

export function updateExpenseLineItem(
  expenseId: string,
  itemId: string,
  input: { description: string; quantity: string; unit_price: string; tax_rate?: string },
): Promise<Expense> {
  return request(`/expenses/${expenseId}/line-items/${itemId}`, {
    method: 'PUT',
    body: JSON.stringify(input),
  })
}

export function deleteExpenseLineItem(expenseId: string, itemId: string): Promise<Expense> {
  return request(`/expenses/${expenseId}/line-items/${itemId}`, { method: 'DELETE' })
}

export function downloadExpensePdf(expense: Expense): Promise<void> {
  return downloadPdf(`/expenses/${expense.id}/pdf`, `${expense.number}.pdf`)
}

export function getExpensePdfUrl(expense: Expense): Promise<string> {
  return getPdfObjectUrl(`/expenses/${expense.id}/pdf`)
}

export function uploadExpenseAttachment(expenseId: string, file: File): Promise<ExpenseAttachment> {
  return uploadFile(`/expenses/${expenseId}/attachments`, file)
}

export function deleteExpenseAttachment(expenseId: string, attachmentId: string): Promise<void> {
  return request(`/expenses/${expenseId}/attachments/${attachmentId}`, { method: 'DELETE' })
}

export function downloadExpenseAttachment(expenseId: string, attachment: ExpenseAttachment): Promise<void> {
  return downloadPdf(`/expenses/${expenseId}/attachments/${attachment.id}`, attachment.filename)
}

export function getExpenseAttachmentPdfUrl(expenseId: string, attachmentId: string): Promise<string> {
  return getPdfObjectUrl(`/expenses/${expenseId}/attachments/${attachmentId}`)
}

export function getMonthlyExpenseTotals(): Promise<MonthlyExpenseTotalsReport> {
  return request('/expenses/monthly-totals')
}

// -- settings ----------------------------------------------------------------

export function getBusinessProfile(): Promise<BusinessProfile> {
  return request('/settings/business-profile')
}

export interface SaveBusinessProfileInput {
  first_name: string
  last_name: string
  business_name: string
  payment_terms_days: number
  quote_validity_days: number
  currency: string
  title?: string
  address_line1?: string
  address_line2?: string
  town_or_city?: string
  county?: string
  postcode?: string
  utr?: string
  vat_number?: string
  bank_account_name?: string
  bank_sort_code?: string
  bank_account_number?: string
  quote_document_header?: string
  quote_document_footer?: string
  invoice_document_header?: string
  invoice_document_footer?: string
  expense_document_header?: string
  expense_document_footer?: string
  quote_number_prefix?: string
  quote_number_digits?: number
  invoice_number_prefix?: string
  invoice_number_digits?: number
  expense_number_prefix?: string
  expense_number_digits?: number
  accent_color?: string
}

export function saveBusinessProfile(input: SaveBusinessProfileInput): Promise<BusinessProfile> {
  return request('/settings/business-profile', { method: 'PUT', body: JSON.stringify(input) })
}

export function setNextQuoteNumber(nextNumber: number): Promise<void> {
  return request('/quotes/next-number', { method: 'POST', body: JSON.stringify({ next_number: nextNumber }) })
}

export function setNextInvoiceNumber(nextNumber: number): Promise<void> {
  return request('/invoices/next-number', {
    method: 'POST',
    body: JSON.stringify({ next_number: nextNumber }),
  })
}

export function setNextExpenseNumber(nextNumber: number): Promise<void> {
  return request('/expenses/next-number', {
    method: 'POST',
    body: JSON.stringify({ next_number: nextNumber }),
  })
}

// -- stats ----------------------------------------------------------------

export function getStats(): Promise<Stats> {
  return request('/stats')
}
