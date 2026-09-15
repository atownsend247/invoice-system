import type { InvoiceStatus, QuoteStatus } from '../types'

export function StatusBadge({ status }: { status: QuoteStatus | InvoiceStatus }) {
  return <span className={`status-badge status-${status}`}>{status}</span>
}
