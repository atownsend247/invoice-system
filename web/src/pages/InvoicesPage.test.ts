import { describe, expect, it } from 'vitest'
import type { Invoice } from '../types'
import { invoiceMatchesFilters } from './InvoicesPage'

function invoice(overrides: Partial<Invoice>): Invoice {
  return {
    id: 'invoice-1',
    account_id: 'acc-1',
    quote_id: null,
    number: 'INV-0001',
    status: 'sent',
    currency: 'GBP',
    issue_date: '2026-01-01',
    due_date: '2026-01-31',
    created_at: '2026-01-01T00:00:00Z',
    line_items: [],
    subtotal: '100.00',
    tax_total: '0.00',
    total: '100.00',
    ...overrides,
  }
}

describe('invoiceMatchesFilters', () => {
  it('matches everything when no filters are set', () => {
    expect(invoiceMatchesFilters(invoice({}), 'Northwind Traders', { accountQuery: '', status: '' })).toBe(true)
  })

  it('matches account name case-insensitively', () => {
    expect(
      invoiceMatchesFilters(invoice({}), 'Northwind Traders', { accountQuery: 'northwind', status: '' }),
    ).toBe(true)
    expect(
      invoiceMatchesFilters(invoice({}), 'Northwind Traders', { accountQuery: 'acme', status: '' }),
    ).toBe(false)
  })

  it('matches status exactly', () => {
    expect(
      invoiceMatchesFilters(invoice({ status: 'paid' }), 'Northwind Traders', {
        accountQuery: '',
        status: 'paid',
      }),
    ).toBe(true)
    expect(
      invoiceMatchesFilters(invoice({ status: 'sent' }), 'Northwind Traders', {
        accountQuery: '',
        status: 'paid',
      }),
    ).toBe(false)
  })

  it('requires both filters to match when both are set', () => {
    const filters = { accountQuery: 'northwind', status: 'paid' as const }
    expect(invoiceMatchesFilters(invoice({ status: 'paid' }), 'Northwind Traders', filters)).toBe(true)
    expect(invoiceMatchesFilters(invoice({ status: 'sent' }), 'Northwind Traders', filters)).toBe(false)
    expect(invoiceMatchesFilters(invoice({ status: 'paid' }), 'Acme Ltd', filters)).toBe(false)
  })
})
