import type { MonthlyExpenseTotal, MonthlyInvoiceTotal } from '../types'

function formatMonthLabel(month: string): string {
  const [year, monthNumber] = month.split('-').map(Number)
  return new Date(year, monthNumber - 1, 1).toLocaleDateString(undefined, { month: 'short', year: '2-digit' })
}

/** Bar heights are Number()-parsed from the decimal-string totals purely to
 * compute a visual proportion - never stored, compared for equality, or fed
 * back into a request. The exact string values stay on `title` (and remain
 * what's sent to the server) - see CLAUDE.md's "money stays a string
 * client-side" convention, which is about avoiding stored/round-tripped
 * arithmetic, not about never calling Number() for a chart. */
export function MonthlyTotalsChart({
  currency,
  months,
  expenseMonths,
}: {
  currency: string
  months: MonthlyInvoiceTotal[]
  expenseMonths: MonthlyExpenseTotal[]
}) {
  // Looked up by month key, not zipped by array index - both come from
  // separate API calls (InvoiceService.monthly_totals/
  // ExpenseService.monthly_totals), so matching on the "YYYY-MM" they both
  // share is what actually guarantees a given expense bar lines up under
  // the right invoice bars, rather than relying on both endpoints always
  // returning the same number of entries in the same order.
  const expenseTotalByMonth = new Map(expenseMonths.map((entry) => [entry.month, entry.total]))
  const max = Math.max(
    1,
    ...months.flatMap((entry) => [Number(entry.paid_total), Number(entry.unpaid_total)]),
    ...expenseMonths.map((entry) => Number(entry.total)),
  )

  return (
    <div>
      <div className="monthly-chart-legend">
        <span className="monthly-chart-swatch paid" />
        <span>Paid</span>
        <span className="monthly-chart-swatch unpaid" />
        <span>Outstanding</span>
        <span className="monthly-chart-swatch expense" />
        <span>Expenses</span>
      </div>
      <div className="monthly-chart" role="group" aria-label={`Invoice totals by month, in ${currency}`}>
        {months.map((entry) => {
          const expenseTotal = expenseTotalByMonth.get(entry.month) ?? '0'
          return (
            <div className="monthly-chart-column" key={entry.month}>
              <div className="monthly-chart-bars">
                <div
                  className="monthly-chart-bar paid"
                  style={{ height: `${(Number(entry.paid_total) / max) * 100}%` }}
                  title={`Paid: ${entry.paid_total} ${currency}`}
                />
                <div
                  className="monthly-chart-bar unpaid"
                  style={{ height: `${(Number(entry.unpaid_total) / max) * 100}%` }}
                  title={`Outstanding: ${entry.unpaid_total} ${currency}`}
                />
                <div
                  className="monthly-chart-bar expense"
                  style={{ height: `${(Number(expenseTotal) / max) * 100}%` }}
                  title={`Expenses: ${expenseTotal} ${currency}`}
                />
              </div>
              <span className="monthly-chart-label">{formatMonthLabel(entry.month)}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
