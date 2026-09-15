import type { Account, BusinessProfile, Invoice, LoginResult, Quote, User } from './types'

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://127.0.0.1:8000'

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

// -- accounts ------------------------------------------------------------

export function listAccounts(): Promise<Account[]> {
  return request('/accounts')
}

export function getAccount(id: number): Promise<Account> {
  return request(`/accounts/${id}`)
}

export interface CreateAccountInput {
  business_name: string
  email: string
  address: string
  contact_name?: string
  phone?: string
}

export function createAccount(input: CreateAccountInput): Promise<Account> {
  return request('/accounts', { method: 'POST', body: JSON.stringify(input) })
}

// -- quotes ----------------------------------------------------------------

export function listQuotes(accountId?: number): Promise<Quote[]> {
  const query = accountId ? `?account_id=${accountId}` : ''
  return request(`/quotes${query}`)
}

export function getQuote(id: number): Promise<Quote> {
  return request(`/quotes/${id}`)
}

export function createQuote(accountId: number, currency = 'USD'): Promise<Quote> {
  return request('/quotes', { method: 'POST', body: JSON.stringify({ account_id: accountId, currency }) })
}

export function addQuoteLineItem(
  quoteId: number,
  input: { description: string; quantity: string; unit_price: string },
): Promise<Quote> {
  return request(`/quotes/${quoteId}/line-items`, { method: 'POST', body: JSON.stringify(input) })
}

export function sendQuote(id: number): Promise<Quote> {
  return request(`/quotes/${id}/send`, { method: 'POST' })
}

export function convertQuote(id: number): Promise<Invoice> {
  return request(`/quotes/${id}/convert`, { method: 'POST' })
}

export function downloadQuotePdf(quote: Quote): Promise<void> {
  return downloadPdf(`/quotes/${quote.id}/pdf`, `${quote.number ?? `quote-${quote.id}`}.pdf`)
}

// -- invoices --------------------------------------------------------------

export function listInvoices(accountId?: number): Promise<Invoice[]> {
  const query = accountId ? `?account_id=${accountId}` : ''
  return request(`/invoices${query}`)
}

export function getInvoice(id: number): Promise<Invoice> {
  return request(`/invoices/${id}`)
}

export function sendInvoice(id: number): Promise<Invoice> {
  return request(`/invoices/${id}/send`, { method: 'POST' })
}

export function voidInvoice(id: number): Promise<Invoice> {
  return request(`/invoices/${id}/void`, { method: 'POST' })
}

export function downloadInvoicePdf(invoice: Invoice): Promise<void> {
  return downloadPdf(`/invoices/${invoice.id}/pdf`, `${invoice.number ?? `invoice-${invoice.id}`}.pdf`)
}

// -- settings ----------------------------------------------------------------

export function getBusinessProfile(): Promise<BusinessProfile> {
  return request('/settings/business-profile')
}

export interface SaveBusinessProfileInput {
  business_name: string
  business_address: string
  payment_terms_days: number
  utr?: string
  vat_number?: string
}

export function saveBusinessProfile(input: SaveBusinessProfileInput): Promise<BusinessProfile> {
  return request('/settings/business-profile', { method: 'PUT', body: JSON.stringify(input) })
}
