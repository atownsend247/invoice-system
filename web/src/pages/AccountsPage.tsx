import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { accountAddressLines } from '../accountAddress'
import * as api from '../api'
import { AccountForm } from '../components/AccountForm'
import { useAsync } from '../hooks/useAsync'
import type { Account } from '../types'

/** Matches a search box query against everything shown in the list -
 * business/contact name, email, phone, and every set address line - not
 * just business name, so "SW1A" or "Priya" both find the right row.
 * Exported (like HomePage's isOverdue/isOutstanding) so the matching logic
 * is unit-testable without rendering the page. */
export function accountMatchesQuery(account: Account, query: string): boolean {
  const normalised = query.trim().toLowerCase()
  if (!normalised) return true
  const haystack = [
    account.business_name,
    account.contact_name,
    account.email,
    account.phone,
    ...accountAddressLines(account),
  ]
    .filter((value): value is string => Boolean(value))
    .join(' ')
    .toLowerCase()
  return haystack.includes(normalised)
}

export function AccountsPage() {
  const { data: accounts, loading, error } = useAsync(() => api.listAccounts(), [])
  const [showForm, setShowForm] = useState(false)
  const [query, setQuery] = useState('')
  const navigate = useNavigate()

  const filteredAccounts = accounts?.filter((account) => accountMatchesQuery(account, query))

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
      {accounts && accounts.length === 0 && <p>No accounts yet.</p>}
      {accounts && accounts.length > 0 && (
        <>
          <label className="search-box">
            Search accounts
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Business name, contact, email, address…"
            />
          </label>

          {filteredAccounts && filteredAccounts.length === 0 && (
            <p className="meta">No accounts match "{query}".</p>
          )}
          {filteredAccounts && filteredAccounts.length > 0 && (
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
                {filteredAccounts.map((account) => (
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
                      <Link to={`/quotes/new?accountId=${account.id}`}>New quote</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </section>
  )
}
