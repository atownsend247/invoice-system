import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import * as api from '../api'
import { AccountForm } from '../components/AccountForm'
import { useAsync } from '../hooks/useAsync'

export function AccountsPage() {
  const { data: accounts, loading, error } = useAsync(() => api.listAccounts(), [])
  const [showForm, setShowForm] = useState(false)
  const navigate = useNavigate()

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
              <tr key={account.id}>
                <td>{account.business_name}</td>
                <td>{account.contact_name ?? '—'}</td>
                <td>{account.email}</td>
                <td>{account.address}</td>
                <td>
                  <Link to={`/accounts/${account.id}`}>Edit</Link>{' '}
                  <Link to={`/quotes/new?accountId=${account.id}`}>New quote</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
