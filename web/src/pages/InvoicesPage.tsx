import { useState } from 'react'
import { Link } from 'react-router-dom'
import * as api from '../api'
import { Pagination } from '../components/Pagination'
import { StatusBadge } from '../components/StatusBadge'
import { useAsync } from '../hooks/useAsync'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import type { InvoiceStatus } from '../types'

const PAGE_SIZE = 20

// 'overdue' deliberately excluded - it's presentation-only, computed
// client-side on the home dashboard, and never actually written to
// Invoice.status (see CLAUDE.md), so it would only ever match zero rows.
const INVOICE_STATUSES: InvoiceStatus[] = ['draft', 'sent', 'paid', 'void']

export function InvoicesPage() {
  const [accountQuery, setAccountQuery] = useState('')
  const [status, setStatus] = useState<InvoiceStatus | ''>('')
  const [page, setPage] = useState(1)

  const debouncedAccountQuery = useDebouncedValue(accountQuery)
  const {
    data: result,
    loading,
    error,
  } = useAsync(
    () =>
      api.listInvoices({
        accountName: debouncedAccountQuery || undefined,
        status: status || undefined,
        page,
        pageSize: PAGE_SIZE,
      }),
    [debouncedAccountQuery, status, page],
  )
  // pageSize: 200 - see the same note on QuotesPage.tsx's own accounts fetch.
  const { data: accounts } = useAsync(() => api.listAccounts({ pageSize: 200 }), [])

  const accountName = (accountId: string) =>
    accounts?.items.find((account) => account.id === accountId)?.business_name ?? `#${accountId}`

  const invoices = result?.items
  const totalPages = Math.max(1, Math.ceil((result?.total ?? 0) / PAGE_SIZE))
  const hasFilters = accountQuery.trim().length > 0 || status !== ''

  return (
    <section>
      <h1>Invoices</h1>

      {loading && <p>Loading…</p>}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {result && result.total === 0 && !hasFilters && (
        <p>No invoices yet — convert a sent quote to create one.</p>
      )}
      {result && (result.total > 0 || hasFilters) && (
        <>
          <div className="filters">
            <label className="search-box">
              Account
              <input
                type="search"
                value={accountQuery}
                onChange={(event) => {
                  setAccountQuery(event.target.value)
                  setPage(1)
                }}
                placeholder="Account name…"
              />
            </label>
            <label className="search-box">
              Status
              <select
                value={status}
                onChange={(event) => {
                  setStatus(event.target.value as InvoiceStatus | '')
                  setPage(1)
                }}
              >
                <option value="">All statuses</option>
                {INVOICE_STATUSES.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {invoices && invoices.length === 0 && <p className="meta">No invoices match these filters.</p>}
          {invoices && invoices.length > 0 && (
            <div className="table-scroll">
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
            </div>
          )}
          <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
        </>
      )}
    </section>
  )
}
