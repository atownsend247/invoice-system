import { type FormEvent, useState } from 'react'
import { Link } from 'react-router-dom'
import * as api from '../api'
import { errorMessage, useAsync } from '../hooks/useAsync'

export function AccountsPage() {
  const { data: accounts, loading, error, refetch } = useAsync(() => api.listAccounts(), [])
  const [showForm, setShowForm] = useState(false)

  return (
    <section>
      <div className="page-header">
        <h1>Accounts</h1>
        <button type="button" onClick={() => setShowForm((show) => !show)}>
          {showForm ? 'Cancel' : 'New account'}
        </button>
      </div>

      {showForm && (
        <NewAccountForm
          onCreated={() => {
            setShowForm(false)
            refetch()
          }}
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

function NewAccountForm({ onCreated }: { onCreated: () => void }) {
  const [businessName, setBusinessName] = useState('')
  const [email, setEmail] = useState('')
  const [address, setAddress] = useState('')
  const [contactName, setContactName] = useState('')
  const [phone, setPhone] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await api.createAccount({
        business_name: businessName,
        email,
        address,
        contact_name: contactName || undefined,
        phone: phone || undefined,
      })
      onCreated()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form className="inline-form" onSubmit={handleSubmit}>
      <label>
        Business name
        <input value={businessName} onChange={(event) => setBusinessName(event.target.value)} required />
      </label>
      <label>
        Email
        <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
      </label>
      <label>
        Address
        <input value={address} onChange={(event) => setAddress(event.target.value)} required />
      </label>
      <label>
        Contact name
        <input value={contactName} onChange={(event) => setContactName(event.target.value)} />
      </label>
      <label>
        Phone
        <input value={phone} onChange={(event) => setPhone(event.target.value)} />
      </label>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <button type="submit" disabled={submitting}>
        {submitting ? 'Creating…' : 'Create account'}
      </button>
    </form>
  )
}
