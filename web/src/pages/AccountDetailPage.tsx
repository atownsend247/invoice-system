import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { accountAddressLines } from '../accountAddress'
import * as api from '../api'
import { AccountForm } from '../components/AccountForm'
import { StatusBadge } from '../components/StatusBadge'
import { useAsync } from '../hooks/useAsync'
import type { Expense, Invoice, Quote } from '../types'

/** Newest first by issue_date (the "when this was created" convention used
 * throughout - see CLAUDE.md). Ids are random UUID4s now (see CLAUDE.md),
 * with no ordering relationship to insertion order, so there's no id-based
 * tie-breaker for same-day entries anymore - instead this relies on the
 * API already returning items oldest-first (the backend orders by SQLite's
 * implicit rowid - see sqlite_repository.py) and Array.sort's stability
 * (guaranteed since ES2019): reversing to newest-insertion-first, then a
 * stable sort by issue_date descending, keeps a same-day group in
 * newest-insertion-first order too. */
function byIssueDateNewestFirst<T extends { issue_date: string }>(items: T[]): T[] {
  return [...items].reverse().sort((a, b) => b.issue_date.localeCompare(a.issue_date))
}

export function AccountDetailPage() {
  const { id: accountId } = useParams()
  const {
    data: account,
    loading,
    error,
    refetch,
  } = useAsync(() => api.getAccount(accountId ?? ''), [accountId])
  const { data: quotes } = useAsync(() => api.listQuotes(accountId), [accountId])
  const { data: invoices } = useAsync(() => api.listInvoices(accountId), [accountId])
  const { data: expenses } = useAsync(() => api.listExpenses(accountId), [accountId])
  const [editing, setEditing] = useState(false)

  if (loading) return <p>Loading…</p>
  if (error)
    return (
      <p className="form-error" role="alert">
        {error}
      </p>
    )
  if (!account) return null

  return (
    <section>
      <div className="page-header">
        <h1>{account.business_name}</h1>
        {!editing && (
          <button type="button" onClick={() => setEditing(true)}>
            Edit
          </button>
        )}
      </div>

      {editing ? (
        <AccountForm
          initial={account}
          submitLabel="Save"
          submittingLabel="Saving…"
          onSubmit={(input) => api.updateAccount(account.id, input)}
          onDone={() => {
            setEditing(false)
            refetch()
          }}
          onCancel={() => setEditing(false)}
        />
      ) : (
        <dl className="account-details">
          <div>
            <dt>Contact</dt>
            <dd>{account.contact_name ?? '—'}</dd>
          </div>
          <div>
            <dt>Email</dt>
            <dd>{account.email}</dd>
          </div>
          <div>
            <dt>Phone</dt>
            <dd>{account.phone ?? '—'}</dd>
          </div>
          <div>
            <dt>Address</dt>
            <dd>
              {accountAddressLines(account).map((line) => (
                // Address lines have no stable id of their own and never
                // reorder within a render - the line text is a safe key.
                <span key={line}>
                  {line}
                  <br />
                </span>
              ))}
            </dd>
          </div>
        </dl>
      )}

      <div className="dashboard-section">
        <div className="page-header">
          <h2>Quotes</h2>
          <Link className="button" to={`/quotes/new?accountId=${account.id}`}>
            New quote
          </Link>
        </div>
        {!quotes && <p>Loading…</p>}
        {quotes && quotes.length === 0 && <p className="meta">No quotes yet.</p>}
        {quotes && quotes.length > 0 && <QuotesTable quotes={byIssueDateNewestFirst(quotes)} />}
      </div>

      <div className="dashboard-section">
        <h2>Invoices</h2>
        {!invoices && <p>Loading…</p>}
        {invoices && invoices.length === 0 && <p className="meta">No invoices yet.</p>}
        {invoices && invoices.length > 0 && <InvoicesTable invoices={byIssueDateNewestFirst(invoices)} />}
      </div>

      <div className="dashboard-section">
        <div className="page-header">
          <h2>Expenses</h2>
          <Link className="button" to={`/expenses/new?accountId=${account.id}`}>
            New expense
          </Link>
        </div>
        {!expenses && <p>Loading…</p>}
        {expenses && expenses.length === 0 && <p className="meta">No expenses recorded yet.</p>}
        {expenses && expenses.length > 0 && <ExpensesTable expenses={byIssueDateNewestFirst(expenses)} />}
      </div>
    </section>
  )
}

function QuotesTable({ quotes }: { quotes: Quote[] }) {
  return (
    <table>
      <thead>
        <tr>
          <th>Number</th>
          <th>Status</th>
          <th>Issued</th>
          <th>Total</th>
          <th />
        </tr>
      </thead>
      <tbody>
        {quotes.map((quote) => (
          <tr key={quote.id}>
            <td>{quote.number ?? `draft #${quote.id}`}</td>
            <td>
              <StatusBadge status={quote.status} />
            </td>
            <td>{quote.issue_date}</td>
            <td>
              {quote.total} {quote.currency}
            </td>
            <td>
              <Link to={`/quotes/${quote.id}`}>View</Link>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function ExpensesTable({ expenses }: { expenses: Expense[] }) {
  return (
    <table>
      <thead>
        <tr>
          <th>Number</th>
          <th>Recorded</th>
          <th>Total</th>
          <th />
        </tr>
      </thead>
      <tbody>
        {expenses.map((expense) => (
          <tr key={expense.id}>
            <td>{expense.number}</td>
            <td>{expense.issue_date}</td>
            <td>
              {expense.total} {expense.currency}
            </td>
            <td>
              <Link to={`/expenses/${expense.id}`}>View</Link>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function InvoicesTable({ invoices }: { invoices: Invoice[] }) {
  return (
    <table>
      <thead>
        <tr>
          <th>Number</th>
          <th>Status</th>
          <th>Issued</th>
          <th>Total</th>
          <th />
        </tr>
      </thead>
      <tbody>
        {invoices.map((invoice) => (
          <tr key={invoice.id}>
            <td>{invoice.number ?? `draft #${invoice.id}`}</td>
            <td>
              <StatusBadge status={invoice.status} />
            </td>
            <td>{invoice.issue_date}</td>
            <td>
              {invoice.total} {invoice.currency}
            </td>
            <td>
              <Link to={`/invoices/${invoice.id}`}>View</Link>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
