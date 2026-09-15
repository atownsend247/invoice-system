import { type FormEvent, useState } from 'react'
import * as api from '../api'
import { errorMessage, useAsync } from '../hooks/useAsync'
import type { BusinessProfile } from '../types'

export function SettingsPage() {
  const { data: profile, loading, error } = useAsync(() => api.getBusinessProfile(), [])

  return (
    <section>
      <h1>Settings</h1>
      <p className="meta">Your business details - shown on the quotes and invoices you send.</p>

      {loading && <p>Loading…</p>}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {profile && <BusinessProfileForm profile={profile} />}
    </section>
  )
}

function BusinessProfileForm({ profile }: { profile: BusinessProfile }) {
  const [businessName, setBusinessName] = useState(profile.business_name)
  const [businessAddress, setBusinessAddress] = useState(profile.business_address)
  const [paymentTermsDays, setPaymentTermsDays] = useState(String(profile.payment_terms_days))
  const [utr, setUtr] = useState(profile.utr ?? '')
  const [vatNumber, setVatNumber] = useState(profile.vat_number ?? '')
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSaved(false)
    setSubmitting(true)
    try {
      const updated = await api.saveBusinessProfile({
        business_name: businessName,
        business_address: businessAddress,
        payment_terms_days: Number(paymentTermsDays),
        utr: utr || undefined,
        vat_number: vatNumber || undefined,
      })
      // Reflect what the server actually stored (e.g. a blank UTR is
      // normalised to null) rather than trusting the pre-submit input back.
      setBusinessName(updated.business_name)
      setBusinessAddress(updated.business_address)
      setPaymentTermsDays(String(updated.payment_terms_days))
      setUtr(updated.utr ?? '')
      setVatNumber(updated.vat_number ?? '')
      setSaved(true)
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
        Business address
        <input
          value={businessAddress}
          onChange={(event) => setBusinessAddress(event.target.value)}
          required
        />
      </label>
      <label>
        Payment terms (days)
        <input
          type="number"
          min={1}
          step={1}
          value={paymentTermsDays}
          onChange={(event) => setPaymentTermsDays(event.target.value)}
          required
        />
      </label>
      <label>
        UTR (optional)
        <input value={utr} onChange={(event) => setUtr(event.target.value)} />
      </label>
      <label>
        VAT number (optional)
        <input value={vatNumber} onChange={(event) => setVatNumber(event.target.value)} />
      </label>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {saved && !error && <p className="form-success">Saved.</p>}
      <button type="submit" disabled={submitting}>
        {submitting ? 'Saving…' : 'Save settings'}
      </button>
    </form>
  )
}
