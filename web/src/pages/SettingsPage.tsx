import { type FormEvent, useEffect, useState } from 'react'
import * as api from '../api'
import { errorMessage, useAsync } from '../hooks/useAsync'
import type { BusinessProfile } from '../types'

const TABS = ['User', 'Business', 'Payment and tax', 'Document'] as const
type Tab = (typeof TABS)[number]

// Element ids can technically contain spaces, but it's fragile (breaks
// plain CSS/querySelector id references without escaping) - a slug keeps
// id/aria-controls values simple while the tab's own visible label (and
// its accessible name, used by e2e's getByRole('tab', { name: ... })
// lookups) stays exactly as written above.
function tabSlug(tab: Tab): string {
  return tab.toLowerCase().replace(/\s+/g, '-')
}

export function SettingsPage() {
  const { data: profile, loading, error } = useAsync(() => api.getBusinessProfile(), [])
  const [activeTab, setActiveTab] = useState<Tab>('User')

  return (
    <section>
      <h1>Settings</h1>
      <p className="meta">Your details - shown on the quotes and invoices you send.</p>

      {loading && <p>Loading…</p>}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {profile && (
        <div role="tablist" aria-label="Settings sections" className="settings-tabs">
          {TABS.map((tab) => (
            <button
              key={tab}
              type="button"
              role="tab"
              id={`settings-tab-${tabSlug(tab)}`}
              aria-selected={activeTab === tab}
              aria-controls={`settings-panel-${tabSlug(tab)}`}
              className={activeTab === tab ? 'active' : undefined}
              onClick={() => setActiveTab(tab)}
            >
              {tab}
            </button>
          ))}
        </div>
      )}
      {profile && <BusinessProfileForm profile={profile} activeTab={activeTab} />}
    </section>
  )
}

