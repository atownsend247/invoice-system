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
      const account = await onSubmit({
        business_name: businessName,
        email,
        address,
        contact_name: contactName || undefined,
        phone: phone || undefined,
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
