# Data model

**Status: implemented** (`src/invoice_system/models.py`,
`storage/schema.py`). Keep this table in sync with the actual schema — this
doc is read as ground truth. `storage/schema.py`'s `MIGRATIONS` has eight
entries: the flattened baseline (2026-09-16), migration 2 (added `tax_rate`
to both line-item tables), migration 3 (added `Organisation` — the tenant
boundary — plus nullable `organisation_id` columns on `accounts`/`quotes`/
`invoices`), migration 4 (rescoped `Quote.number`/`Invoice.number`
uniqueness from a single global column constraint to a composite
`(organisation_id, number)` index, since numbering is now per-organisation),
migration 5 (split `accounts.address` into `address_line1`/
`address_line2`/`town_or_city`/`county`/`postcode`, same UK GOV.UK Design
System structure as `BusinessProfile`'s), migration 6 (added
`bank_account_name`/`bank_sort_code`/`bank_account_number`/
`document_header`/`document_footer` to `business_profiles`), migration 7
(every primary key, and every column referencing one, switched from an
autoincrementing `INTEGER` to an opaque UUID4 `TEXT` string — see "Opaque
ids" below and `CLAUDE.md`'s migrations gotcha), and migration 8 (added
`expenses`/`expense_line_items` — two brand new tables, a plain `CREATE
TABLE` each, no rebuild needed). Schema changes from here on are new
entries appended to that list, not edits to any of these eight.

## Entities

| Entity | Key fields | Notes |
|---|---|---|
| `Organisation` | id, name, created_at | The tenant boundary — every `Account`/`Quote`/`Invoice` belongs to exactly one. Auto-created the first time a login user needs one (`OrganisationService.get_or_create_for_user`), via an `organisation_members` join table (`organisation_id`, `user_id`, `created_at`) with `UNIQUE` on `user_id` enforcing "one organisation per user" *for now* — see "Multi-tenancy" below. |
| `Account` | id, organisation_id, business_name, contact_name, email, phone, address_line1, address_line2, town_or_city, county, postcode, created_at | A business you provide a service to and bill, scoped to one `Organisation`. Editable after creation (`AccountService.update_account`, full replace). Not a login identity — see `CLAUDE.md`. Address fields follow the same UK GOV.UK Design System pattern as `BusinessProfile`'s below, except `address_line1` is required here (an `Account` is a real client being billed, not the user's own optionally-published details) — the rest are each independently optional. |
| `Quote` | id, organisation_id, account_id, number, status, currency, issue_date, expiry_date, created_at | `status`: `draft \| sent \| accepted \| rejected \| expired \| converted`. `number` (`Q-0001`, ...) is assigned on `send`, not on creation, and is unique per-`organisation_id`, not globally (see migration 4 above) — two organisations' first quotes can both be `Q-0001`. |
| `Invoice` | id, organisation_id, account_id, quote_id, number, status, currency, issue_date, due_date, created_at | `status`: `draft \| sent \| paid \| overdue \| void`. `quote_id` is set when created via conversion, `NULL` otherwise. `number` (`INV-0001`, ...) and `due_date` are assigned on `send`, and — same as `Quote.number` — unique per-`organisation_id`, not globally. `paid` is assigned by `InvoiceService.pay()`, only from `sent` — `overdue` is a defined enum value nothing ever actually sets (see "Not yet modelled"). |
| `LineItem` | id, description, quantity, unit_price, tax_rate, position | One shape, shared by quotes, invoices, and expenses; associated via `quote_line_items`/`invoice_line_items`/`expense_line_items` join tables (`quote_id`/`invoice_id`/`expense_id` + the same columns). `tax_rate` is a fraction (`0.20` = 20% UK VAT; `0` = none), independently set per line. `net_total`/`tax_amount`/`total` (`net_total + tax_amount`, gross) are derived properties, never stored — `tax_amount` is rounded to the minor currency unit, `net_total` is not (see `CLAUDE.md`). |
| `Expense` | id, organisation_id, account_id, number, currency, issue_date, created_at | A cost incurred against an `Account` (e.g. a domain renewal paid on the client's behalf) — see `CLAUDE.md`. Unlike `Quote`/`Invoice`, no `status` column: there's no draft/sent lifecycle, so `number` (`EXP-0001`, ..., same per-`organisation_id` composite-unique-index pattern as `Quote.number`/`Invoice.number` — see migration 8) is `NOT NULL` and assigned by `ExpenseService.create_expense` immediately, not deferred to a later `send()`. |
| `BusinessProfile` | id, user_id, title, first_name, last_name, business_name, address_line1, address_line2, town_or_city, county, postcode, payment_terms_days, currency, utr, vat_number, bank_account_name, bank_sort_code, bank_account_number, document_header, document_footer, created_at, updated_at | The logged-in user's *own* details, in four groups (see `CLAUDE.md`): user settings (`title` optional, `first_name`/`last_name` required), business settings (`business_name` required; `address_line1`/`address_line2`/`town_or_city`/`county`/`postcode` — a UK GOV.UK Design System-style address, each line independently optional), payment and tax settings (`payment_terms_days`, `currency` — the home dashboard's *reporting* currency, defaults `"GBP"`, independent of any quote/invoice's own `currency` — `utr`/`vat_number`/`bank_account_name`/`bank_sort_code`/`bank_account_number` all optional and purely informational, not currently rendered on a PDF), document settings (`document_header`/`document_footer`, free text, each independently optional — inserted into every quote/invoice/expense PDF this user generates, see `pdf.py`'s `document_header_lines()`/`document_footer_lines()` and the invariants below). Not `Account` (the client being billed). One per `user_id` (`UNIQUE`), which is sessionkit's `User.id` — a plain column, not an enforced FK (see `CLAUDE.md`, "Login accounts" below). Deliberately still per-*user*, not per-`Organisation` — see "Multi-tenancy" below. Every optional field: blank input is normalised to `NULL`, never stored as `""`. |
| counters (internal) | name, value | Backs `next_quote_number`/`next_invoice_number`/`next_expense_number`; not a domain entity, not exposed via API/CLI. `name` is `"<organisation_id>:quote"`/`"<organisation_id>:invoice"`/`"<organisation_id>:expense"`, not a bare `"quote"`/`"invoice"`/`"expense"` — each organisation gets its own independent sequence starting from one. |

