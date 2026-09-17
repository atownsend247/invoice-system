import { useState } from 'react'
import { Link } from 'react-router-dom'
import * as api from '../api'
import { Pagination } from '../components/Pagination'
import { StatusBadge } from '../components/StatusBadge'
import { useAsync } from '../hooks/useAsync'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import type { QuoteStatus } from '../types'

const PAGE_SIZE = 20
const QUOTE_STATUSES: QuoteStatus[] = ['draft', 'sent', 'accepted', 'rejected', 'expired', 'converted']

export function QuotesPage() {
  const [accountQuery, setAccountQuery] = useState('')
  const [status, setStatus] = useState<QuoteStatus | ''>('')
  const [page, setPage] = useState(1)

  const debouncedAccountQuery = useDebouncedValue(accountQuery)
  const {
    data: result,
    loading,
    error,
  } = useAsync(
    () =>
      api.listQuotes({
        accountName: debouncedAccountQuery || undefined,
        status: status || undefined,
        page,
        pageSize: PAGE_SIZE,
      }),
    [debouncedAccountQuery, status, page],
  )
  // pageSize: 200 - this is only for resolving id -> business_name below,
  // not the page shown, so it needs every account in the organisation, not
  // just the accounts list page's own first page (see CLAUDE.md/roadmap on
  // why 200 is the accepted cap rather than truly unbounded).
  const { data: accounts } = useAsync(() => api.listAccounts({ pageSize: 200 }), [])

  const accountName = (accountId: string) =>
    accounts?.items.find((account) => account.id === accountId)?.business_name ?? `#${accountId}`

  const quotes = result?.items
  const totalPages = Math.max(1, Math.ceil((result?.total ?? 0) / PAGE_SIZE))
  const hasFilters = accountQuery.trim().length > 0 || status !== ''

  return (
    <section>
      <div className="page-header">
        <h1>Quotes</h1>
        <Link className="button" to="/quotes/new">
          New quote
        </Link>
      </div>

      {loading && <p>Loading…</p>}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {result && result.total === 0 && !hasFilters && <p>No quotes yet.</p>}
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
                  setStatus(event.target.value as QuoteStatus | '')
                  setPage(1)
                }}
              >
                <option value="">All statuses</option>
                {QUOTE_STATUSES.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {quotes && quotes.length === 0 && <p className="meta">No quotes match these filters.</p>}
          {quotes && quotes.length > 0 && (
            <table>
              <thead>
                <tr>
                  <th>Number</th>
                  <th>Account</th>
                  <th>Status</th>
                  <th>Total</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {quotes.map((quote) => (
                  <tr key={quote.id}>
                    <td>{quote.number ?? `draft #${quote.id}`}</td>
                    <td>{accountName(quote.account_id)}</td>
                    <td>
                      <StatusBadge status={quote.status} />
                    </td>
                    <td>
                      {quote.total} {quote.currency}
                    </td>
                    <td>
                      <Link to={`/quotes/${quote.id}`}>View</Link>
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
