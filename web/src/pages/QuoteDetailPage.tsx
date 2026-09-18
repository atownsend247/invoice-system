import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import * as api from '../api'
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

  return (
    <section>
      <Link to={`/accounts/${quote.account_id}`} className="back-link">
        ← Back to {account?.business_name ?? 'account'}
      </Link>
      <div className="page-header">
        <h1>{quote.number ?? `Draft quote #${quote.id}`}</h1>
        <StatusBadge status={quote.status} />
      </div>
      <p className="meta">
        {account?.business_name ?? `Account #${quote.account_id}`} · issued {quote.issue_date}
        {quote.expiry_date && <> · expires {quote.expiry_date}</>}
      </p>

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
          <button
            type="button"
            disabled={busy}
            onClick={() =>
              run(async () => {
                const invoice = await api.convertQuote(quote.id)
                navigate(`/invoices/${invoice.id}`)
              })
            }
          >
            Convert to invoice
          </button>
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
    </section>
  )
}