`MonthlyInvoiceTotals` (`month`, `paid_total`, `unpaid_total`) and `Stats`
(`account_count`, `quote_count`, `invoice_count`, `quotes_sent_count`,
`quotes_converted_count`, `total_paid`) are **not** stored tables — they're
`InvoiceService.monthly_totals()`/`StatsService.get_stats()`'s return
shapes, computed on read for the home dashboard. See the invariants below
for exactly what the former includes/excludes.

## Opaque ids

Every `id` in this schema (and every column that references one -
`organisation_id`, `account_id`, `quote_id`, `invoice_id`, `user_id`) is a
random UUID4 string, not an autoincrementing integer - `Organisation`,
`Account`, `Quote`, `Invoice`, `LineItem`, `BusinessProfile` alike (migration
7). `user_id` is sessionkit's own `User.id`, itself a UUID4 string since
sessionkit v0.2.0, for the same reason.

Why: a sequential id leaks information it has no business leaking - an id
appearing in a URL or API response otherwise tells a caller roughly how many
rows exist and in what order they were created, which nothing should be
able to infer about another organisation's activity. This is the same
reasoning that already justified making `Quote.number`/`Invoice.number`
per-organisation (migration 4) rather than a single global counter; this
migration closes the same leak for every id, not just those two.

Ids are generated in the application layer, not by the database:
`AccountService`/`QuoteService`/`InvoiceService`/`OrganisationService`/
`BusinessProfileService` each take an injectable `new_id: IdGenerator`
constructor parameter (`src/invoice_system/ids.py`, `default_new_id` →
`uuid.uuid4()`), mirroring the existing `clock: Clock` pattern - a service
generates the id *before* constructing the dataclass passed to
`Repository.create_*`, which now only persists whatever id it's given
(never `cursor.lastrowid`) - see CLAUDE.md's architecture rules on why
storage doesn't generate ids itself.

