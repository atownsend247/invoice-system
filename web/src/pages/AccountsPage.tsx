import { type FormEvent, useState } from 'react'
import { Link } from 'react-router-dom'
import * as api from '../api'
import type { CreateAccountInput } from '../api'
import { errorMessage, useAsync } from '../hooks/useAsync'
import type { Account } from '../types'

export function AccountsPage() {
  const { data: accounts, loading, error, refetch } = useAsync(() => api.listAccounts(), [])
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)

  return (
    <section>
      <div className="page-header">
        <h1>Accounts</h1>
        <button
          type="button"
          onClick={() => {
            setShowForm((show) => !show)
            setEditingId(null)
          }}
        >
          {showForm ? 'Cancel' : 'New account'}
        </button>
      </div>

      {showForm && (
        <AccountForm
          submitLabel="Create account"
          submittingLabel="Creating…"
          onSubmit={(input) => api.createAccount(input)}
          onDone={() => {
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
            {accounts.map((account) =>
              editingId === account.id ? (
                <tr key={account.id}>
                  <td colSpan={5}>
                    <AccountForm
                      initial={account}
                      submitLabel="Save"
                      submittingLabel="Saving…"
                      onSubmit={(input) => api.updateAccount(account.id, input)}
                      onDone={() => {
                        setEditingId(null)
                        refetch()
                      }}
                      onCancel={() => setEditingId(null)}
                    />
                  </td>
                </tr>
              ) : (
                <tr key={account.id}>
                  <td>{account.business_name}</td>
                  <td>{account.contact_name ?? '—'}</td>
                  <td>{account.email}</td>
                  <td>{account.address}</td>
                  <td>
                    <button
                      type="button"
                      onClick={() => {
                        setEditingId(account.id)
                        setShowForm(false)
                      }}
                    >
                      Edit
                    </button>{' '}
                    <Link to={`/quotes/new?accountId=${account.id}`}>New quote</Link>
                  </td>
                </tr>
              ),
            )}
          </tbody>
        </table>
      )}
    </section>
  )
}

function AccountForm({
  initial,
  submitLabel,
  submittingLabel,
  onSubmit,
  onDone,
  onCancel,
}: {
  initial?: Account
  submitLabel: string
  submittingLabel: string
  onSubmit: (input: CreateAccountInput) => Promise<Account>
  onDone: () => void
  onCancel?: () => void
}) {
  const [businessName, setBusinessName] = useState(initial?.business_name ?? '')
  const [email, setEmail] = useState(initial?.email ?? '')
  const [address, setAddress] = useState(initial?.address ?? '')
  const [contactName, setContactName] = useState(initial?.contact_name ?? '')
  const [phone, setPhone] = useState(initial?.phone ?? '')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await onSubmit({
        business_name: businessName,
        email,
        address,
        contact_name: contactName || undefined,
        phone: phone || undefined,
      })
      onDone()
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
        {submitting ? submittingLabel : submitLabel}
      </button>
      {onCancel && (
        <button type="button" className="secondary" onClick={onCancel} disabled={submitting}>
          Cancel
        </button>
      )}
    </form>
  )
}
