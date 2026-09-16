import { type FormEvent, useState } from 'react'
import type { CreateAccountInput } from '../api'
import { errorMessage } from '../hooks/useAsync'
import type { Account } from '../types'

export function AccountForm({
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
  onDone: (account: Account) => void
  onCancel?: () => void
}) {
  const [businessName, setBusinessName] = useState(initial?.business_name ?? '')
  const [email, setEmail] = useState(initial?.email ?? '')
  const [addressLine1, setAddressLine1] = useState(initial?.address_line1 ?? '')
  const [addressLine2, setAddressLine2] = useState(initial?.address_line2 ?? '')
  const [townOrCity, setTownOrCity] = useState(initial?.town_or_city ?? '')
  const [county, setCounty] = useState(initial?.county ?? '')
  const [postcode, setPostcode] = useState(initial?.postcode ?? '')
  const [contactName, setContactName] = useState(initial?.contact_name ?? '')
  const [phone, setPhone] = useState(initial?.phone ?? '')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const account = await onSubmit({
        business_name: businessName,
        email,
        address_line1: addressLine1,
        contact_name: contactName || undefined,
        phone: phone || undefined,
        address_line2: addressLine2 || undefined,
        town_or_city: townOrCity || undefined,
        county: county || undefined,
        postcode: postcode || undefined,
      })
      onDone(account)
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
        Contact name
        <input value={contactName} onChange={(event) => setContactName(event.target.value)} />
      </label>
      <label>
        Phone
        <input value={phone} onChange={(event) => setPhone(event.target.value)} />
      </label>
      <label>
        Address line 1
        <input value={addressLine1} onChange={(event) => setAddressLine1(event.target.value)} required />
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
