import { type FormEvent, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import * as api from '../api'
import { todayLocalDate } from '../dates'
import { errorMessage, useAsync } from '../hooks/useAsync'

export function QuoteNewPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  // pageSize: 200 - every account in the organisation belongs in this
  // dropdown, not just a paginated list page's first page.
  const { data: accountsResult, loading } = useAsync(() => api.listAccounts({ pageSize: 200 }), [])
  const accounts = accountsResult?.items
  const { data: profile } = useAsync(() => api.getBusinessProfile(), [])
  const [accountId, setAccountId] = useState(searchParams.get('accountId') ?? '')
  // null until the user actually edits it, so the field can default to the
  // profile's reporting currency once that loads (falling back to USD
  // before it has) without clobbering an in-progress edit.
  const [currency, setCurrency] = useState<string | null>(null)
  const currencyValue = currency ?? profile?.currency ?? 'USD'
  // Defaults to today but stays overridable to backdate a quote - drives
  // the calculated expiry date (issue_date + the business's configured
  // validity period, see CLAUDE.md/models.BusinessProfile).
  const [issueDate, setIssueDate] = useState(todayLocalDate())
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!accountId) return
    setError(null)
    setSubmitting(true)
    try {
      const quote = await api.createQuote(accountId, currencyValue, issueDate)
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
              value={currencyValue}
              onChange={(event) => setCurrency(event.target.value.toUpperCase())}
              maxLength={3}
              required
            />
          </label>
          <label>
            Issue date
            <input
              type="date"
              value={issueDate}
              onChange={(event) => setIssueDate(event.target.value)}
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
