import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import * as api from '../api'
import { ActivityTimeline } from '../components/ActivityTimeline'
import { LineItemsTable } from '../components/LineItemsTable'
import { PdfViewerModal } from '../components/PdfViewerModal'
import { StatusBadge } from '../components/StatusBadge'
import { errorMessage, useAsync } from '../hooks/useAsync'

export function QuoteDetailPage() {
  const { id: quoteId } = useParams()
  const navigate = useNavigate()
  const { data: quote, loading, error, refetch } = useAsync(() => api.getQuote(quoteId ?? ''), [quoteId])
  const { data: account } = useAsync(
    () => (quote ? api.getAccount(quote.account_id) : Promise.resolve(null)),
    [quote?.account_id],
  )
  // A quote converts to at most one invoice, so this filtered lookup ever
  // returns 0 or 1 - only fetched once converted, since before then there's
  // nothing to find. Lets a converted quote link back to the invoice it
  // became even after navigating away and back (the initial "Convert to
  // invoice" action already redirects straight there - see below - but
  // that redirect only happens once, at conversion time).
  const { data: convertedInvoices } = useAsync(
    () =>
      quote?.status === 'converted'
        ? api.listInvoices({ quoteId: quote.id, pageSize: 1 })
        : Promise.resolve(null),
    [quote?.id, quote?.status],
  )
  const convertedInvoice = convertedInvoices?.items[0]
  const [actionError, setActionError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)
  // Optional backdating for the resulting invoice - blank means "today"
  // (see CLAUDE.md/QuoteService.convert_to_invoice).
  const [convertIssueDate, setConvertIssueDate] = useState('')
  const [editingDetails, setEditingDetails] = useState(false)
  const [currencyInput, setCurrencyInput] = useState('')
  const [issueDateInput, setIssueDateInput] = useState('')
  const [detailsError, setDetailsError] = useState<string | null>(null)
  const [savingDetails, setSavingDetails] = useState(false)

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
  if (!quote) return null

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

  async function handleSaveDetails() {
    if (!quote) return
    setDetailsError(null)
    setSavingDetails(true)
    try {
      await api.updateQuote(quote.id, { currency: currencyInput, issue_date: issueDateInput })
      setEditingDetails(false)
      refetch()
    } catch (err) {
      setDetailsError(errorMessage(err))
    } finally {
      setSavingDetails(false)
    }
  }

  return (
    <section>
      <Link to={`/accounts/${quote.account_id}`} className="back-link">
        ← Back to {account?.business_name ?? 'account'}
      </Link>
      <div className="page-header">
        <h1>{quote.number ?? `Draft quote #${quote.id}`}</h1>
        <StatusBadge status={quote.status} />
      </div>
      <p className="meta quote-details-row">
        {account?.business_name ?? `Account #${quote.account_id}`} ·{' '}
        {editingDetails ? (
          <>
            <label>
              Currency
              <input
                value={currencyInput}
                onChange={(event) => setCurrencyInput(event.target.value.toUpperCase())}
                maxLength={3}
              />
            </label>
            <label>
              Issue date
              <input
                type="date"
                value={issueDateInput}
                onChange={(event) => setIssueDateInput(event.target.value)}
              />
            </label>
            <button type="button" onClick={handleSaveDetails} disabled={savingDetails}>
              {savingDetails ? 'Saving…' : 'Save'}
            </button>
            <button
              type="button"
              className="secondary"
              onClick={() => setEditingDetails(false)}
              disabled={savingDetails}
            >
              Cancel
            </button>
          </>
        ) : (
          <>
            issued {quote.issue_date}
            {quote.expiry_date && <> · expires {quote.expiry_date}</>} · {quote.currency}{' '}
            {quote.status === 'draft' && (
              <button
                type="button"
                onClick={() => {
                  setCurrencyInput(quote.currency)
                  setIssueDateInput(quote.issue_date)
                  setDetailsError(null)
                  setEditingDetails(true)
                }}
              >
                Edit
              </button>
            )}
          </>
        )}
      </p>
      {detailsError && (
        <p className="form-error" role="alert">
          {detailsError}
        </p>
      )}

      <LineItemsTable
        lineItems={quote.line_items}
        currency={quote.currency}
        subtotal={quote.subtotal}
        taxTotal={quote.tax_total}
        total={quote.total}
        onAdd={
          quote.status === 'draft'
            ? async (input) => {
                await api.addQuoteLineItem(quote.id, input)
                refetch()
              }
            : undefined
        }
        onEdit={
          quote.status === 'draft'
            ? async (itemId, input) => {
                await api.updateQuoteLineItem(quote.id, itemId, input)
                refetch()
              }
            : undefined
        }
        onDelete={
          quote.status === 'draft'
            ? async (itemId) => {
                await api.deleteQuoteLineItem(quote.id, itemId)
                refetch()
              }
            : undefined
        }
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
              setPdfUrl(await api.getQuotePdfUrl(quote))
            })
          }
        >
          View PDF
        </button>
        <button type="button" disabled={busy} onClick={() => run(() => api.downloadQuotePdf(quote))}>
          Download PDF
        </button>
        {quote.status === 'draft' && (
          <button
            type="button"
            disabled={busy || quote.line_items.length === 0}
            onClick={() =>
              run(async () => {
                await api.sendQuote(quote.id)
                refetch()
              })
            }
          >
            Send
          </button>
        )}
        {(quote.status === 'sent' || quote.status === 'accepted') && (
          <span className="convert-action">
            <label>
              Issue date (optional, defaults to today)
              <input
                type="date"
                value={convertIssueDate}
                onChange={(event) => setConvertIssueDate(event.target.value)}
              />
            </label>
            <button
              type="button"
              disabled={busy}
              onClick={() =>
                run(async () => {
                  const invoice = await api.convertQuote(quote.id, convertIssueDate || undefined)
                  navigate(`/invoices/${invoice.id}`)
                })
              }
            >
              Convert to invoice
            </button>
          </span>
        )}
        {quote.status === 'converted' && convertedInvoice && (
          <button type="button" onClick={() => navigate(`/invoices/${convertedInvoice.id}`)}>
            View invoice
          </button>
        )}
      </div>

      <PdfViewerModal
        url={pdfUrl}
        title={quote.number ?? `Draft quote #${quote.id}`}
        onClose={closePdfPreview}
      />

      <ActivityTimeline events={quote.events} />
    </section>
  )
}
