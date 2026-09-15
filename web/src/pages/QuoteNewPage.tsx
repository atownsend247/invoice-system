import { type FormEvent, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import * as api from '../api'
import { errorMessage, useAsync } from '../hooks/useAsync'

export function QuoteNewPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { data: accounts, loading } = useAsync(() => api.listAccounts(), [])
  const [accountId, setAccountId] = useState(searchParams.get('accountId') ?? '')
  const [currency, setCurrency] = useState('USD')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!accountId) return
    setError(null)
    setSubmitting(true)
    try {
      const quote = await api.createQuote(Number(accountId), currency)
      navigate(`/quotes/${quote.id}`, { replace: true })
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section>
      <h1>New quote</h1>
      {loading && <p>Loading accounts…</p>}
      {accounts && accounts.length === 0 && <p>Create an account first.</p>}
      {accounts && accounts.length > 0 && (
        <form className="inline-form" onSubmit={handleSubmit}>
          <label>
            Account
            <select value={accountId} onChange={(event) => setAccountId(event.target.value)} required>
              <option value="" disabled>
                Select an account
              </option>
              {accounts.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.business_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Currency
            <input
              value={currency}
              onChange={(event) => setCurrency(event.target.value.toUpperCase())}
              maxLength={3}
              required
            />
          </label>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <button type="submit" disabled={submitting}>
            {submitting ? 'Creating…' : 'Create draft quote'}
          </button>
        </form>
      )}
    </section>
  )
}
