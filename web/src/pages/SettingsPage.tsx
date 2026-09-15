import { type FormEvent, useState } from 'react'
import * as api from '../api'
import { errorMessage, useAsync } from '../hooks/useAsync'
import type { BusinessProfile } from '../types'

export function SettingsPage() {
  const { data: profile, loading, error } = useAsync(() => api.getBusinessProfile(), [])

  return (
    <section>
      <h1>Settings</h1>
      <p className="meta">Your details - shown on the quotes and invoices you send.</p>

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
  const [title, setTitle] = useState(profile.title ?? '')
  const [firstName, setFirstName] = useState(profile.first_name)
  const [lastName, setLastName] = useState(profile.last_name)
  const [businessName, setBusinessName] = useState(profile.business_name)
  const [addressLine1, setAddressLine1] = useState(profile.address_line1 ?? '')
  const [addressLine2, setAddressLine2] = useState(profile.address_line2 ?? '')
  const [townOrCity, setTownOrCity] = useState(profile.town_or_city ?? '')
  const [county, setCounty] = useState(profile.county ?? '')
  const [postcode, setPostcode] = useState(profile.postcode ?? '')
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
        title: title || undefined,
        first_name: firstName,
        last_name: lastName,
        business_name: businessName,
        address_line1: addressLine1 || undefined,
        address_line2: addressLine2 || undefined,
        town_or_city: townOrCity || undefined,
        county: county || undefined,
        postcode: postcode || undefined,
        payment_terms_days: Number(paymentTermsDays),
        utr: utr || undefined,
        vat_number: vatNumber || undefined,
      })
      // Reflect what the server actually stored (e.g. a blank UTR is
      // normalised to null) rather than trusting the pre-submit input back.
      setTitle(updated.title ?? '')
      setFirstName(updated.first_name)
      setLastName(updated.last_name)
      setBusinessName(updated.business_name)
      setAddressLine1(updated.address_line1 ?? '')
      setAddressLine2(updated.address_line2 ?? '')
      setTownOrCity(updated.town_or_city ?? '')
      setCounty(updated.county ?? '')
      setPostcode(updated.postcode ?? '')
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
    <form className="settings-form" onSubmit={handleSubmit}>
      <fieldset className="form-section">
        <legend>User settings</legend>
        <div className="form-section-fields">
          <label>
            Title (optional)
            <input value={title} onChange={(event) => setTitle(event.target.value)} />
          </label>
          <label>
            First name
            <input value={firstName} onChange={(event) => setFirstName(event.target.value)} required />
          </label>
          <label>
            Last name
            <input value={lastName} onChange={(event) => setLastName(event.target.value)} required />
          </label>
        </div>
      </fieldset>

      <fieldset className="form-section">
        <legend>Business settings</legend>
        <div className="form-section-fields">
          <label>
            Business name
            <input value={businessName} onChange={(event) => setBusinessName(event.target.value)} required />
          </label>
          <label>
            Address line 1 (optional)
            <input value={addressLine1} onChange={(event) => setAddressLine1(event.target.value)} />
          </label>
          <label>
            Address line 2 (optional)
            <input value={addressLine2} onChange={(event) => setAddressLine2(event.target.value)} />
          </label>
          <label>
            Town or city (optional)
            <input value={townOrCity} onChange={(event) => setTownOrCity(event.target.value)} />
          </label>
          <label>
            County (optional)
            <input value={county} onChange={(event) => setCounty(event.target.value)} />
          </label>
          <label>
            Postcode (optional)
            <input value={postcode} onChange={(event) => setPostcode(event.target.value)} />
          </label>
        </div>
      </fieldset>

      <fieldset className="form-section">
        <legend>Payment and tax settings</legend>
        <div className="form-section-fields">
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
        </div>
      </fieldset>

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
