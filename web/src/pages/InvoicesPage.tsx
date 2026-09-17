import { useState } from 'react'
import { Link } from 'react-router-dom'
import * as api from '../api'
import { Pagination } from '../components/Pagination'
import { StatusBadge } from '../components/StatusBadge'
import { useAsync } from '../hooks/useAsync'
import { usePagedList } from '../hooks/usePagedList'
import type { Invoice, InvoiceStatus } from '../types'

// 'overdue' deliberately excluded - it's presentation-only, computed
// client-side on the home dashboard, and never actually written to
// Invoice.status (see CLAUDE.md), so it would only ever match zero rows.
const INVOICE_STATUSES: InvoiceStatus[] = ['draft', 'sent', 'paid', 'void']

/** Matches an invoice against the account-name and status filters on this
 * page. Exported (like AccountsPage's accountMatchesQuery) so the matching
 * logic is unit-testable without rendering the page. */
export function invoiceMatchesFilters(
  invoice: Invoice,
  accountName: string,
  filters: { accountQuery: string; status: InvoiceStatus | '' },
): boolean {
  if (filters.status && invoice.status !== filters.status) return false
  const normalised = filters.accountQuery.trim().toLowerCase()
  if (!normalised) return true
  return accountName.toLowerCase().includes(normalised)
}

export function InvoicesPage() {
  const { data: invoices, loading, error } = useAsync(() => api.listInvoices(), [])
  const { data: accounts } = useAsync(() => api.listAccounts(), [])
  const [accountQuery, setAccountQuery] = useState('')
  const [status, setStatus] = useState<InvoiceStatus | ''>('')

  const accountName = (accountId: string) =>
    accounts?.find((account) => account.id === accountId)?.business_name ?? `#${accountId}`

  const filteredInvoices = invoices?.filter((invoice) =>
    invoiceMatchesFilters(invoice, accountName(invoice.account_id), { accountQuery, status }),
  )
  const { page, totalPages, setPage, paged: pagedInvoices } = usePagedList(filteredInvoices)

  return (
    <section>
      <h1>Invoices</h1>

      {loading && <p>Loading…</p>}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {invoices && invoices.length === 0 && <p>No invoices yet — convert a sent quote to create one.</p>}
      {invoices && invoices.length > 0 && (
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

          {filteredInvoices && filteredInvoices.length === 0 && (
            <p className="meta">No invoices match these filters.</p>
          )}
          {pagedInvoices && pagedInvoices.length > 0 && (
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
                {pagedInvoices.map((invoice) => (
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
          <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
        </>
      )}
    </section>
  )
}
