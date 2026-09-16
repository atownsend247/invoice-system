# Data model

**Status: implemented** (`src/invoice_system/models.py`,
`storage/schema.py`). Keep this table in sync with the actual schema — this
doc is read as ground truth. `storage/schema.py`'s `MIGRATIONS` is currently
a single flattened baseline entry (see `CLAUDE.md`'s migrations gotcha) —
schema changes from here on are new entries appended to that list, not
edits to it.

## Entities

| Entity | Key fields | Notes |
|---|---|---|
| `Account` | id, business_name, contact_name, email, phone, address, created_at | A business you provide a service to and bill. Not a login identity — see `CLAUDE.md`. |
| `Quote` | id, account_id, number, status, currency, issue_date, expiry_date, created_at | `status`: `draft \| sent \| accepted \| rejected \| expired \| converted`. `number` (`Q-0001`, ...) is assigned on `send`, not on creation. |
| `Invoice` | id, account_id, quote_id, number, status, currency, issue_date, due_date, created_at | `status`: `draft \| sent \| paid \| overdue \| void`. `quote_id` is set when created via conversion, `NULL` otherwise. `number` (`INV-0001`, ...) and `due_date` are assigned on `send`. `paid` is assigned by `InvoiceService.pay()`, only from `sent` — `overdue` is a defined enum value nothing ever actually sets (see "Not yet modelled"). |
| `LineItem` | id, description, quantity, unit_price, position | One shape, shared by quotes and invoices; associated via `quote_line_items`/`invoice_line_items` join tables (`quote_id`/`invoice_id` + the same columns). `total` (`quantity * unit_price`) is a derived property, never stored. |
| `BusinessProfile` | id, user_id, title, first_name, last_name, business_name, address_line1, address_line2, town_or_city, county, postcode, payment_terms_days, currency, utr, vat_number, created_at, updated_at | The logged-in user's *own* details, in three groups (see `CLAUDE.md`): user settings (`title` optional, `first_name`/`last_name` required), business settings (`business_name` required; `address_line1`/`address_line2`/`town_or_city`/`county`/`postcode` — a UK GOV.UK Design System-style address, each line independently optional), payment and tax settings (`payment_terms_days`, `currency` — the home dashboard's *reporting* currency, defaults `"GBP"`, independent of any quote/invoice's own `currency` — `utr`/`vat_number` optional). Not `Account` (the client being billed). One per `user_id` (`UNIQUE`), which is sessionkit's `User.id` — a plain column, not an enforced FK (see `CLAUDE.md`, "Login accounts" below). Every optional field: blank input is normalised to `NULL`, never stored as `""`. |
| counters (internal) | name, value | Backs `next_quote_number`/`next_invoice_number`; not a domain entity, not exposed via API/CLI. |

`MonthlyInvoiceTotals` (`month`, `paid_total`, `unpaid_total`) is **not** a
stored table — it's `InvoiceService.monthly_totals()`'s return shape,
computed on read from `Invoice` rows for the home dashboard's chart. See
the invariants below for exactly what it includes/excludes.

## Relationships

```
Account 1──* Quote
Account 1──* Invoice
Quote   1──* LineItem   (via quote_line_items)
Quote   0/1──0/1 Invoice  (conversion; quote.status becomes "converted")
Invoice 1──* LineItem   (via invoice_line_items)
```

## Invariants enforced in `core`, not in storage

- `LineItem`s are only addable while the owning `Quote`/`Invoice` is
  `draft`; `send()` freezes them (issue a new quote/invoice instead of
  editing history — see `CLAUDE.md` conventions).
- `Quote.number`/`Invoice.number` are assigned by the service on `send()`,
  not on creation — a draft can exist indefinitely without consuming a
  number.
- A `Quote` converts to an `Invoice` at most once, and only from `sent` or
  `accepted` — `QuoteService.convert_to_invoice` copies its line items and
  flips the quote to `converted`.
- Money fields (`unit_price`) are `Decimal` end-to-end; `SqliteRepository`
  stores them as `TEXT`, never `REAL`.
- `BusinessProfileService.get_profile` never 404s — it returns a virtual,
  unsaved default (`id=None`, blank name/address, `payment_terms_days=30`)
  when no row exists yet for that `user_id`. `save_profile` upserts: the
  first save for a `user_id` inserts, every save after that updates the
  same row (`created_at` untouched, `updated_at` bumped).
- `InvoiceService.pay()` only transitions `sent → paid` — rejects `draft`
  (never sent, nothing to have been paid for), `void` (cancelled), and an
  already-`paid` invoice. Stricter than `void()`, which also allows `draft`.
- `InvoiceService.monthly_totals(currency, months=12)` buckets every
  non-`draft`, non-`void` invoice **system-wide** (not filtered by
  account) by the calendar month of `issue_date` (when it was created, not
  `due_date`/`created_at`'s time-of-day), for the trailing `months` months
  ending with the current one. Only invoices whose `currency` matches the
  argument count — a different-currency invoice is excluded, never summed
  in regardless. `paid` invoices go in `paid_total`; everything else left
  (`sent`) goes in `unpaid_total`. Months with no matching invoices still
  appear, with both totals `Decimal("0")`.

## Login accounts (not this schema)

`sessionkit`'s `User` (email, name, password hash, TOTP state) and its
`sessions`/`recovery_codes` tables live in a **separate** SQLite file
(`auth.db` by default) with their own schema, owned and migrated by the
`sessionkit` package itself — not listed here, not touched by
`storage/schema.py`. See `CLAUDE.md` for why `User`, `Account`, and
`BusinessProfile` are three deliberately different things.

## Not yet modelled

Partial-payment tracking (a `Payment` model recording amounts/dates against
an invoice) and a real `sent → overdue` status transition are future work —
see `docs/roadmap.md`. Marking an invoice fully `paid` is implemented
(`InvoiceService.pay()`, a status flag, not a ledger); "overdue" is only
ever derived for display (`web/src/pages/HomePage.tsx`'s `isOverdue`), never
written to `Invoice.status`.
