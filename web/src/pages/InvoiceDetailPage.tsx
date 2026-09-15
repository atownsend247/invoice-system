import { useState } from 'react'
import { useParams } from 'react-router-dom'
import * as api from '../api'
import { LineItemsTable } from '../components/LineItemsTable'
import { StatusBadge } from '../components/StatusBadge'
import { errorMessage, useAsync } from '../hooks/useAsync'

export function InvoiceDetailPage() {
  const { id } = useParams()
  const invoiceId = Number(id)
  const { data: invoice, loading, error, refetch } = useAsync(() => api.getInvoice(invoiceId), [invoiceId])
  const { data: account } = useAsync(
    () => (invoice ? api.getAccount(invoice.account_id) : Promise.resolve(null)),
    [invoice?.account_id],
  )
  const [actionError, setActionError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (loading) return <p>Loading…</p>
  if (error)
    return (
      <p className="form-error" role="alert">
        {error}
      </p>
    )
  if (!invoice) return null

  async function run(action: () => Promise<void>) {
    setActionError(null)
    setBusy(true)
    try {
      await action()
    } catch (err) {
      setActionError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const canVoid = invoice.status !== 'paid' && invoice.status !== 'void'

  return (
    <section>
      <div className="page-header">
        <h1>{invoice.number ?? `Draft invoice #${invoice.id}`}</h1>
        <StatusBadge status={invoice.status} />
      </div>
      <p className="meta">
        {account?.business_name ?? `Account #${invoice.account_id}`} · issued {invoice.issue_date}
        {invoice.due_date && <> · due {invoice.due_date}</>}
        {invoice.quote_id && <> · converted from quote #{invoice.quote_id}</>}
      </p>

      <LineItemsTable lineItems={invoice.line_items} currency={invoice.currency} total={invoice.total} />

      {actionError && (
        <p className="form-error" role="alert">
          {actionError}
        </p>
      )}

      <div className="actions">
        <button type="button" disabled={busy} onClick={() => run(() => api.downloadInvoicePdf(invoice))}>
          Download PDF
        </button>
        {invoice.status === 'draft' && (
          <button
            type="button"
            disabled={busy || invoice.line_items.length === 0}
            onClick={() =>
              run(async () => {
                await api.sendInvoice(invoice.id)
                refetch()
              })
            }
          >
            Send
          </button>
        )}
        {canVoid && (
          <button
            type="button"
            disabled={busy}
            onClick={() =>
              run(async () => {
                await api.voidInvoice(invoice.id)
                refetch()
              })
            }
          >
            Void
          </button>
        )}
      </div>
    </section>
  )
}
