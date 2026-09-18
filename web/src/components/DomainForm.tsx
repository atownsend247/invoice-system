import { type FormEvent, useState } from 'react'
import type { SaveDomainInput } from '../api'
import { errorMessage } from '../hooks/useAsync'
import type { Domain } from '../types'

export function DomainForm({
  initial,
  submitLabel,
  submittingLabel,
  onSubmit,
  onDone,
  onCancel,
}: {
  initial?: Domain
  submitLabel: string
  submittingLabel: string
  onSubmit: (input: SaveDomainInput) => Promise<Domain>
  onDone: (domain: Domain) => void
  onCancel?: () => void
}) {
  const [domainName, setDomainName] = useState(initial?.domain_name ?? '')
  const [expiryDate, setExpiryDate] = useState(initial?.expiry_date ?? '')
  const [registrar, setRegistrar] = useState(initial?.registrar ?? '')
  const [autoRenew, setAutoRenew] = useState(initial?.auto_renew ?? false)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const domain = await onSubmit({
        domain_name: domainName,
        expiry_date: expiryDate,
        registrar,
        auto_renew: autoRenew,
      })
      onDone(domain)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form className="inline-form" onSubmit={handleSubmit}>
      <label>
        Domain name
        <input value={domainName} onChange={(event) => setDomainName(event.target.value)} required />
      </label>
      <label>
        Expiry date
        <input
          type="date"
          value={expiryDate}
          onChange={(event) => setExpiryDate(event.target.value)}
          required
        />
      </label>
      <label>
        Registrar
        <input value={registrar} onChange={(event) => setRegistrar(event.target.value)} required />
      </label>
      <label className="checkbox-field">
        <input
          type="checkbox"
          checked={autoRenew}
          onChange={(event) => setAutoRenew(event.target.checked)}
        />
        Auto-renew
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
