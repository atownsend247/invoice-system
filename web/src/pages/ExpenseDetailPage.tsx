import { useState } from 'react'
import { useParams } from 'react-router-dom'
import * as api from '../api'
import { LineItemsTable } from '../components/LineItemsTable'
import { PdfViewerModal } from '../components/PdfViewerModal'
import { errorMessage, useAsync } from '../hooks/useAsync'

export function ExpenseDetailPage() {
  const { id: expenseId } = useParams()
  const {
    data: expense,
    loading,
    error,
    refetch,
  } = useAsync(() => api.getExpense(expenseId ?? ''), [expenseId])
  const { data: account } = useAsync(
    () => (expense ? api.getAccount(expense.account_id) : Promise.resolve(null)),
    [expense?.account_id],
  )
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
  if (!expense) return null

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
      <div className="page-header">
        <h1>{expense.number}</h1>
      </div>
      <p className="meta">
        {account?.business_name ?? `Account #${expense.account_id}`} · recorded {expense.issue_date}
      </p>

      <LineItemsTable
        lineItems={expense.line_items}
        currency={expense.currency}
        subtotal={expense.subtotal}
        taxTotal={expense.tax_total}
        total={expense.total}
        onAdd={async (input) => {
          await api.addExpenseLineItem(expense.id, input)
          refetch()
        }}
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
              setPdfUrl(await api.getExpensePdfUrl(expense))
            })
          }
        >
          View PDF
        </button>
        <button type="button" disabled={busy} onClick={() => run(() => api.downloadExpensePdf(expense))}>
          Download PDF
        </button>
      </div>

      <PdfViewerModal url={pdfUrl} title={expense.number} onClose={closePdfPreview} />
    </section>
  )
}
