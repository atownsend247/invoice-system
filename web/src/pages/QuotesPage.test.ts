import { describe, expect, it } from 'vitest'
import type { Quote } from '../types'
import { quoteMatchesFilters } from './QuotesPage'

function quote(overrides: Partial<Quote>): Quote {
  return {
    id: 'quote-1',
    account_id: 'acc-1',
    number: 'Q-0001',
    status: 'sent',
    currency: 'GBP',
    issue_date: '2026-01-01',
    expiry_date: null,
    created_at: '2026-01-01T00:00:00Z',
    line_items: [],
    subtotal: '100.00',
    tax_total: '0.00',
    total: '100.00',
    ...overrides,
  }
}

describe('quoteMatchesFilters', () => {
  it('matches everything when no filters are set', () => {
    expect(quoteMatchesFilters(quote({}), 'Northwind Traders', { accountQuery: '', status: '' })).toBe(true)
  })

  it('matches account name case-insensitively', () => {
    expect(
      quoteMatchesFilters(quote({}), 'Northwind Traders', { accountQuery: 'northwind', status: '' }),
    ).toBe(true)
    expect(quoteMatchesFilters(quote({}), 'Northwind Traders', { accountQuery: 'acme', status: '' })).toBe(
      false,
    )
  })

  it('matches status exactly', () => {
    expect(
      quoteMatchesFilters(quote({ status: 'draft' }), 'Northwind Traders', { accountQuery: '', status: 'draft' }),
    ).toBe(true)
    expect(
      quoteMatchesFilters(quote({ status: 'sent' }), 'Northwind Traders', { accountQuery: '', status: 'draft' }),
    ).toBe(false)
  })

  it('requires both filters to match when both are set', () => {
    const filters = { accountQuery: 'northwind', status: 'sent' as const }
    expect(quoteMatchesFilters(quote({ status: 'sent' }), 'Northwind Traders', filters)).toBe(true)
    expect(quoteMatchesFilters(quote({ status: 'draft' }), 'Northwind Traders', filters)).toBe(false)
    expect(quoteMatchesFilters(quote({ status: 'sent' }), 'Acme Ltd', filters)).toBe(false)
  })
})
