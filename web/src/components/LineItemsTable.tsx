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

interface LineItemInput {
  description: string
  quantity: string
  unit_price: string
  tax_rate: string
}

interface Props {
  lineItems: LineItem[]
  currency: string
  subtotal: string
  taxTotal: string
  total: string
  /** Only quotes support adding line items through the API while draft -
   * invoices are populated once, at conversion time (see docs/api.md). */
  onAdd?: (input: LineItemInput) => Promise<void>
  /** Expense-only (see docs/api.md) - editing/removing a quote/invoice line
   * item isn't supported, so Quote/Invoice detail pages simply don't pass
   * these, and the table renders with no actions column at all. */
  onEdit?: (itemId: string, input: LineItemInput) => Promise<void>
  onDelete?: (itemId: string) => Promise<void>
}

export function LineItemsTable({
  lineItems,
  currency,
  subtotal,
  taxTotal,
  total,
  onAdd,
  onEdit,
  onDelete,
}: Props) {
  const hasActions = Boolean(onEdit || onDelete)
  const columnCount = hasActions ? 6 : 5
  const [editingItem, setEditingItem] = useState<LineItem | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  async function handleDelete(item: LineItem) {
    if (!onDelete) return
    setDeleteError(null)
    setDeletingId(item.id)
    try {
      await onDelete(item.id)
      if (editingItem?.id === item.id) setEditingItem(null)
    } catch (err) {
      setDeleteError(errorMessage(err))
    } finally {
      setDeletingId(null)
    }
  }

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
              {hasActions && <th />}
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
                {hasActions && (
                  <td className="actions">
                    {onEdit && (
                      <button
                        type="button"
                        disabled={deletingId === item.id}
                        onClick={() => setEditingItem(item)}
                      >
                        Edit
                      </button>
                    )}
                    {onDelete && (
                      <button
                        type="button"
                        className="secondary"
                        disabled={deletingId === item.id}
                        onClick={() => handleDelete(item)}
                      >
                        {deletingId === item.id ? 'Deleting…' : 'Delete'}
                      </button>
                    )}
                  </td>
                )}
              </tr>
            ))}
            {lineItems.length === 0 && (
              <tr>
                <td colSpan={columnCount} className="empty">
                  No line items yet.
                </td>
              </tr>
            )}
          </tbody>
          <tfoot>
            <tr>
              <td colSpan={columnCount - 1}>Subtotal</td>
              <td>
                {subtotal} {currency}
              </td>
            </tr>
            <tr>
              <td colSpan={columnCount - 1}>VAT</td>
              <td>
                {taxTotal} {currency}
              </td>
            </tr>
            <tr>
              <td colSpan={columnCount - 1}>Total</td>
              <td>
                {total} {currency}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>

      {deleteError && (
        <p className="form-error" role="alert">
          {deleteError}
        </p>
      )}

      {onAdd && (
        <LineItemForm
          key={editingItem?.id ?? 'add'}
          onAdd={onAdd}
          onEdit={onEdit}
          editingItem={editingItem}
          onCancelEdit={() => setEditingItem(null)}
        />
      )}
    </div>
  )
}

function LineItemForm({
  onAdd,
  onEdit,
  editingItem,
  onCancelEdit,
}: {
  onAdd: NonNullable<Props['onAdd']>
  onEdit: Props['onEdit']
  editingItem: LineItem | null
  onCancelEdit: () => void
}) {
  const [description, setDescription] = useState(editingItem?.description ?? '')
  const [quantity, setQuantity] = useState(editingItem?.quantity ?? '1')
  const [unitPrice, setUnitPrice] = useState(editingItem?.unit_price ?? '')
  const [taxRate, setTaxRate] = useState(editingItem?.tax_rate ?? TAX_RATE_OPTIONS[0].value)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const input = { description, quantity, unit_price: unitPrice, tax_rate: taxRate }
      if (editingItem && onEdit) {
        await onEdit(editingItem.id, input)
        onCancelEdit()
      } else {
        await onAdd(input)
        setDescription('')
        setQuantity('1')
        setUnitPrice('')
        setTaxRate(TAX_RATE_OPTIONS[0].value)
      }
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
        {editingItem
          ? submitting
            ? 'Updating…'
            : 'Update item'
          : submitting
            ? 'Adding…'
            : 'Add item'}
      </button>
      {editingItem && (
        <button type="button" className="secondary" disabled={submitting} onClick={onCancelEdit}>
          Cancel
        </button>
      )}
    </form>
  )
}
