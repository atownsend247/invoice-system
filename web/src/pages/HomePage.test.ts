import { describe, expect, it } from 'vitest'
import type { Invoice } from '../types'
import { isOutstanding, isOverdue } from './HomePage'

function invoice(overrides: Partial<Invoice>): Invoice {
  return {
    id: 1,
    account_id: 1,
    quote_id: null,
    number: 'INV-0001',
    status: 'sent',
    currency: 'USD',
    issue_date: '2026-01-01',
    due_date: '2026-01-15',
    created_at: '2026-01-01T00:00:00Z',
    line_items: [],
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
