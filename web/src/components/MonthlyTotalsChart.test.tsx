import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { MonthlyInvoiceTotal } from '../types'
import { MonthlyTotalsChart } from './MonthlyTotalsChart'

function months(overrides: Partial<MonthlyInvoiceTotal>[]): MonthlyInvoiceTotal[] {
  return overrides.map((entry, index) => ({
    month: `2026-${String(index + 1).padStart(2, '0')}`,
    paid_total: '0',
    unpaid_total: '0',
    ...entry,
  }))
}

describe('MonthlyTotalsChart', () => {
  it('renders one column per month with a bar for each total, exact amounts on title', () => {
    render(
      <MonthlyTotalsChart
        currency="GBP"
        months={months([{ paid_total: '100.00', unpaid_total: '50.00' }, {}])}
      />,
    )

    expect(screen.getByRole('group', { name: /Invoice totals by month, in GBP/ })).toBeInTheDocument()
    expect(screen.getByTitle('Paid: 100.00 GBP')).toBeInTheDocument()
    expect(screen.getByTitle('Outstanding: 50.00 GBP')).toBeInTheDocument()
  })

  it('scales the tallest bar to 100% of the max value seen across all months', () => {
    render(<MonthlyTotalsChart currency="GBP" months={months([{ paid_total: '200.00' }, { paid_total: '50.00' }])} />)

    expect(screen.getByTitle('Paid: 200.00 GBP')).toHaveStyle({ height: '100%' })
    expect(screen.getByTitle('Paid: 50.00 GBP')).toHaveStyle({ height: '25%' })
  })

  it('renders a zero-height bar without dividing by zero when every month is empty', () => {
    render(<MonthlyTotalsChart currency="GBP" months={months([{}, {}])} />)
    expect(screen.getAllByTitle(/^Paid: 0 GBP$/)[0]).toHaveStyle({ height: '0%' })
  })

  it('shows a legend for the two series', () => {
    render(<MonthlyTotalsChart currency="GBP" months={months([{}])} />)
    expect(screen.getByText('Paid')).toBeInTheDocument()
    expect(screen.getByText('Outstanding')).toBeInTheDocument()
  })
})
