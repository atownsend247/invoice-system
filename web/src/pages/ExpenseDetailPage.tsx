import { type FormEvent, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import * as api from '../api'
import { LineItemsTable } from '../components/LineItemsTable'
import { PdfViewerModal } from '../components/PdfViewerModal'
import { errorMessage, useAsync } from '../hooks/useAsync'

/** A human-readable file size (e.g. "12.3 KB") - exported so the
 * threshold math is unit-testable without rendering the page. */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

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
  const [pdfTitle, setPdfTitle] = useState('')
  const [editingDate, setEditingDate] = useState(false)
  const [expenseDateInput, setExpenseDateInput] = useState('')
  const [dateError, setDateError] = useState<string | null>(null)
  const [savingDate, setSavingDate] = useState(false)

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

  async function handleSaveDate() {
    if (!expense) return
    setDateError(null)
    setSavingDate(true)
    try {
      await api.updateExpenseDate(expense.id, expenseDateInput)
      setEditingDate(false)
      refetch()
    } catch (err) {
      setDateError(errorMessage(err))
    } finally {
      setSavingDate(false)
    }
  }

  return (
    <section>
      <Link to={`/accounts/${expense.account_id}`} className="back-link">
        ← Back to {account?.business_name ?? 'account'}
      </Link>
      <div className="page-header">
        <h1>{expense.number}</h1>
      </div>
      <p className="meta">
        {account?.business_name ?? `Account #${expense.account_id}`} · recorded {expense.issue_date}
      </p>
      <p className="meta expense-date-row">
        Expense date:{' '}
        {editingDate ? (
          <>
            <input
              type="date"
              aria-label="Expense date"
              value={expenseDateInput}
              onChange={(event) => setExpenseDateInput(event.target.value)}
            />
            <button type="button" onClick={handleSaveDate} disabled={savingDate}>
              {savingDate ? 'Saving…' : 'Save'}
            </button>
            <button
              type="button"
              className="secondary"
              onClick={() => setEditingDate(false)}
              disabled={savingDate}
            >
              Cancel
            </button>
          </>
        ) : (
          <>
            {expense.expense_date}{' '}
            <button
              type="button"
              onClick={() => {
                setExpenseDateInput(expense.expense_date)
                setDateError(null)
                setEditingDate(true)
              }}
            >
              Edit
            </button>
          </>
        )}
      </p>
      {dateError && (
        <p className="form-error" role="alert">
          {dateError}
        </p>
      )}

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
              setPdfTitle(expense.number)
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

      <div className="dashboard-section">
        <h2>Attachments</h2>
        {expense.attachments.length === 0 && <p className="meta">No supplementary PDFs uploaded yet.</p>}
        {expense.attachments.length > 0 && (
          <div className="table-scroll">
            <table>
            <thead>
              <tr>
                <th>File</th>
                <th>Size</th>
                <th>Uploaded</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {expense.attachments.map((attachment) => (
                <tr key={attachment.id}>
                  <td>{attachment.filename}</td>
                  <td>{formatFileSize(attachment.size)}</td>
                  <td>{attachment.created_at.slice(0, 10)}</td>
                  <td className="actions">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() =>
                        run(async () => {
                          setPdfTitle(attachment.filename)
                          setPdfUrl(await api.getExpenseAttachmentPdfUrl(expense.id, attachment.id))
                        })
                      }
                    >
                      View
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() =>
                        run(() => api.downloadExpenseAttachment(expense.id, attachment))
                      }
                    >
                      Download
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() =>
                        run(async () => {
                          await api.deleteExpenseAttachment(expense.id, attachment.id)
                          refetch()
                        })
                      }
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
            </table>
          </div>
        )}

        <AttachmentUploadForm
          onUpload={async (file) => {
            await api.uploadExpenseAttachment(expense.id, file)
            refetch()
          }}
        />
      </div>

      <PdfViewerModal url={pdfUrl} title={pdfTitle} onClose={closePdfPreview} />
    </section>
  )
}

function AttachmentUploadForm({ onUpload }: { onUpload: (file: File) => Promise<void> }) {
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!file) return
    setError(null)
    setSubmitting(true)
    try {
      await onUpload(file)
      setFile(null)
      // Controlled <input type="file"> can't be reset via its value prop -
      // clearing the form element itself is the only way to un-select it.
      ;(event.target as HTMLFormElement).reset()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form className="inline-form" onSubmit={handleSubmit}>
      <label>
        Upload a PDF
        <input
          type="file"
          accept="application/pdf"
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          required
        />
      </label>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <button type="submit" disabled={submitting || !file}>
        {submitting ? 'Uploading…' : 'Upload'}
      </button>
    </form>
  )
}
