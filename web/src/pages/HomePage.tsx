import { Link } from 'react-router-dom'
import * as api from '../api'
import { MonthlyTotalsChart } from '../components/MonthlyTotalsChart'
import { StatusBadge } from '../components/StatusBadge'
import { useAsync } from '../hooks/useAsync'
import type { Account, Invoice, Stats } from '../types'

/** Today as an ISO date (`YYYY-MM-DD`) - comparable directly against
 * `due_date`, which is stored/serialised the same way (see CLAUDE.md,
 * timestamps convention). */
function today(): string {
  return new Date().toISOString().slice(0, 10)
}

/** "overdue"/"outstanding" aren't stored invoice statuses - only `sent`,
 * `paid`, `draft`, `void` are (see CLAUDE.md: the `overdue` status
 * transition is unimplemented future work). Both are derived here, purely
 * for display, from a `sent` invoice's `due_date` vs `asOf` (defaults to
 * today; a param so this stays unit-testable without mocking the clock). */
export function isOverdue(invoice: Invoice, asOf: string = today()): boolean {
  return invoice.status === 'sent' && invoice.due_date !== null && invoice.due_date < asOf
}

export function isOutstanding(invoice: Invoice, asOf: string = today()): boolean {
  return invoice.status === 'sent' && !isOverdue(invoice, asOf)
}

/** The percentage of sent quotes that went on to become an invoice.
 * `quotes_sent_count`/`quotes_converted_count` are raw counts from the API
 * (see types.ts's Stats) - the division, and the "no quotes sent yet" case,
 * are handled here rather than server-side, same reasoning as isOverdue/
 * isOutstanding above. `null` (not 0 or NaN) when nothing's been sent yet,
 * so the caller can render a dash instead of a misleading "0%". */
export function conversionRate(stats: Pick<Stats, 'quotes_sent_count' | 'quotes_converted_count'>): number | null {
  if (stats.quotes_sent_count === 0) return null
  return (stats.quotes_converted_count / stats.quotes_sent_count) * 100
}

export function HomePage() {
  // status: 'sent' - both isOverdue/isOutstanding below require it anyway,
  // so filtering server-side keeps this to "invoices currently awaiting
  // payment" (naturally small - most invoices eventually get paid/voided)
  // rather than every invoice this organisation has ever issued. pageSize:
  // 200 is then a comfortably generous cap on that smaller set, not on the
  // organisation's whole invoice history.
  const {
    data: invoicesResult,
    loading,
    error,
  } = useAsync(() => api.listInvoices({ status: 'sent', pageSize: 200 }), [])
  const invoices = invoicesResult?.items
  const { data: accountsResult } = useAsync(() => api.listAccounts({ pageSize: 200 }), [])
  const accounts = accountsResult?.items
  const { data: monthlyTotals, error: monthlyTotalsError } = useAsync(
    () => api.getMonthlyInvoiceTotals(),
    [],
  )
  const { data: monthlyExpenseTotals, error: monthlyExpenseTotalsError } = useAsync(
    () => api.getMonthlyExpenseTotals(),
    [],
  )
  const { data: stats, error: statsError } = useAsync(() => api.getStats(), [])

  return (
    <section>
      <h1>Home</h1>
      <p className="meta">Invoices that need your attention.</p>

      {loading && <p>Loading…</p>}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}

      {invoices && (
        <>
          <InvoiceSection
            title="Overdue"
            invoices={invoices.filter((invoice) => isOverdue(invoice))}
            accounts={accounts}
            emptyMessage="No overdue invoices."
          />
          <InvoiceSection
            title="Outstanding"
            invoices={invoices.filter((invoice) => isOutstanding(invoice))}
            accounts={accounts}
            emptyMessage="No outstanding invoices."
          />
        </>
      )}

      <div className="dashboard-section">
        <h2>Invoice totals, last 12 months</h2>
        {monthlyTotalsError && (
          <p className="form-error" role="alert">
            {monthlyTotalsError}
          </p>
        )}
        {monthlyExpenseTotalsError && (
          <p className="form-error" role="alert">
            {monthlyExpenseTotalsError}
          </p>
        )}
        {monthlyTotals && monthlyExpenseTotals && (
          <MonthlyTotalsChart
            currency={monthlyTotals.currency}
            months={monthlyTotals.months}
            expenseMonths={monthlyExpenseTotals.months}
          />
        )}
      </div>

      <div className="dashboard-section">
        <h2>All-time stats</h2>
        {statsError && (
          <p className="form-error" role="alert">
            {statsError}
          </p>
        )}
        {stats && (
          <dl className="stats-grid">
            <div className="stat">
              <dt>Accounts registered</dt>
              <dd>{stats.account_count}</dd>
            </div>
            <div className="stat">
              <dt>Quotes created</dt>
              <dd>{stats.quote_count}</dd>
            </div>
            <div className="stat">
              <dt>Quote conversion rate</dt>
              <dd>
                {conversionRate(stats) === null ? '—' : `${conversionRate(stats)!.toFixed(0)}%`}
              </dd>
            </div>
            <div className="stat">
              <dt>Invoices created</dt>
              <dd>{stats.invoice_count}</dd>
            </div>
            <div className="stat">
              <dt>Total paid</dt>
              <dd>
                {stats.total_paid} {stats.currency}
              </dd>
            </div>
          </dl>
        )}
      </div>
    </section>
  )
}

function InvoiceSection({
  title,
  invoices,
  accounts,
  emptyMessage,
}: {
  title: string
  invoices: Invoice[]
  accounts: Account[] | null | undefined
  emptyMessage: string
}) {
  const accountName = (accountId: string) =>
    accounts?.find((account) => account.id === accountId)?.business_name ?? `#${accountId}`

  return (
    <div className="dashboard-section">
      <h2>{title}</h2>
      {invoices.length === 0 && <p className="meta">{emptyMessage}</p>}
      {invoices.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Number</th>
              <th>Account</th>
              <th>Status</th>
              <th>Due</th>
              <th>Total</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {invoices.map((invoice) => (
              <tr key={invoice.id}>
                <td>{invoice.number ?? `draft #${invoice.id}`}</td>
                <td>{accountName(invoice.account_id)}</td>
                <td>
                  <StatusBadge status={invoice.status} />
                </td>
                <td>{invoice.due_date ?? '—'}</td>
                <td>
                  {invoice.total} {invoice.currency}
                </td>
                <td>
                  <Link to={`/invoices/${invoice.id}`}>View</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
