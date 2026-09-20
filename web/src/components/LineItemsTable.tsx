import { type FormEvent, useState } from 'react'
import { errorMessage } from '../hooks/useAsync'
import type { LineItem } from '../types'

// UK VAT rates - the only three a business normally needs to pick from day
// to day. tax_rate is still a plain decimal-string field server-side (see
// CLAUDE.md), so nothing stops a custom rate via the API/CLI; the UI just
// doesn't offer one, since "a dropdown" was the ask.
const TAX_RATE_OPTIONS = [
  { value: '0', label: 'No VAT (0%)' },
  { value: '0.05', label: 'Reduced rate (5%)' },
  { value: '0.20', label: 'Standard rate (20%)' },
]

const percentFormatter = new Intl.NumberFormat(undefined, { style: 'percent' })

/** Intl's percent formatter, not `Number(rate) * 100` - float multiplication
 * on a value like 0.05 can print extra digits (e.g. 5.000000000000001%).
 * Intl.NumberFormat rounds correctly instead. */
function formatTaxRate(rate: string): string {
  return percentFormatter.format(Number(rate))
}

interface Props {
  lineItems: LineItem[]
  currency: string
  subtotal: string
  taxTotal: string
  total: string
  /** Only quotes support adding line items through the API while draft -
   * invoices are populated once, at conversion time (see docs/api.md). */
  onAdd?: (input: {
    description: string
    quantity: string
    unit_price: string
    tax_rate: string
  }) => Promise<void>
}

export function LineItemsTable({ lineItems, currency, subtotal, taxTotal, total, onAdd }: Props) {
  return (
    <div className="line-items">
      <div className="table-scroll">
        <table>
        <thead>
          <tr>
            <th>Description</th>
            <th>Qty</th>
            <th>Unit price</th>
            <th>VAT</th>
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
              <td>{formatTaxRate(item.tax_rate)}</td>
              <td>
                {item.total} {currency}
              </td>
            </tr>
          ))}
          {lineItems.length === 0 && (
            <tr>
              <td colSpan={5} className="empty">
                No line items yet.
              </td>
            </tr>
          )}
        </tbody>
        <tfoot>
          <tr>
            <td colSpan={4}>Subtotal</td>
            <td>
              {subtotal} {currency}
            </td>
          </tr>
          <tr>
            <td colSpan={4}>VAT</td>
            <td>
              {taxTotal} {currency}
            </td>
          </tr>
          <tr>
            <td colSpan={4}>Total</td>
            <td>
              {total} {currency}
            </td>
          </tr>
        </tfoot>
        </table>
      </div>

      {onAdd && <AddLineItemForm onAdd={onAdd} />}
    </div>
  )
}

function AddLineItemForm({ onAdd }: { onAdd: NonNullable<Props['onAdd']> }) {
  const [description, setDescription] = useState('')
  const [quantity, setQuantity] = useState('1')
  const [unitPrice, setUnitPrice] = useState('')
  const [taxRate, setTaxRate] = useState(TAX_RATE_OPTIONS[0].value)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await onAdd({ description, quantity, unit_price: unitPrice, tax_rate: taxRate })
      setDescription('')
      setQuantity('1')
      setUnitPrice('')
      setTaxRate(TAX_RATE_OPTIONS[0].value)
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
      <label>
        VAT rate
        <select value={taxRate} onChange={(event) => setTaxRate(event.target.value)}>
          {TAX_RATE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
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
