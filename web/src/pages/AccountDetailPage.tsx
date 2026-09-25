import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { accountAddressLines } from '../accountAddress'
import * as api from '../api'
import { AccountForm } from '../components/AccountForm'
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
  // This account's own linked domains, plus every organisation domain (to
  // find which ones are currently unlinked and available to link - see
  // LinkDomainAction below). Full CRUD on a domain's own fields now lives
  // on the standalone Domains page, not here - see CLAUDE.md.
  const { data: domains, refetch: refetchDomains } = useAsync(
    () => api.listDomains({ accountId }),
    [accountId],
  )
  const { data: allDomains, refetch: refetchAllDomains } = useAsync(() => api.listDomains(), [])
  // Fetched once here, not per AccountForm instance - same reasoning as
  // DomainsPage.tsx's own registrars fetch for DomainForm.
  const { data: hostingProviders } = useAsync(() => api.listHostingProviders(), [])
  const [editing, setEditing] = useState(false)

  function refetchBothDomainLists() {
    refetchDomains()
    refetchAllDomains()
  }

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
        <StatusBadge status={account.status} />
        {!editing && (
          <button type="button" onClick={() => setEditing(true)}>
            Edit
          </button>
        )}
      </div>

      {editing ? (
        <AccountForm
          initial={account}
          hostingProviders={hostingProviders ?? []}
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
          <div>
            <dt>Hosting provider</dt>
            <dd>{account.hosting_provider ?? '—'}</dd>
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
        </div>
        <p className="meta">
          Link a domain already set up in the <Link to="/domains">Domains</Link> section - full domain/registrar
          management lives there now.
        </p>
        <LinkDomainAction
          unlinkedDomains={(allDomains ?? []).filter((d) => d.account_id === null)}
          loading={!allDomains}
          onLink={(domainId) => api.linkDomain(domainId, account.id)}
          onLinked={refetchBothDomainLists}
        />
        {!domains && <p>Loading…</p>}
        {domains && domains.length === 0 && <p className="meta">No domains linked yet.</p>}
        {domains && domains.length > 0 && (
          <DomainsTable domains={domains} onUnlinked={refetchBothDomainLists} />
        )}
      </div>
    </section>
  )
}

/** An immediate, one-time action - not a persisted field, so a plain
 * self-contained control with its own busy/error/success state, same
 * shape as SettingsPage.tsx's NextNumberAction. Only unlinked domains are
 * offered (see AccountDetailPage's own filter) - a domain already linked
 * elsewhere is re-linked from the Domains page instead, where its current
 * link is visible. */
function LinkDomainAction({
  unlinkedDomains,
  loading,
  onLink,
  onLinked,
}: {
  unlinkedDomains: Domain[]
  loading: boolean
  onLink: (domainId: string) => Promise<Domain>
  onLinked: () => void
}) {
  const [domainId, setDomainId] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const noDomainsAvailable = !loading && unlinkedDomains.length === 0

  async function handleLink() {
    setError(null)
    setSubmitting(true)
    try {
      await onLink(domainId)
      setDomainId('')
      onLinked()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="next-number-action">
      <label>
        Link domain
        <select
          value={domainId}
          onChange={(event) => setDomainId(event.target.value)}
          disabled={loading || noDomainsAvailable}
        >
          <option value="" disabled>
            {loading ? 'Loading…' : noDomainsAvailable ? 'No unlinked domains available' : 'Select a domain'}
          </option>
          {unlinkedDomains.map((domain) => (
            <option key={domain.id} value={domain.id}>
              {domain.domain_name}
            </option>
          ))}
        </select>
      </label>
      <button type="button" disabled={submitting || !domainId} onClick={handleLink}>
        {submitting ? 'Linking…' : 'Link'}
      </button>
      {noDomainsAvailable && (
        <p className="meta">
          No unlinked domains available - add one in <Link to="/domains">Domains</Link> first.
        </p>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}

function QuotesTable({ quotes }: { quotes: Quote[] }) {
  return (
    <div className="table-scroll">
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
    </div>
  )
}

function ExpensesTable({ expenses }: { expenses: Expense[] }) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Number</th>
            <th>Expense date</th>
            <th>Total</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {expenses.map((expense) => (
            <tr key={expense.id}>
              <td>{expense.number}</td>
              <td>{expense.expense_date}</td>
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
    </div>
  )
}

/** Read-only-ish list of this account's own linked domains - just an
 * "Unlink" action per row, not Edit/Delete (full domain management lives
 * on the standalone Domains page now - see CLAUDE.md). Unlinking never
 * deletes the domain itself, just clears its account_id, so it stays
 * available to link elsewhere. */
function DomainsTable({ domains, onUnlinked }: { domains: Domain[]; onUnlinked: () => void }) {
  const [unlinkingId, setUnlinkingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleUnlink(domain: Domain) {
    setError(null)
    setUnlinkingId(domain.id)
    try {
      await api.unlinkDomain(domain.id)
      onUnlinked()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setUnlinkingId(null)
    }
  }

  return (
    <>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <div className="table-scroll">
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
            {domains.map((domain) => (
              <tr key={domain.id}>
                <td>{domain.domain_name}</td>
                <td>{domain.expiry_date}</td>
                <td>{domain.registrar}</td>
                <td>{domain.auto_renew ? 'Yes' : 'No'}</td>
                <td>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => handleUnlink(domain)}
                    disabled={unlinkingId === domain.id}
                  >
                    {unlinkingId === domain.id ? 'Unlinking…' : 'Unlink'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

function InvoicesTable({ invoices }: { invoices: Invoice[] }) {
  return (
    <div className="table-scroll">
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
    </div>
  )
}
