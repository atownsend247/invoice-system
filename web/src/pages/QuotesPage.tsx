import { Link } from 'react-router-dom'
import * as api from '../api'
import { StatusBadge } from '../components/StatusBadge'
import { useAsync } from '../hooks/useAsync'

export function QuotesPage() {
  const { data: quotes, loading, error } = useAsync(() => api.listQuotes(), [])
  const { data: accounts } = useAsync(() => api.listAccounts(), [])

  const accountName = (accountId: string) =>
    accounts?.find((account) => account.id === accountId)?.business_name ?? `#${accountId}`

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
    </section>
  )
}
