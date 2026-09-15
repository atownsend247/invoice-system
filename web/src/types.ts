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

export interface Account {
  id: number
  business_name: string
  contact_name: string | null
  email: string
  phone: string | null
  address: string
  created_at: string
}

export interface LineItem {
  id: number
  description: string
  quantity: string
  unit_price: string
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
  total: string
}
