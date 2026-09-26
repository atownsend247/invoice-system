import { type FormEvent, useState } from 'react'
import type { SaveAccountHostingProviderInput } from '../api'
import { errorMessage } from '../hooks/useAsync'
import type { AccountHostingProvider, HostingProvider } from '../types'

export function AccountHostingProviderForm({
  initial,
  hostingProviders,
  submitLabel,
  submittingLabel,
  onSubmit,
  onDone,
  onCancel,
}: {
  initial?: AccountHostingProvider
  // The managed hosting-provider list (see the Domains page's own Hosting
  // providers section) - fetched once by the caller and passed down, same
  // reasoning as DomainForm.tsx's own `registrars` prop.
  hostingProviders: HostingProvider[]
  submitLabel: string
  submittingLabel: string
  onSubmit: (input: SaveAccountHostingProviderInput) => Promise<AccountHostingProvider>
  onDone: (link: AccountHostingProvider) => void
  onCancel?: () => void
}) {
  const [hostingProviderId, setHostingProviderId] = useState(initial?.hosting_provider_id ?? '')
  const [notes, setNotes] = useState(initial?.notes ?? '')
  const [providerAccountId, setProviderAccountId] = useState(initial?.provider_account_id ?? '')
  const [providerEmail, setProviderEmail] = useState(initial?.provider_email ?? '')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  // A link's already-recorded hosting_provider_id can point at a provider
  // since renamed - not possible to lose since links reference an id, not
  // a name (see CLAUDE.md), but the id could still be missing from the
  // current list if it's since been deleted (blocked while any link still
  // references it, but a link created before that guard existed in an
  // older revision could still dangle) - same defensive prepend
  // DomainForm.tsx uses for `registrar`.
  const providerIds = hostingProviders.map((p) => p.id)
  const providerOptions =
    initial && !providerIds.includes(initial.hosting_provider_id)
      ? [{ id: initial.hosting_provider_id, name: initial.hosting_provider_name }, ...hostingProviders]
      : hostingProviders

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const link = await onSubmit({
        hosting_provider_id: hostingProviderId,
        notes: notes || undefined,
        provider_account_id: providerAccountId || undefined,
        provider_email: providerEmail || undefined,
      })
      onDone(link)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  const noProvidersAvailable = providerOptions.length === 0

  return (
    <form className="inline-form" onSubmit={handleSubmit}>
      <label>
        Hosting provider
        <select
          value={hostingProviderId}
          onChange={(event) => setHostingProviderId(event.target.value)}
          disabled={noProvidersAvailable}
          required
        >
          <option value="" disabled>
            {noProvidersAvailable ? 'No hosting providers configured' : 'Select a hosting provider'}
          </option>
          {providerOptions.map((provider) => (
            <option key={provider.id} value={provider.id}>
              {provider.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Notes (optional)
        <input value={notes} onChange={(event) => setNotes(event.target.value)} />
      </label>
      <label>
        Provider account/customer reference (optional)
        <input value={providerAccountId} onChange={(event) => setProviderAccountId(event.target.value)} />
      </label>
      <label>
        Email used at provider (optional)
        <input
          type="email"
          value={providerEmail}
          onChange={(event) => setProviderEmail(event.target.value)}
        />
      </label>
      {noProvidersAvailable && (
        <p className="meta">Add a hosting provider in the Domains section first.</p>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <button type="submit" disabled={submitting || !hostingProviderId}>
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
