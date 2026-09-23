import { describe, expect, it } from 'vitest'
import type { Invoice } from '../types'
import { conversionRate, isOutstanding, isOverdue } from './HomePage'

function invoice(overrides: Partial<Invoice>): Invoice {
  return {
    id: 'inv-1',
    account_id: 'acc-1',
    quote_id: null,
    number: 'INV-0001',
    status: 'sent',
    currency: 'USD',
    issue_date: '2026-01-01',
    due_date: '2026-01-15',
    created_at: '2026-01-01T00:00:00Z',
    customer_notes: null,
    line_items: [],
    events: [],
    subtotal: '100.00',
    tax_total: '0',
    total: '100.00',
    ...overrides,
  }
}

describe('isOverdue', () => {
  it('is true for a sent invoice whose due date is before the reference date', () => {
    expect(isOverdue(invoice({ due_date: '2026-01-15' }), '2026-01-16')).toBe(true)
  })

  it('is false for a sent invoice due exactly on the reference date', () => {
    expect(isOverdue(invoice({ due_date: '2026-01-16' }), '2026-01-16')).toBe(false)
  })

  it('is false for a sent invoice due after the reference date', () => {
    expect(isOverdue(invoice({ due_date: '2026-01-17' }), '2026-01-16')).toBe(false)
  })

  it('is false for a non-sent invoice regardless of due date', () => {
    expect(isOverdue(invoice({ status: 'paid', due_date: '2026-01-01' }), '2026-01-16')).toBe(false)
    expect(isOverdue(invoice({ status: 'draft', due_date: null }), '2026-01-16')).toBe(false)
    expect(isOverdue(invoice({ status: 'void', due_date: '2026-01-01' }), '2026-01-16')).toBe(false)
  })

  it('is false for a sent invoice with no due date', () => {
    expect(isOverdue(invoice({ due_date: null }), '2026-01-16')).toBe(false)
  })
})

describe('isOutstanding', () => {
  it('is true for a sent invoice due today or in the future', () => {
    expect(isOutstanding(invoice({ due_date: '2026-01-16' }), '2026-01-16')).toBe(true)
    expect(isOutstanding(invoice({ due_date: '2026-01-17' }), '2026-01-16')).toBe(true)
  })

  it('is false once the invoice is overdue', () => {
    expect(isOutstanding(invoice({ due_date: '2026-01-15' }), '2026-01-16')).toBe(false)
  })

  it('is false for a non-sent invoice', () => {
    expect(isOutstanding(invoice({ status: 'paid' }), '2026-01-16')).toBe(false)
  })
})

describe('conversionRate', () => {
  it('is null when no quotes have been sent yet, not 0 or NaN', () => {
    expect(conversionRate({ quotes_sent_count: 0, quotes_converted_count: 0 })).toBeNull()
  })

  it('is a percentage of sent quotes that were converted', () => {
    expect(conversionRate({ quotes_sent_count: 4, quotes_converted_count: 1 })).toBe(25)
  })

  it('is 100 when every sent quote converted', () => {
    expect(conversionRate({ quotes_sent_count: 3, quotes_converted_count: 3 })).toBe(100)
  })

  it('is 0 when quotes were sent but none converted', () => {
    expect(conversionRate({ quotes_sent_count: 3, quotes_converted_count: 0 })).toBe(0)
  })
})
