import { type FormEvent, useState } from 'react'
import type { SaveDomainInput } from '../api'
import { errorMessage } from '../hooks/useAsync'
import type { Domain, Registrar } from '../types'

export function DomainForm({
  initial,
  registrars,
  submitLabel,
  submittingLabel,
  onSubmit,
  onDone,
  onCancel,
}: {
  initial?: Domain
  // The managed registrar list (see Settings > Registrars) - fetched once
  // by the caller (AccountDetailPage.tsx) and passed down, not re-fetched
  // per form instance. The Registrar field is a strict <select> sourced
  // from this list, not free text - see CLAUDE.md.
  registrars: Registrar[]
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

  // A domain recorded before this feature existed - or whose registrar
  // was since renamed/deleted from the managed list - can hold a
  // registrar string that isn't one of the current options. Prepend it
  // rather than silently dropping it, so opening "Edit" never changes the
  // value just by rendering the form (see CLAUDE.md).
  const registrarNames = registrars.map((r) => r.name)
  const registrarOptions =
    initial?.registrar && !registrarNames.includes(initial.registrar)
      ? [initial.registrar, ...registrarNames]
      : registrarNames
  const noRegistrarsAvailable = registrarOptions.length === 0

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
        <select
          value={registrar}
          onChange={(event) => setRegistrar(event.target.value)}
          required
          disabled={noRegistrarsAvailable}
        >
          <option value="" disabled>
            {noRegistrarsAvailable ? 'No registrars configured' : 'Select a registrar'}
          </option>
          {registrarOptions.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
      </label>
      <label className="checkbox-field">
        <input
          type="checkbox"
          checked={autoRenew}
          onChange={(event) => setAutoRenew(event.target.checked)}
        />
        Auto-renew
      </label>
      {noRegistrarsAvailable && (
        <p className="meta">No registrars configured yet - add one in Settings first.</p>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <button type="submit" disabled={submitting || noRegistrarsAvailable}>
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
