import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { MonthlyExpenseTotal, MonthlyInvoiceTotal } from '../types'
import { MonthlyTotalsChart } from './MonthlyTotalsChart'

function months(overrides: Partial<MonthlyInvoiceTotal>[]): MonthlyInvoiceTotal[] {
  return overrides.map((entry, index) => ({
    month: `2026-${String(index + 1).padStart(2, '0')}`,
    paid_total: '0',
    unpaid_total: '0',
    ...entry,
  }))
}

function expenseMonths(overrides: Partial<MonthlyExpenseTotal>[]): MonthlyExpenseTotal[] {
  return overrides.map((entry, index) => ({
    month: `2026-${String(index + 1).padStart(2, '0')}`,
    total: '0',
    ...entry,
  }))
}

describe('MonthlyTotalsChart', () => {
  it('renders one column per month with a bar for each total, exact amounts on title', () => {
    render(
      <MonthlyTotalsChart
        currency="GBP"
        months={months([{ paid_total: '100.00', unpaid_total: '50.00' }, {}])}
        expenseMonths={expenseMonths([{ total: '30.00' }, {}])}
      />,
    )

    expect(screen.getByRole('group', { name: /Invoice totals by month, in GBP/ })).toBeInTheDocument()
    expect(screen.getByTitle('Paid: 100.00 GBP')).toBeInTheDocument()
    expect(screen.getByTitle('Outstanding: 50.00 GBP')).toBeInTheDocument()
    expect(screen.getByTitle('Expenses: 30.00 GBP')).toBeInTheDocument()
  })

  it('scales the tallest bar to 100% of the max value seen across invoice and expense totals', () => {
    render(
      <MonthlyTotalsChart
        currency="GBP"
        months={months([{ paid_total: '200.00' }, { paid_total: '50.00' }])}
        expenseMonths={expenseMonths([{}, {}])}
      />,
    )

    expect(screen.getByTitle('Paid: 200.00 GBP')).toHaveStyle({ height: '100%' })
    expect(screen.getByTitle('Paid: 50.00 GBP')).toHaveStyle({ height: '25%' })
  })

  it('an expense total larger than any invoice total sets the scale', () => {
    render(
      <MonthlyTotalsChart
        currency="GBP"
        months={months([{ paid_total: '50.00' }])}
        expenseMonths={expenseMonths([{ total: '200.00' }])}
      />,
    )

    expect(screen.getByTitle('Expenses: 200.00 GBP')).toHaveStyle({ height: '100%' })
    expect(screen.getByTitle('Paid: 50.00 GBP')).toHaveStyle({ height: '25%' })
  })

  it('renders a zero-height bar without dividing by zero when every month is empty', () => {
    render(<MonthlyTotalsChart currency="GBP" months={months([{}, {}])} expenseMonths={[]} />)
    expect(screen.getAllByTitle(/^Paid: 0 GBP$/)[0]).toHaveStyle({ height: '0%' })
    expect(screen.getAllByTitle(/^Expenses: 0 GBP$/)[0]).toHaveStyle({ height: '0%' })
  })

  it('matches expense totals to invoice months by month key, not array position', () => {
    // Deliberately out of order and a different length than `months` -
    // proves the lookup is keyed by "YYYY-MM", not zipped by index.
    render(
      <MonthlyTotalsChart
        currency="GBP"
        months={months([{}, {}])} // 2026-01, 2026-02
        expenseMonths={[{ month: '2026-02', total: '75.00' }]}
      />,
    )

    expect(screen.getByTitle('Expenses: 75.00 GBP')).toBeInTheDocument()
    expect(screen.getByTitle('Expenses: 0 GBP')).toBeInTheDocument() // 2026-01 has no matching entry
  })

  it('shows a legend for all three series', () => {
    render(<MonthlyTotalsChart currency="GBP" months={months([{}])} expenseMonths={expenseMonths([{}])} />)
    expect(screen.getByText('Paid')).toBeInTheDocument()
    expect(screen.getByText('Outstanding')).toBeInTheDocument()
    expect(screen.getByText('Expenses')).toBeInTheDocument()
  })
})
