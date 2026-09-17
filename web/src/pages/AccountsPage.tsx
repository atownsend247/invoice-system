import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { accountAddressLines } from '../accountAddress'
import * as api from '../api'
import { AccountForm } from '../components/AccountForm'
import { Pagination } from '../components/Pagination'
import { useAsync } from '../hooks/useAsync'
import { useDebouncedValue } from '../hooks/useDebouncedValue'

const PAGE_SIZE = 20

export function AccountsPage() {
  const [showForm, setShowForm] = useState(false)
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const navigate = useNavigate()

  const debouncedQuery = useDebouncedValue(query)
  const {
    data: result,
    loading,
    error,
  } = useAsync(
    () => api.listAccounts({ query: debouncedQuery || undefined, page, pageSize: PAGE_SIZE }),
    [debouncedQuery, page],
  )
  const accounts = result?.items
  const totalPages = Math.max(1, Math.ceil((result?.total ?? 0) / PAGE_SIZE))
  const hasQuery = query.trim().length > 0

  return (
    <section>
      <div className="page-header">
        <h1>Accounts</h1>
        <button type="button" onClick={() => setShowForm((show) => !show)}>
          {showForm ? 'Cancel' : 'New account'}
        </button>
      </div>

      {showForm && (
        <AccountForm
          submitLabel="Create account"
          submittingLabel="Creating…"
          onSubmit={(input) => api.createAccount(input)}
          onDone={(account) => navigate(`/accounts/${account.id}`)}
        />
      )}

      {loading && <p>Loading…</p>}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {result && result.total === 0 && !hasQuery && <p>No accounts yet.</p>}
      {result && (result.total > 0 || hasQuery) && (
        <>
          <label className="search-box">
            Search accounts
            <input
              type="search"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value)
                setPage(1)
              }}
              placeholder="Business name, contact, email, address…"
            />
          </label>

          {accounts && accounts.length === 0 && <p className="meta">No accounts match "{query}".</p>}
          {accounts && accounts.length > 0 && (
            <table>
              <thead>
                <tr>
                  <th>Business</th>
                  <th>Contact</th>
                  <th>Email</th>
                  <th>Address</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {accounts.map((account) => (
                  <tr
                    key={account.id}
                    className="row-link"
                    tabIndex={0}
                    role="link"
                    aria-label={`View ${account.business_name}`}
                    onClick={() => navigate(`/accounts/${account.id}`)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault()
                        navigate(`/accounts/${account.id}`)
                      }
                    }}
                  >
                    <td>{account.business_name}</td>
                    <td>{account.contact_name ?? '—'}</td>
                    <td>{account.email}</td>
                    <td>{accountAddressLines(account).join(', ')}</td>
                    <td
                      onClick={(event) => event.stopPropagation()}
                      onKeyDown={(event) => event.stopPropagation()}
                    >
                      <Link className="button" to={`/quotes/new?accountId=${account.id}`}>
                        New quote
                      </Link>
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
