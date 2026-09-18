import { type FormEvent, useState } from 'react'
import type { SaveRegistrarInput } from '../api'
import { errorMessage } from '../hooks/useAsync'
import type { Registrar } from '../types'

export function RegistrarForm({
  initial,
  submitLabel,
  submittingLabel,
  onSubmit,
  onDone,
  onCancel,
}: {
  initial?: Registrar
  submitLabel: string
  submittingLabel: string
  onSubmit: (input: SaveRegistrarInput) => Promise<Registrar>
  onDone: (registrar: Registrar) => void
  onCancel?: () => void
}) {
  const [name, setName] = useState(initial?.name ?? '')
  const [notes, setNotes] = useState(initial?.notes ?? '')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const registrar = await onSubmit({ name, notes: notes || undefined })
      onDone(registrar)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form className="inline-form" onSubmit={handleSubmit}>
      <label>
        Name
        <input value={name} onChange={(event) => setName(event.target.value)} required />
      </label>
      <label>
        Notes (optional)
        <input value={notes} onChange={(event) => setNotes(event.target.value)} />
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
