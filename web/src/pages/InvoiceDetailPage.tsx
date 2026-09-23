import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import * as api from '../api'
import { ActivityTimeline } from '../components/ActivityTimeline'
import { LineItemsTable } from '../components/LineItemsTable'
import { PdfViewerModal } from '../components/PdfViewerModal'
import { StatusBadge } from '../components/StatusBadge'
import { errorMessage, useAsync } from '../hooks/useAsync'

export function InvoiceDetailPage() {
  const { id: invoiceId } = useParams()
  const {
    data: invoice,
    loading,
    error,
    refetch,
  } = useAsync(() => api.getInvoice(invoiceId ?? ''), [invoiceId])
  const { data: account } = useAsync(
    () => (invoice ? api.getAccount(invoice.account_id) : Promise.resolve(null)),
    [invoice?.account_id],
  )
  const [actionError, setActionError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)
  const [editingNotes, setEditingNotes] = useState(false)
  const [customerNotesInput, setCustomerNotesInput] = useState('')
  const [notesError, setNotesError] = useState<string | null>(null)
  const [savingNotes, setSavingNotes] = useState(false)

  function closePdfPreview() {
    if (pdfUrl) URL.revokeObjectURL(pdfUrl)
    setPdfUrl(null)
  }

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

  async function handleSaveNotes() {
    if (!invoice) return
    setNotesError(null)
    setSavingNotes(true)
    try {
      await api.updateInvoiceCustomerNotes(invoice.id, customerNotesInput)
      setEditingNotes(false)
      refetch()
    } catch (err) {
      setNotesError(errorMessage(err))
    } finally {
      setSavingNotes(false)
    }
  }

  const canVoid = invoice.status !== 'paid' && invoice.status !== 'void'
  const canPay = invoice.status === 'sent'

  return (
    <section>
      <Link to={`/accounts/${invoice.account_id}`} className="back-link">
        ← Back to {account?.business_name ?? 'account'}
      </Link>
      <div className="page-header">
        <h1>{invoice.number ?? `Draft invoice #${invoice.id}`}</h1>
        <StatusBadge status={invoice.status} />
      </div>
      <p className="meta">
        {account?.business_name ?? `Account #${invoice.account_id}`} · issued {invoice.issue_date}
        {invoice.due_date && <> · due {invoice.due_date}</>}
        {invoice.quote_id && <> · converted from quote #{invoice.quote_id}</>}
      </p>

      <div className="customer-notes-section">
        <h2>Customer notes</h2>
        {editingNotes ? (
          <>
            <textarea
              aria-label="Customer notes"
              value={customerNotesInput}
              onChange={(event) => setCustomerNotesInput(event.target.value)}
              rows={3}
            />
            <div className="actions">
              <button type="button" onClick={handleSaveNotes} disabled={savingNotes}>
                {savingNotes ? 'Saving…' : 'Save'}
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => setEditingNotes(false)}
                disabled={savingNotes}
              >
                Cancel
              </button>
            </div>
          </>
        ) : (
          <>
            {invoice.customer_notes ? (
              <p className="customer-notes-text">{invoice.customer_notes}</p>
            ) : (
              <p className="meta">No customer notes yet.</p>
            )}
            <button
              type="button"
              onClick={() => {
                setCustomerNotesInput(invoice.customer_notes ?? '')
                setNotesError(null)
                setEditingNotes(true)
              }}
            >
              Edit
            </button>
          </>
        )}
        {notesError && (
          <p className="form-error" role="alert">
            {notesError}
          </p>
        )}
      </div>

      <LineItemsTable
        lineItems={invoice.line_items}
        currency={invoice.currency}
        subtotal={invoice.subtotal}
        taxTotal={invoice.tax_total}
        total={invoice.total}
      />

      {actionError && (
        <p className="form-error" role="alert">
          {actionError}
        </p>
      )}

      <div className="actions">
        <button
          type="button"
          disabled={busy}
          onClick={() =>
            run(async () => {
              setPdfUrl(await api.getInvoicePdfUrl(invoice))
            })
          }
        >
          View PDF
        </button>
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
        {canPay && (
          <button
            type="button"
            disabled={busy}
            onClick={() =>
              run(async () => {
                await api.payInvoice(invoice.id)
                refetch()
              })
            }
          >
            Mark as paid
          </button>
        )}
        {canVoid && (
          <button
            type="button"
            className="danger"
            disabled={busy}
            onClick={() => {
              if (!window.confirm('Are you sure you want to mark as void?')) return
              run(async () => {
                await api.voidInvoice(invoice.id)
                refetch()
              })
            }}
          >
            Void
          </button>
        )}
      </div>

      <PdfViewerModal
        url={pdfUrl}
        title={invoice.number ?? `Draft invoice #${invoice.id}`}
        onClose={closePdfPreview}
      />

      <ActivityTimeline events={invoice.events} />
    </section>
  )
}
