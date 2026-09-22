// id is a UUID4 string (sessionkit's own, since v0.2.0 - see CLAUDE.md),
// not a sequential integer - never parsed or compared as a number.
export interface User {
  id: string
  email: string
  name: string
  created_at: string
  totp_enabled: boolean
}

export interface LoginResult {
  token: string
  expires_at: string
  user: User
}

// Address fields follow the same UK GOV.UK Design System pattern as
// BusinessProfile's - see CLAUDE.md. address_line1 is required (an Account
// is a real client being billed); the rest are each independently
// optional. id (like every id in this app) is a UUID4 string, not a
// sequential integer - see CLAUDE.md.
// One server-paginated page of a list endpoint (accounts/quotes/invoices) -
// `total` is the count matching the request's filters across every page,
// not just `items`, letting the caller compute how many pages exist
// without a second request.
export interface PagedResult<T> {
  items: T[]
  total: number
}

export interface Account {
  id: string
  business_name: string
  contact_name: string | null
  email: string
  phone: string | null
  address_line1: string
  address_line2: string | null
  town_or_city: string | null
  county: string | null
  postcode: string | null
  created_at: string
}

// A domain name owned by an Account - which domain, when it expires, who
// it's registered with (see CLAUDE.md). domain_name/expiry_date/registrar
// are all required; auto_renew is purely informational.
export interface Domain {
  id: string
  account_id: string
  domain_name: string
  expiry_date: string
  registrar: string
  auto_renew: boolean
  created_at: string
  updated_at: string
}

// A business's managed list of domain registrars, used to populate the
// Domain form's registrar <select> - see CLAUDE.md. Organisation-wide,
// not account-scoped like Domain. Domain.registrar stores the chosen
// name as a plain string, not a reference to this row's id.
export interface Registrar {
  id: string
  name: string
  notes: string | null
  // How many domains (and, in turn, distinct accounts) currently name
  // this registrar - see RegistrarUsage in models.py. Computed, not
  // stored - always present.
  domain_count: number
  account_count: number
  created_at: string
  updated_at: string
}

// tax_rate is a fraction ("0.20" for 20% VAT, "0" for none) applied to
// this line only - see CLAUDE.md. total is *gross* (net_total +
// tax_amount) - what this line actually adds to what's owed.
export interface LineItem {
  id: string
  description: string
  quantity: string
  unit_price: string
  tax_rate: string
  net_total: string
  tax_amount: string
  total: string
}

export type QuoteStatus = 'draft' | 'sent' | 'accepted' | 'rejected' | 'expired' | 'converted'

// One entry in a Quote's or Invoice's audit trail - creation and status
// changes only (not every field edit). from_status is null for a 'created'
// event. The API returns these newest-first (see CLAUDE.md), so no
// client-side sort is needed before rendering.
export interface ActivityEvent {
  id: string
  event_type: 'created' | 'status_changed'
  from_status: string | null
  to_status: string
  occurred_at: string
}

export interface Quote {
  id: string
  account_id: string
  number: string | null
  status: QuoteStatus
  currency: string
  issue_date: string
  expiry_date: string | null
  created_at: string
  line_items: LineItem[]
  events: ActivityEvent[]
  subtotal: string
  tax_total: string
  total: string
}

export type InvoiceStatus = 'draft' | 'sent' | 'paid' | 'overdue' | 'void'

export interface Invoice {
  id: string
  account_id: string
  quote_id: string | null
  number: string | null
  status: InvoiceStatus
  currency: string
  issue_date: string
  due_date: string | null
  created_at: string
  line_items: LineItem[]
  events: ActivityEvent[]
  subtotal: string
  tax_total: string
  total: string
}

