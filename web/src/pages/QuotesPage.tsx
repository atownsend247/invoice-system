import { useState } from 'react'
import { Link } from 'react-router-dom'
import * as api from '../api'
import { Pagination } from '../components/Pagination'
import { StatusBadge } from '../components/StatusBadge'
import { useAsync } from '../hooks/useAsync'
import { usePagedList } from '../hooks/usePagedList'
import type { Quote, QuoteStatus } from '../types'

const QUOTE_STATUSES: QuoteStatus[] = ['draft', 'sent', 'accepted', 'rejected', 'expired', 'converted']

/** Matches a quote against the account-name and status filters on this
 * page. Exported (like AccountsPage's accountMatchesQuery) so the matching
 * logic is unit-testable without rendering the page. */
export function quoteMatchesFilters(
  quote: Quote,
  accountName: string,
  filters: { accountQuery: string; status: QuoteStatus | '' },
): boolean {
  if (filters.status && quote.status !== filters.status) return false
  const normalised = filters.accountQuery.trim().toLowerCase()
  if (!normalised) return true
  return accountName.toLowerCase().includes(normalised)
}

export function QuotesPage() {
  const { data: quotes, loading, error } = useAsync(() => api.listQuotes(), [])
  const { data: accounts } = useAsync(() => api.listAccounts(), [])
  const [accountQuery, setAccountQuery] = useState('')
  const [status, setStatus] = useState<QuoteStatus | ''>('')

  const accountName = (accountId: string) =>
    accounts?.find((account) => account.id === accountId)?.business_name ?? `#${accountId}`

  const filteredQuotes = quotes?.filter((quote) =>
    quoteMatchesFilters(quote, accountName(quote.account_id), { accountQuery, status }),
  )
  const { page, totalPages, setPage, paged: pagedQuotes } = usePagedList(filteredQuotes)

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
      {quotes && quotes.length === 0 && <p>No quotes yet.</p>}
      {quotes && quotes.length > 0 && (
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

          {filteredQuotes && filteredQuotes.length === 0 && <p className="meta">No quotes match these filters.</p>}
          {pagedQuotes && pagedQuotes.length > 0 && (
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
                {pagedQuotes.map((quote) => (
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
