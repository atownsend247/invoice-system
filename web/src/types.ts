export interface User {
  id: number
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
// optional.
export interface Account {
  id: number
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

// tax_rate is a fraction ("0.20" for 20% VAT, "0" for none) applied to
// this line only - see CLAUDE.md. total is *gross* (net_total +
// tax_amount) - what this line actually adds to what's owed.
export interface LineItem {
  id: number
  description: string
  quantity: string
  unit_price: string
  tax_rate: string
  net_total: string
  tax_amount: string
  total: string
}

export type QuoteStatus = 'draft' | 'sent' | 'accepted' | 'rejected' | 'expired' | 'converted'

export interface Quote {
  id: number
  account_id: number
  number: string | null
  status: QuoteStatus
  currency: string
  issue_date: string
  expiry_date: string | null
  created_at: string
  line_items: LineItem[]
  subtotal: string
  tax_total: string
  total: string
}

export type InvoiceStatus = 'draft' | 'sent' | 'paid' | 'overdue' | 'void'

export interface Invoice {
  id: number
  account_id: number
  quote_id: number | null
  number: string | null
  status: InvoiceStatus
  currency: string
  issue_date: string
  due_date: string | null
  created_at: string
  line_items: LineItem[]
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
  currency: string
  utr: string | null
  vat_number: string | null
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

// All-time, system-wide counters for the home dashboard's stats section -
// see StatsService.get_stats. A small, flat shape that grows one field at
// a time as new stats are actually asked for.
export interface Stats {
  account_count: number
}