**`list_accounts`/`list_quotes`/`list_invoices` order by SQLite's implicit
`rowid`, not `id`.** A UUID has no relationship to insertion order (unlike
the old autoincrementing integer, which doubled as one) - every SQLite
table not declared `WITHOUT ROWID` keeps a hidden, monotonically-increasing
`rowid` regardless of its declared `PRIMARY KEY` type. It's never selected
or exposed to any caller, so ordering by it doesn't reintroduce the
information leak switching to UUIDs was meant to close - see
`sqlite_repository.py`'s comment on `list_accounts` for the full reasoning
(including why `ORDER BY created_at` alone isn't enough: two rows can share
a timestamp, notably under a frozen/fake clock in tests).

Migration 7 is a one-time authorized full reset, not a data-preserving
migration like every other one in this list: every table is dropped and
recreated, deliberately, rather than remapping each existing integer id to
a UUID and rewriting every foreign key that pointed at it - added
complexity for no benefit on a pre-1.0 app with no production database to
preserve. `invoice-system-cli init-db` reseeds demo data with real UUIDs
afterward. This is *not* a pattern to reuse for a future migration once
real user data exists - that's exactly what forward-only, data-preserving
migrations (every other entry in this list) exist to avoid.

## Relationships

```
Organisation 1──* Account
Organisation 1──* Quote
Organisation 1──* Invoice
Organisation 1──* Expense
Organisation 1──1 User (sessionkit, via organisation_members - see "Multi-tenancy" below)
Account 1──* Quote
Account 1──* Invoice
Account 1──* Expense
Quote   1──* LineItem   (via quote_line_items)
Quote   0/1──0/1 Invoice  (conversion; quote.status becomes "converted")
Invoice 1──* LineItem   (via invoice_line_items)
Expense 1──* LineItem   (via expense_line_items)
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
- Money fields (`unit_price`, `tax_rate`) are `Decimal` end-to-end;
  `SqliteRepository` stores them as `TEXT`, never `REAL`.
- `QuoteService.add_line_item`/`InvoiceService.add_line_item` reject a
  `tax_rate` outside `[0, 1]`. `QuoteService.convert_to_invoice` copies
  `tax_rate` across to the new `LineItem` along with the other fields — a
  migration or refactor that adds another `LineItem` field must update that
  copy too, or it silently reverts to the field's default on every
  converted invoice.
- `BusinessProfileService.get_profile` never 404s — it returns a virtual,
  unsaved default (`id=None`, blank name/address, `payment_terms_days=30`)
  when no row exists yet for that `user_id`. `save_profile` upserts: the
  first save for a `user_id` inserts, every save after that updates the
  same row (`created_at` untouched, `updated_at` bumped).
- `AccountService.update_account` requires the same non-blank
  `business_name`/`email`/`address_line1` as `create_account` (the other
  address lines stay independently optional, blank input normalised to
  `NULL`) and always replaces the whole record (no partial-field updates)
  — 404s via `get_account` if the id doesn't exist first.
- `StatsService.get_stats(organisation_id, currency)` is scoped to one
  `Organisation` — not a system-wide snapshot, same as
  `InvoiceService.monthly_totals`. `total_paid` follows that same method's
  currency-filtering convention: only paid invoices in `currency` count.
- `ExpenseService.create_expense` assigns `number` immediately — unlike
  `Quote`/`Invoice`, there's no draft state for it to be deferred past, so
  it's never `NULL` (migration 8's `expenses.number` is `NOT NULL`, unlike
  `quotes.number`/`invoices.number`). `add_line_item` isn't gated behind any
  status check — a line item can be added at any time, not just while
  "draft" (there is no draft).
- `InvoiceService.pay()` only transitions `sent → paid` — rejects `draft`
  (never sent, nothing to have been paid for), `void` (cancelled), and an
  already-`paid` invoice. Stricter than `void()`, which also allows `draft`.
- `InvoiceService.monthly_totals(organisation_id, currency, months=12)`
  buckets every non-`draft`, non-`void` invoice **belonging to that
  organisation** (not filtered by account) by the calendar month of
  `issue_date` (when it was created, not `due_date`/`created_at`'s
  time-of-day), for the trailing `months` months ending with the current
  one. Only invoices whose `currency` matches the argument count — a
  different-currency invoice is excluded, never summed in regardless.
  `paid` invoices go in `paid_total`; everything else left (`sent`) goes in
  `unpaid_total`. Months with no matching invoices still appear, with both
  totals `Decimal("0")`.
- Fetching another organisation's `Account`/`Quote`/`Invoice` by id raises
  `NotFound` (`AccountService.get_account`/`QuoteService.get_quote`/
  `InvoiceService.get_invoice` all filter by `organisation_id` at the
  storage layer, not just by id) — the same error as "doesn't exist",
  deliberately, so a cross-tenant lookup never reveals *that* a given id
  belongs to someone else, only that it isn't visible to you.
- `BusinessProfile.document_header`/`document_footer` are rendered into
  every quote/invoice PDF this user generates (`pdf.py`'s
  `document_header_lines()`/`document_footer_lines()`, called from `_render`
  with the same `from_profile` parameter `business_profile_lines()`
  already uses) — the header above the title, the footer below the totals
  table, each split into its non-blank lines. Deliberately not a per-page
  running header/footer (that needs reportlab page templates/canvas
  callbacks); just fixed text once at the top and bottom of the document.

## Multi-tenancy

`Organisation` is the tenant boundary (see its docstring in `models.py`).
Every `Account`/`Quote`/`Invoice`/`Expense` create/get/list call takes an
`organisation_id` — there is no "admin" bypass anywhere in `core.py`.

- **API**: `api/app.py`'s `get_organisation_id` dependency resolves it from
  the authenticated user (`Depends(get_current_user)` →
  `application.organisations.get_or_create_for_user(user.id)`), auto-creating
  an `Organisation` the first time that user hits any domain route. A
  client never sends or sees an `organisation_id` — it's entirely
  server-side, deliberately absent from every request/response schema in
  `api/schemas.py`.
- **CLI**: has no login session to resolve a user from, so `--user-id` is a
  **required** option on every account/quote/invoice/expense command (a
  breaking change from before `Organisation` existed, where these commands
  took no user context at all) — see `docs/development.md`'s CLI section.
- **Currently**: exactly one login user per `Organisation`
  (`organisation_members.user_id` is `UNIQUE`) — auto-created, never
  explicitly named by a user today (see `OrganisationService.get_or_create_for_user`'s
  `default_name`). "Multiple users per organisation" (inviting a
  colleague to share one business's data) is deliberately future work: the
  schema shape doesn't need to change for it, only dropping that `UNIQUE`
  constraint and adding an invite/add-member flow — see `docs/roadmap.md`.
- `accounts`/`quotes`/`invoices.organisation_id` is `NOT NULL` as of
  migration 7 (a fresh `CREATE TABLE`, not the `ALTER TABLE ADD COLUMN`
  migration 3 originally used, which had to be nullable since SQLite can't
  add a `NOT NULL` column without a default and there was no meaningful one
  to backfill existing rows with at the time). Every account/quote/invoice
  has always had an `organisation_id` set at creation since `Organisation`
  was introduced, so by the time migration 7 ran there was nothing left
  needing that historical nullability.

## Login accounts (not this schema)

`sessionkit`'s `User` (email, name, password hash, TOTP state) and its
`sessions`/`recovery_codes` tables live in a **separate** SQLite file
(`auth.db` by default) with their own schema, owned and migrated by the
`sessionkit` package itself — not listed here, not touched by
`storage/schema.py`. See `CLAUDE.md` for why `User`, `Account`, and
`BusinessProfile` are three deliberately different things.

## Demo data

`invoice-system-cli init-db` seeds a demo login user, a `BusinessProfile`,
several `Account`s, a 12-month spread of `Quote`/`Invoice` statuses, and a
handful of `Expense`s across a few accounts
(`src/invoice_system/demo_data.py`) unless `--no-demo` is passed. It's
idempotent (a no-op once the demo user exists) and goes through the real
service layer with a backdated clock, not hand-crafted storage rows — see
`CLAUDE.md` for why, and the "keep this in sync" convention for updating it
when a feature changes what these entities can look like.

## Not yet modelled

Partial-payment tracking (a `Payment` model recording amounts/dates against
an invoice) and a real `sent → overdue` status transition are future work —
see `docs/roadmap.md`. Marking an invoice fully `paid` is implemented
(`InvoiceService.pay()`, a status flag, not a ledger); "overdue" is only
ever derived for display (`web/src/pages/HomePage.tsx`'s `isOverdue`), never
written to `Invoice.status`.
