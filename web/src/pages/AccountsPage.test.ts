import { describe, expect, it } from 'vitest'
import type { Account } from '../types'
import { accountMatchesQuery } from './AccountsPage'

function account(overrides: Partial<Account>): Account {
  return {
    id: 'acc-1',
    business_name: 'Northwind Traders',
    contact_name: 'Priya Patel',
    email: 'billing@northwindtraders.test',
    phone: '020 7946 0958',
    address_line1: '12 Kings Road',
    address_line2: null,
    town_or_city: 'London',
    county: null,
    postcode: 'SW1A 1AA',
    created_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

describe('accountMatchesQuery', () => {
  it('matches everything when the query is blank', () => {
    expect(accountMatchesQuery(account({}), '')).toBe(true)
    expect(accountMatchesQuery(account({}), '   ')).toBe(true)
  })

  it('matches business name, case-insensitively', () => {
    expect(accountMatchesQuery(account({}), 'northwind')).toBe(true)
    expect(accountMatchesQuery(account({}), 'NORTHWIND')).toBe(true)
  })

  it('matches contact name, email, and phone', () => {
    expect(accountMatchesQuery(account({}), 'Priya')).toBe(true)
    expect(accountMatchesQuery(account({}), 'billing@northwindtraders.test')).toBe(true)
    expect(accountMatchesQuery(account({}), '7946')).toBe(true)
  })

  it('matches any set address line, including the postcode', () => {
    expect(accountMatchesQuery(account({}), 'Kings Road')).toBe(true)
    expect(accountMatchesQuery(account({}), 'London')).toBe(true)
    expect(accountMatchesQuery(account({}), 'SW1A')).toBe(true)
  })

  it('does not match unset optional fields', () => {
    expect(accountMatchesQuery(account({ contact_name: null }), 'Priya')).toBe(false)
  })

  it('is false when nothing matches', () => {
    expect(accountMatchesQuery(account({}), 'Nonexistent Ltd')).toBe(false)
  })
})