function BusinessProfileForm({ profile, activeTab }: { profile: BusinessProfile; activeTab: Tab }) {
  const [title, setTitle] = useState(profile.title ?? '')
  const [firstName, setFirstName] = useState(profile.first_name)
  const [lastName, setLastName] = useState(profile.last_name)
  const [businessName, setBusinessName] = useState(profile.business_name)
  const [addressLine1, setAddressLine1] = useState(profile.address_line1 ?? '')
  const [addressLine2, setAddressLine2] = useState(profile.address_line2 ?? '')
  const [townOrCity, setTownOrCity] = useState(profile.town_or_city ?? '')
  const [county, setCounty] = useState(profile.county ?? '')
  const [postcode, setPostcode] = useState(profile.postcode ?? '')
  const [paymentTermsDays, setPaymentTermsDays] = useState(String(profile.payment_terms_days))
  const [quoteValidityDays, setQuoteValidityDays] = useState(String(profile.quote_validity_days))
  const [currency, setCurrency] = useState(profile.currency)
  const [utr, setUtr] = useState(profile.utr ?? '')
  const [vatNumber, setVatNumber] = useState(profile.vat_number ?? '')
  const [bankAccountName, setBankAccountName] = useState(profile.bank_account_name ?? '')
  const [bankSortCode, setBankSortCode] = useState(profile.bank_sort_code ?? '')
  const [bankAccountNumber, setBankAccountNumber] = useState(profile.bank_account_number ?? '')
  const [quoteHeader, setQuoteHeader] = useState(profile.quote_document_header ?? '')
  const [quoteFooter, setQuoteFooter] = useState(profile.quote_document_footer ?? '')
  const [invoiceHeader, setInvoiceHeader] = useState(profile.invoice_document_header ?? '')
  const [invoiceFooter, setInvoiceFooter] = useState(profile.invoice_document_footer ?? '')
  const [expenseHeader, setExpenseHeader] = useState(profile.expense_document_header ?? '')
  const [expenseFooter, setExpenseFooter] = useState(profile.expense_document_footer ?? '')
  const [quoteNumberPrefix, setQuoteNumberPrefix] = useState(profile.quote_number_prefix)
  const [quoteNumberDigits, setQuoteNumberDigits] = useState(String(profile.quote_number_digits))
  const [invoiceNumberPrefix, setInvoiceNumberPrefix] = useState(profile.invoice_number_prefix)
  const [invoiceNumberDigits, setInvoiceNumberDigits] = useState(String(profile.invoice_number_digits))
  const [expenseNumberPrefix, setExpenseNumberPrefix] = useState(profile.expense_number_prefix)
  const [expenseNumberDigits, setExpenseNumberDigits] = useState(String(profile.expense_number_digits))
  const [accentColor, setAccentColor] = useState(profile.accent_color ?? '')
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  // One shared <form>/Save button covers every tab (see the class comment
  // below), so a "Saved."/error message from one tab would otherwise
  // still be showing after switching to a completely different tab -
  // confusing, since it looks like it's about whatever's now on screen.
  // Clear it on every tab change instead of leaving it to linger.
  useEffect(() => {
    setError(null)
    setSaved(false)
  }, [activeTab])

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSaved(false)
    setSubmitting(true)
    try {
      const updated = await api.saveBusinessProfile({
        title: title || undefined,
        first_name: firstName,
        last_name: lastName,
        business_name: businessName,
        address_line1: addressLine1 || undefined,
        address_line2: addressLine2 || undefined,
        town_or_city: townOrCity || undefined,
        county: county || undefined,
        postcode: postcode || undefined,
        payment_terms_days: Number(paymentTermsDays),
        quote_validity_days: Number(quoteValidityDays),
        currency,
        utr: utr || undefined,
        vat_number: vatNumber || undefined,
        bank_account_name: bankAccountName || undefined,
        bank_sort_code: bankSortCode || undefined,
        bank_account_number: bankAccountNumber || undefined,
        quote_document_header: quoteHeader || undefined,
        quote_document_footer: quoteFooter || undefined,
        invoice_document_header: invoiceHeader || undefined,
        invoice_document_footer: invoiceFooter || undefined,
        expense_document_header: expenseHeader || undefined,
        expense_document_footer: expenseFooter || undefined,
        quote_number_prefix: quoteNumberPrefix,
        quote_number_digits: Number(quoteNumberDigits),
        invoice_number_prefix: invoiceNumberPrefix,
        invoice_number_digits: Number(invoiceNumberDigits),
        expense_number_prefix: expenseNumberPrefix,
        expense_number_digits: Number(expenseNumberDigits),
        accent_color: accentColor || undefined,
      })
      // Reflect what the server actually stored (e.g. a blank UTR is
      // normalised to null) rather than trusting the pre-submit input back.
      setTitle(updated.title ?? '')
      setFirstName(updated.first_name)
      setLastName(updated.last_name)
      setBusinessName(updated.business_name)
      setAddressLine1(updated.address_line1 ?? '')
      setAddressLine2(updated.address_line2 ?? '')
      setTownOrCity(updated.town_or_city ?? '')
      setCounty(updated.county ?? '')
      setPostcode(updated.postcode ?? '')
      setPaymentTermsDays(String(updated.payment_terms_days))
      setQuoteValidityDays(String(updated.quote_validity_days))
      setCurrency(updated.currency)
      setUtr(updated.utr ?? '')
      setVatNumber(updated.vat_number ?? '')
      setBankAccountName(updated.bank_account_name ?? '')
      setBankSortCode(updated.bank_sort_code ?? '')
      setBankAccountNumber(updated.bank_account_number ?? '')
      setQuoteHeader(updated.quote_document_header ?? '')
      setQuoteFooter(updated.quote_document_footer ?? '')
      setInvoiceHeader(updated.invoice_document_header ?? '')
      setInvoiceFooter(updated.invoice_document_footer ?? '')
      setExpenseHeader(updated.expense_document_header ?? '')
      setExpenseFooter(updated.expense_document_footer ?? '')
      setQuoteNumberPrefix(updated.quote_number_prefix)
      setQuoteNumberDigits(String(updated.quote_number_digits))
      setInvoiceNumberPrefix(updated.invoice_number_prefix)
      setInvoiceNumberDigits(String(updated.invoice_number_digits))
      setExpenseNumberPrefix(updated.expense_number_prefix)
      setExpenseNumberDigits(String(updated.expense_number_digits))
      setAccentColor(updated.accent_color ?? '')
      setSaved(true)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form className="settings-form" onSubmit={handleSubmit}>
      <div
        role="tabpanel"
        id={`settings-panel-${tabSlug('User')}`}
        aria-labelledby={`settings-tab-${tabSlug('User')}`}
        hidden={activeTab !== 'User'}
      >
        <fieldset className="form-section">
          <legend>User settings</legend>
          <div className="form-section-fields">
            <label>
              Title (optional)
              <input value={title} onChange={(event) => setTitle(event.target.value)} />
            </label>
            <label>
              First name (optional)
              <input value={firstName} onChange={(event) => setFirstName(event.target.value)} />
            </label>
            <label>
              Last name (optional)
              <input value={lastName} onChange={(event) => setLastName(event.target.value)} />
            </label>
          </div>
        </fieldset>
      </div>

      <div
        role="tabpanel"
        id={`settings-panel-${tabSlug('Business')}`}
        aria-labelledby={`settings-tab-${tabSlug('Business')}`}
        hidden={activeTab !== 'Business'}
      >
        <fieldset className="form-section">
          <legend>Business settings</legend>
          <div className="form-section-fields">
            <label>
              Business name (optional)
              <input value={businessName} onChange={(event) => setBusinessName(event.target.value)} />
            </label>
            <label>
              Address line 1 (optional)
              <input value={addressLine1} onChange={(event) => setAddressLine1(event.target.value)} />
            </label>
            <label>
              Address line 2 (optional)
              <input value={addressLine2} onChange={(event) => setAddressLine2(event.target.value)} />
            </label>
            <label>
              Town or city (optional)
              <input value={townOrCity} onChange={(event) => setTownOrCity(event.target.value)} />
            </label>
            <label>
              County (optional)
              <input value={county} onChange={(event) => setCounty(event.target.value)} />
            </label>
            <label>
              Postcode (optional)
              <input value={postcode} onChange={(event) => setPostcode(event.target.value)} />
            </label>
          </div>
        </fieldset>
      </div>

      <div
        role="tabpanel"
        id={`settings-panel-${tabSlug('Payment and tax')}`}
        aria-labelledby={`settings-tab-${tabSlug('Payment and tax')}`}
        hidden={activeTab !== 'Payment and tax'}
      >
        <fieldset className="form-section">
          <legend>Payment and tax settings</legend>
          <div className="form-section-fields">
            <label>
              Payment terms (days)
              <input
                type="number"
                min={1}
                step={1}
                value={paymentTermsDays}
                onChange={(event) => setPaymentTermsDays(event.target.value)}
              />
            </label>
            <label>
              Quote validity (days)
              <input
                type="number"
                min={1}
                step={1}
                value={quoteValidityDays}
                onChange={(event) => setQuoteValidityDays(event.target.value)}
              />
            </label>
            <label>
              Currency
              <input
                value={currency}
                onChange={(event) => setCurrency(event.target.value.toUpperCase())}
                maxLength={3}
              />
            </label>
            <label>
              UTR (optional)
              <input value={utr} onChange={(event) => setUtr(event.target.value)} />
            </label>
            <label>
              VAT number (optional)
              <input value={vatNumber} onChange={(event) => setVatNumber(event.target.value)} />
            </label>
            <label>
              Bank account name (optional)
              <input value={bankAccountName} onChange={(event) => setBankAccountName(event.target.value)} />
            </label>
            <label>
              Bank sort code (optional)
              <input value={bankSortCode} onChange={(event) => setBankSortCode(event.target.value)} />
            </label>
            <label>
              Bank account number (optional)
              <input
                value={bankAccountNumber}
                onChange={(event) => setBankAccountNumber(event.target.value)}
              />
            </label>
          </div>
        </fieldset>
      </div>

      <div
        role="tabpanel"
        id={`settings-panel-${tabSlug('Document')}`}
        aria-labelledby={`settings-tab-${tabSlug('Document')}`}
        hidden={activeTab !== 'Document'}
      >
        <fieldset className="form-section">
          <legend>Document settings</legend>

          <div className="form-section-fields">
            <label>
              Accent colour (optional)
              <span className="accent-color-field">
                <input
                  type="color"
                  aria-label="Colour picker"
                  value={/^#[0-9a-f]{6}$/i.test(accentColor) ? accentColor : '#1f2430'}
                  onChange={(event) => setAccentColor(event.target.value)}
                />
                <input
                  type="text"
                  aria-label="Accent colour"
                  value={accentColor}
                  onChange={(event) => setAccentColor(event.target.value)}
                  placeholder="#2563EB"
                />
              </span>
            </label>
          </div>

          <fieldset className="form-subsection">
            <legend>Quotes</legend>
            <div className="form-section-fields">
              <label>
                Number prefix
                <input
                  value={quoteNumberPrefix}
                  onChange={(event) => setQuoteNumberPrefix(event.target.value)}
                />
              </label>
              <label>
                Number digits
                <input
                  type="number"
                  min={1}
                  step={1}
                  value={quoteNumberDigits}
                  onChange={(event) => setQuoteNumberDigits(event.target.value)}
                />
              </label>
              <label className="form-field-wide">
                Quote header (optional)
                <textarea
                  rows={3}
                  value={quoteHeader}
                  onChange={(event) => setQuoteHeader(event.target.value)}
                  placeholder="Shown above the title on every quote PDF you generate."
                />
              </label>
              <label className="form-field-wide">
                Quote footer (optional)
                <textarea
                  rows={3}
                  value={quoteFooter}
                  onChange={(event) => setQuoteFooter(event.target.value)}
                  placeholder="Shown below the totals table on every quote PDF you generate."
                />
              </label>
            </div>
            <NextNumberAction label="quote" onSet={api.setNextQuoteNumber} />
          </fieldset>

          <fieldset className="form-subsection">
            <legend>Invoices</legend>
            <div className="form-section-fields">
              <label>
                Number prefix
                <input
                  value={invoiceNumberPrefix}
                  onChange={(event) => setInvoiceNumberPrefix(event.target.value)}
                />
              </label>
              <label>
                Number digits
                <input
                  type="number"
                  min={1}
                  step={1}
                  value={invoiceNumberDigits}
                  onChange={(event) => setInvoiceNumberDigits(event.target.value)}
                />
              </label>
              <label className="form-field-wide">
                Invoice header (optional)
                <textarea
                  rows={3}
                  value={invoiceHeader}
                  onChange={(event) => setInvoiceHeader(event.target.value)}
                  placeholder="Shown above the title on every invoice PDF you generate."
                />
              </label>
              <label className="form-field-wide">
                Invoice footer (optional)
                <textarea
                  rows={3}
                  value={invoiceFooter}
                  onChange={(event) => setInvoiceFooter(event.target.value)}
                  placeholder="Shown below the totals table on every invoice PDF you generate."
                />
              </label>
            </div>
            <NextNumberAction label="invoice" onSet={api.setNextInvoiceNumber} />
          </fieldset>

          <fieldset className="form-subsection">
            <legend>Expenses</legend>
            <div className="form-section-fields">
              <label>
                Number prefix
                <input
                  value={expenseNumberPrefix}
                  onChange={(event) => setExpenseNumberPrefix(event.target.value)}
                />
              </label>
              <label>
                Number digits
                <input
                  type="number"
                  min={1}
                  step={1}
                  value={expenseNumberDigits}
                  onChange={(event) => setExpenseNumberDigits(event.target.value)}
                />
              </label>
              <label className="form-field-wide">
                Expense header (optional)
                <textarea
                  rows={3}
                  value={expenseHeader}
                  onChange={(event) => setExpenseHeader(event.target.value)}
                  placeholder="Shown above the title on every expense PDF you generate."
                />
              </label>
              <label className="form-field-wide">
                Expense footer (optional)
                <textarea
                  rows={3}
                  value={expenseFooter}
                  onChange={(event) => setExpenseFooter(event.target.value)}
                  placeholder="Shown below the totals table on every expense PDF you generate."
                />
              </label>
            </div>
            <NextNumberAction label="expense" onSet={api.setNextExpenseNumber} />
          </fieldset>
        </fieldset>
      </div>

      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {saved && !error && <p className="form-success">Saved.</p>}
      <button type="submit" disabled={submitting}>
        {submitting ? 'Saving…' : 'Save settings'}
      </button>
    </form>
  )
}

/** An immediate, one-time action - not a persisted field, so it's a plain
 * `<div>` with an onClick handler rather than a nested `<form>` (this
 * fieldset already sits inside BusinessProfileForm's own `<form>`, and a
 * `<form>` can't nest inside another). Jumps the counter so the *next*
 * document of this type gets exactly the number entered, regardless of
 * how many already exist (see CLAUDE.md). */
function NextNumberAction({ label, onSet }: { label: string; onSet: (nextNumber: number) => Promise<void> }) {
  const [value, setValue] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  async function handleSet() {
    setError(null)
    setSuccess(false)
    setSubmitting(true)
    try {
      await onSet(Number(value))
      setSuccess(true)
      setValue('')
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="next-number-action">
      <label>
        {`Next ${label} number`}
        <input
          type="number"
          min={1}
          step={1}
          value={value}
          onChange={(event) => {
            setValue(event.target.value)
            setSuccess(false)
          }}
          placeholder="e.g. 67"
        />
      </label>
      <button type="button" disabled={submitting || !value} onClick={handleSet}>
        {submitting ? 'Setting…' : 'Set'}
      </button>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {success && <p className="form-success">Set.</p>}
    </div>
  )
}