// The logged-in user's own business details - not an Account (that's the
// client being billed). One per user; there's no id, since GET/PUT always
// mean "my own profile" via the auth token, not an id in the URL.
export interface BusinessProfile {
  title: string | null
  first_name: string
  last_name: string
  business_name: string
  address_line1: string | null
  address_line2: string | null
  town_or_city: string | null
  county: string | null
  postcode: string | null
  payment_terms_days: number
  quote_validity_days: number
  currency: string
  utr: string | null
  vat_number: string | null
  bank_account_name: string | null
  bank_sort_code: string | null
  bank_account_number: string | null
  // Free text (multi-line) shown on every PDF of the matching type this
  // user generates - header before the title, footer after the totals
  // table. Three independent pairs, one per document type, so each can
  // say something different.
  quote_document_header: string | null
  quote_document_footer: string | null
  invoice_document_header: string | null
  invoice_document_footer: string | null
  expense_document_header: string | null
  expense_document_footer: string | null
  // Configurable per-document-type number prefix/zero-padding (e.g.
  // "Q-" + 4 digits -> Q-0001) - only affects numbers assigned from now
  // on, never rewrites an already-issued one.
  quote_number_prefix: string
  quote_number_digits: number
  invoice_number_prefix: string
  invoice_number_digits: number
  expense_number_prefix: string
  expense_number_digits: number
  // A single #RRGGBB hex colour used as the brand colour across every
  // quote/invoice/expense PDF this user generates - one shared value, not
  // a per-document-type triple like the header/footer pairs above.
  accent_color: string | null
  updated_at: string
}

// One entry per month for the home dashboard's monthly totals chart - see
// InvoiceService.monthly_totals. amounts are decimal strings, like every
// other money value on the wire (see CLAUDE.md conventions).
export interface MonthlyInvoiceTotal {
  month: string // "YYYY-MM"
  paid_total: string
  unpaid_total: string
}

export interface MonthlyTotalsReport {
  currency: string
  months: MonthlyInvoiceTotal[]
}

// One entry per month for the home dashboard's monthly totals chart - see
// ExpenseService.monthly_totals. No paid/unpaid split, unlike invoices -
// an Expense has no status (see CLAUDE.md).
export interface MonthlyExpenseTotal {
  month: string // "YYYY-MM"
  total: string
}

export interface MonthlyExpenseTotalsReport {
  currency: string
  months: MonthlyExpenseTotal[]
}

// A supplementary file (e.g. a scanned receipt) uploaded against an
// Expense - always a PDF (validated server-side in
// ExpenseService.add_attachment). `size` is in bytes.
export interface ExpenseAttachment {
  id: string
  filename: string
  content_type: string
  size: number
  created_at: string
}

// A cost incurred against an Account - e.g. a domain renewal paid on a
// client's behalf. Unlike Quote/Invoice there's no status/lifecycle field:
// it's a record of money already spent, not a document with a draft/sent
// workflow, so `number` (EXP-0001, same per-organisation counter pattern
// as Quote.number/Invoice.number) is always set, never null - see
// CLAUDE.md and models.Expense. `attachments` are addable at any time too,
// same no-lifecycle reasoning as `line_items`. `issue_date` (when this was
// recorded) and `expense_date` (when the money was actually spent) answer
// different questions - see CLAUDE.md - `expense_date` is the one field
// here that's editable after creation.
export interface Expense {
  id: string
  account_id: string
  number: string
  currency: string
  issue_date: string
  expense_date: string
  created_at: string
  line_items: LineItem[]
  attachments: ExpenseAttachment[]
  subtotal: string
  tax_total: string
  total: string
}

// All-time, organisation-scoped counters for the home dashboard's stats
// section - see StatsService.get_stats. A small, flat shape that grows one
// field at a time as new stats are actually asked for. quotes_sent_count/
// quotes_converted_count are raw counts, not a precomputed rate - dividing
// them (and handling "no quotes sent yet") is done client-side, same as
// isOverdue/isOutstanding below. total_paid follows the same
// currency-filtering convention as MonthlyTotalsReport: only paid invoices
// in `currency` count.
export interface Stats {
  account_count: number
  quote_count: number
  invoice_count: number
  quotes_sent_count: number
  quotes_converted_count: number
  total_paid: string
  currency: string
}
