import type { AccountStatus, InvoiceStatus, QuoteStatus } from '../types'

export function StatusBadge({ status }: { status: QuoteStatus | InvoiceStatus | AccountStatus }) {
  return <span className={`status-badge status-${status}`}>{status}</span>
}
