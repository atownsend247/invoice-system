import { Link } from 'react-router-dom'
import * as api from '../api'
import { MonthlyTotalsChart } from '../components/MonthlyTotalsChart'
import { StatusBadge } from '../components/StatusBadge'
import { useAsync } from '../hooks/useAsync'
import type { Account, Invoice } from '../types'

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

export function HomePage() {
  const { data: invoices, loading, error } = useAsync(() => api.listInvoices(), [])
  const { data: accounts } = useAsync(() => api.listAccounts(), [])
  const { data: monthlyTotals, error: monthlyTotalsError } = useAsync(
    () => api.getMonthlyInvoiceTotals(),
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
        {monthlyTotals && (
          <MonthlyTotalsChart currency={monthlyTotals.currency} months={monthlyTotals.months} />
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
  accounts: Account[] | null
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
