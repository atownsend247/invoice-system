# Data model

**Status: implemented** (`src/invoice_system/models.py`,
`storage/schema.py`). Keep this table in sync with the actual schema — this
doc is read as ground truth.

## Entities

| Entity | Key fields | Notes |
|---|---|---|
| `Account` | id, business_name, contact_name, email, phone, address, created_at | A business you provide a service to and bill. Not a login identity — see `CLAUDE.md`. |
| `Quote` | id, account_id, number, status, currency, issue_date, expiry_date, created_at | `status`: `draft \| sent \| accepted \| rejected \| expired \| converted`. `number` (`Q-0001`, ...) is assigned on `send`, not on creation. |
| `Invoice` | id, account_id, quote_id, number, status, currency, issue_date, due_date, created_at | `status`: `draft \| sent \| paid \| overdue \| void`. `quote_id` is set when created via conversion, `NULL` otherwise. `number` (`INV-0001`, ...) and `due_date` are assigned on `send`. |
| `LineItem` | id, description, quantity, unit_price, position | One shape, shared by quotes and invoices; associated via `quote_line_items`/`invoice_line_items` join tables (`quote_id`/`invoice_id` + the same columns). `total` (`quantity * unit_price`) is a derived property, never stored. |
| `BusinessProfile` | id, user_id, title, first_name, last_name, business_name, business_address, payment_terms_days, utr, vat_number, created_at, updated_at | The logged-in user's *own* details — not `Account` (the client being billed). One per `user_id` (`UNIQUE`), which is sessionkit's `User.id` — a plain column, not an enforced FK (see `CLAUDE.md`, "Login accounts" below). `first_name`/`last_name`/`business_name` are required (validated non-blank in `BusinessProfileService`, never `NULL`). `title`/`business_address`/`utr`/`vat_number` are optional — blank input is normalised to `NULL`, never stored as `""`. |
| counters (internal) | name, value | Backs `next_quote_number`/`next_invoice_number`; not a domain entity, not exposed via API/CLI. |

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
- `business_address` was originally `NOT NULL DEFAULT ''` (migration 2);
  migration 3 relaxed it to nullable via a rebuild-and-swap, since SQLite
  can't `ALTER COLUMN` a constraint in place — see the migrations gotcha in
  `CLAUDE.md`. Any pre-migration-3 row's stored `''` became `NULL` in the
  copy, not a literal empty string surviving forward.

## Login accounts (not this schema)

`sessionkit`'s `User` (email, name, password hash, TOTP state) and its
`sessions`/`recovery_codes` tables live in a **separate** SQLite file
(`auth.db` by default) with their own schema, owned and migrated by the
`sessionkit` package itself — not listed here, not touched by
`storage/schema.py`. See `CLAUDE.md` for why `User`, `Account`, and
`BusinessProfile` are three deliberately different things.

## Not yet modelled

Payments/partial-payment tracking and an `overdue` status transition are
future work — see `docs/roadmap.md`. There is currently no way to mark an
`Invoice` `paid` other than direct storage access.
