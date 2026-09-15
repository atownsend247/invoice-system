import { Link } from 'react-router-dom'
import * as api from '../api'
import { StatusBadge } from '../components/StatusBadge'
import { useAsync } from '../hooks/useAsync'

export function InvoicesPage() {
  const { data: invoices, loading, error } = useAsync(() => api.listInvoices(), [])
  const { data: accounts } = useAsync(() => api.listAccounts(), [])

  const accountName = (accountId: number) =>
    accounts?.find((account) => account.id === accountId)?.business_name ?? `#${accountId}`

  return (
    <section>
      <h1>Invoices</h1>

      {loading && <p>Loading…</p>}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {invoices && invoices.length === 0 && <p>No invoices yet — convert a sent quote to create one.</p>}
      {invoices && invoices.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Number</th>
              <th>Account</th>
              <th>Status</th>
              <th>Due</th>
              <th>Total</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {invoices.map((invoice) => (
              <tr key={invoice.id}>
                <td>{invoice.number ?? `draft #${invoice.id}`}</td>
                <td>{accountName(invoice.account_id)}</td>
                <td>
                  <StatusBadge status={invoice.status} />
                </td>
                <td>{invoice.due_date ?? '—'}</td>
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
      )}
    </section>
  )
}
