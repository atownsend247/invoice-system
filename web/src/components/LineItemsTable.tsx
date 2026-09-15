import { type FormEvent, useState } from 'react'
import { errorMessage } from '../hooks/useAsync'
import type { LineItem } from '../types'

interface Props {
  lineItems: LineItem[]
  currency: string
  total: string
  /** Only quotes support adding line items through the API while draft -
   * invoices are populated once, at conversion time (see docs/api.md). */
  onAdd?: (input: { description: string; quantity: string; unit_price: string }) => Promise<void>
}

export function LineItemsTable({ lineItems, currency, total, onAdd }: Props) {
  return (
    <div className="line-items">
      <table>
        <thead>
          <tr>
            <th>Description</th>
            <th>Qty</th>
            <th>Unit price</th>
            <th>Total</th>
          </tr>
        </thead>
        <tbody>
          {lineItems.map((item) => (
            <tr key={item.id}>
              <td>{item.description}</td>
              <td>{item.quantity}</td>
              <td>
                {item.unit_price} {currency}
              </td>
              <td>
                {item.total} {currency}
              </td>
            </tr>
          ))}
          {lineItems.length === 0 && (
            <tr>
              <td colSpan={4} className="empty">
                No line items yet.
              </td>
            </tr>
          )}
        </tbody>
        <tfoot>
          <tr>
            <td colSpan={3}>Total</td>
            <td>
              {total} {currency}
            </td>
          </tr>
        </tfoot>
      </table>

      {onAdd && <AddLineItemForm onAdd={onAdd} />}
    </div>
  )
}

function AddLineItemForm({ onAdd }: { onAdd: NonNullable<Props['onAdd']> }) {
  const [description, setDescription] = useState('')
  const [quantity, setQuantity] = useState('1')
  const [unitPrice, setUnitPrice] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await onAdd({ description, quantity, unit_price: unitPrice })
      setDescription('')
      setQuantity('1')
      setUnitPrice('')
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form className="inline-form line-item-form" onSubmit={handleSubmit}>
      <label>
        Description
        <input value={description} onChange={(event) => setDescription(event.target.value)} required />
      </label>
      <label>
        Qty
        <input value={quantity} onChange={(event) => setQuantity(event.target.value)} inputMode="decimal" required />
      </label>
      <label>
        Unit price
        <input
          value={unitPrice}
          onChange={(event) => setUnitPrice(event.target.value)}
          inputMode="decimal"
          required
        />
      </label>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <button type="submit" disabled={submitting}>
        {submitting ? 'Adding…' : 'Add item'}
      </button>
    </form>
  )
}
