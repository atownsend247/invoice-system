import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { accountAddressLines } from '../accountAddress'
import * as api from '../api'
import { AccountForm } from '../components/AccountForm'
import { DomainForm } from '../components/DomainForm'
import { StatusBadge } from '../components/StatusBadge'
import { errorMessage, useAsync } from '../hooks/useAsync'
import type { Domain, Expense, Invoice, Quote } from '../types'

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
  // pageSize: 200 - this account's own full history, not a paginated list
  // page - see CLAUDE.md/roadmap on why that's a comfortably-generous cap
  // rather than truly unbounded.
  const { data: quotesResult } = useAsync(
    () => api.listQuotes({ accountId, pageSize: 200 }),
    [accountId],
  )
  const { data: invoicesResult } = useAsync(
    () => api.listInvoices({ accountId, pageSize: 200 }),
    [accountId],
  )
  const quotes = quotesResult?.items
  const invoices = invoicesResult?.items
  const { data: expenses } = useAsync(() => api.listExpenses(accountId), [accountId])
  const { data: domains, refetch: refetchDomains } = useAsync(
    () => api.listDomains(accountId ?? ''),
    [accountId],
  )
  const [editing, setEditing] = useState(false)
  const [addingDomain, setAddingDomain] = useState(false)

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

      <div className="dashboard-section">
        <div className="page-header">
          <h2>Domains</h2>
          {!addingDomain && (
            <button type="button" onClick={() => setAddingDomain(true)}>
              Add domain
            </button>
          )}
        </div>
        {addingDomain && (
          <DomainForm
            submitLabel="Add"
            submittingLabel="Adding…"
            onSubmit={(input) => api.createDomain(account.id, input)}
            onDone={() => {
              setAddingDomain(false)
              refetchDomains()
            }}
            onCancel={() => setAddingDomain(false)}
          />
        )}
        {!domains && <p>Loading…</p>}
        {domains && domains.length === 0 && <p className="meta">No domains recorded yet.</p>}
        {domains && domains.length > 0 && (
          <DomainsTable accountId={account.id} domains={domains} onChanged={refetchDomains} />
        )}
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

function DomainsTable({
  accountId,
  domains,
  onChanged,
}: {
  accountId: string
  domains: Domain[]
  onChanged: () => void
}) {
  const [editingId, setEditingId] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleDelete(domain: Domain) {
    setError(null)
    setDeletingId(domain.id)
    try {
      await api.deleteDomain(accountId, domain.id)
      onChanged()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <table>
        <thead>
          <tr>
            <th>Domain</th>
            <th>Expires</th>
            <th>Registrar</th>
            <th>Auto-renew</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {domains.map((domain) =>
            editingId === domain.id ? (
              <tr key={domain.id}>
                <td colSpan={5}>
                  <DomainForm
                    initial={domain}
                    submitLabel="Save"
                    submittingLabel="Saving…"
                    onSubmit={(input) => api.updateDomain(accountId, domain.id, input)}
                    onDone={() => {
                      setEditingId(null)
                      onChanged()
                    }}
                    onCancel={() => setEditingId(null)}
                  />
                </td>
              </tr>
            ) : (
              <tr key={domain.id}>
                <td>{domain.domain_name}</td>
                <td>{domain.expiry_date}</td>
                <td>{domain.registrar}</td>
                <td>{domain.auto_renew ? 'Yes' : 'No'}</td>
                <td>
                  <button type="button" onClick={() => setEditingId(domain.id)}>
                    Edit
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => handleDelete(domain)}
                    disabled={deletingId === domain.id}
                  >
                    {deletingId === domain.id ? 'Deleting…' : 'Delete'}
                  </button>
                </td>
              </tr>
            ),
          )}
        </tbody>
      </table>
    </>
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
