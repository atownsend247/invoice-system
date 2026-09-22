# Data model

**Status: implemented** (`src/invoice_system/models.py`,
`storage/schema.py`). Keep this table in sync with the actual schema — this
doc is read as ground truth. `storage/schema.py`'s `MIGRATIONS` has
twenty-one entries: the flattened baseline (2026-09-16), migration 2 (added `tax_rate`
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
ids" below and `CLAUDE.md`'s migrations gotcha), migration 8 (added
`expenses`/`expense_line_items` — two brand new tables, a plain `CREATE
TABLE` each, no rebuild needed), migration 9 (added
`expense_attachments` — metadata for uploaded supplementary PDFs; the bytes
themselves live on the filesystem, not in this table — one more new table,
no rebuild needed), and migration 10 (added `idx_accounts_organisation`,
`idx_quotes_organisation_account`/`idx_invoices_organisation_account`, and
`idx_quotes_organisation_status`/`idx_invoices_organisation_status` —
plain `CREATE INDEX` statements backing the server-side pagination/
filtering added to `GET /accounts`/`GET /quotes`/`GET /invoices`, see
`docs/api.md`'s pagination convention), migration 11 (added
`registration_invites` — one more new table, no rebuild needed — see the
`RegistrationInvite` row below and `docs/api.md`'s invite-gated
registration convention), and migration 12 (split
`business_profiles.document_header`/`document_footer` - added by
migration 6 above - into three independent pairs, one per document type:
`quote_`/`invoice_`/`expense_document_header`/`document_footer`, same
add-columns/copy-data/drop-old-columns shape as migration 5's
`accounts.address` split, existing values copied into all three new pairs
rather than dropped - see `docs/api.md`'s per-document-type header/footer
convention), migration 13 (added `idx_invoices_organisation_quote` —
one more plain `CREATE INDEX`, backing `list_invoices`' new `quote_id`
filter — see `CLAUDE.md`'s Quote/Invoice conversion note), and migration 14
(added a nullable `accent_color TEXT` column to `business_profiles` — one
more plain `ADD COLUMN`, same shape as migration 6, backing the brand
colour used across every quote/invoice/expense PDF a user generates — see
`CLAUDE.md`'s `BusinessProfile` accent colour paragraph), migration 15
(added `domains` — one more brand new table plus its own
`idx_domains_account` index, no rebuild needed, same reasoning as every
other pure-addition migration in this file — see the `Domain` row below),
migration 16 (added `registrars` — another brand new table plus its
own `idx_registrars_organisation` index, no rebuild needed either — see
the `Registrar` row below), migration 17 (added `expenses.expense_date`
— same rebuild-free shape as migration 5's `accounts.address_line1`
split, a `NOT NULL DEFAULT ''` `ADD COLUMN` backfilled via `UPDATE
expenses SET expense_date = issue_date` — see the `Expense` row below),
migration 18 (added `quote_events`/`invoice_events` — two brand new
tables plus their own `idx_quote_events_quote`/`idx_invoice_events_invoice`
indexes, no rebuild needed and no backfill attempted (a pre-existing
quote/invoice's real history was never captured) — see the
`ActivityEvent` row below), migration 19 (added
`business_profiles.quote_validity_days INTEGER NOT NULL DEFAULT 30` —
one more plain `ADD COLUMN`, same shape as `payment_terms_days` itself —
see the `BusinessProfile` row below), migration 20 (added six more
plain `ADD COLUMN`s to `business_profiles` —
`quote_number_prefix TEXT NOT NULL DEFAULT 'Q-'`/
`quote_number_digits INTEGER NOT NULL DEFAULT 4`, and the `invoice_`/
`expense_` equivalents defaulting `'INV-'`/`'EXP-'` — same constant-default
shape as `payment_terms_days`/migration 19, no rebuild needed — see the
`BusinessProfile` row below and `docs/api.md`'s number-prefix/digits
convention), and migration 21 (`domains` became organisation-scoped
directly instead of resolving tenant ownership only through its parent
account — a rebuild-and-swap, not a plain `ADD COLUMN`, since
`account_id` relaxes from `NOT NULL` to nullable, which SQLite can't
`ALTER COLUMN` in place, same shape as migration 4; the new
`organisation_id NOT NULL` column is backfilled via a join to each
existing domain's account, safe because every domain already had one at
the time — see the `Domain` row below and `docs/api.md`'s `Domain`
Convention).
Schema changes from here on are new entries appended to that list, not
edits to any of these twenty-one.

## Entities

| Entity | Key fields | Notes |
|---|---|---|
| `Organisation` | id, name, created_at | The tenant boundary — every `Account`/`Quote`/`Invoice` belongs to exactly one. Auto-created the first time a login user needs one (`OrganisationService.get_or_create_for_user`), via an `organisation_members` join table (`organisation_id`, `user_id`, `created_at`) with `UNIQUE` on `user_id` enforcing "one organisation per user" *for now* — see "Multi-tenancy" below. |
| `Account` | id, organisation_id, business_name, contact_name, email, phone, address_line1, address_line2, town_or_city, county, postcode, created_at | A business you provide a service to and bill, scoped to one `Organisation`. Editable after creation (`AccountService.update_account`, full replace). Not a login identity — see `CLAUDE.md`. Address fields follow the same UK GOV.UK Design System pattern as `BusinessProfile`'s below, except `address_line1` is required here (an `Account` is a real client being billed, not the user's own optionally-published details) — the rest are each independently optional. |
| `Domain` | id, organisation_id, account_id, domain_name, expiry_date, registrar, auto_renew, created_at, updated_at | A domain name a business tracks — which domain, when it expires, who it's registered with, whether it's set to auto-renew. **Organisation-scoped directly** (`organisation_id`, migration 21) — structurally close to `Registrar` below now, not resolved through a parent `Account` the way it used to be. `account_id` is **nullable** — a domain is created independently (the standalone Domains page) and only *optionally* linked to one `Account` at a time; changing that link is a dedicated action (`DomainService.link_domain`/`unlink_domain`), not part of a plain edit. `domain_name`/`expiry_date`/`registrar` all required; `auto_renew` defaults `false`, purely informational. Editable in place (`DomainService.update_domain`, full replace of its own fields, mirroring `AccountService.update_account` — but never touches `account_id`) — see `CLAUDE.md`. `registrar` is a plain string, not a foreign key to `Registrar` below — the web UI populates it from a strict `<select>` sourced from that managed list, but stores the chosen name, so a later rename/delete of a `Registrar` never needs to touch this row. |
| `Registrar` | id, organisation_id, name, notes, created_at, updated_at | A business's managed list of domain registrars, used to populate the Domain form's registrar `<select>` — see `CLAUDE.md`. **Organisation-scoped**, same as `Domain` above now — carries its own `organisation_id`, full CRUD, tenant ownership checked directly. Unlike `Account`, supports delete — nothing holds a foreign key to a `Registrar` (see the `Domain` row above), so there's no *database-level* cascade. `RegistrarService.delete_registrar` still refuses (`Conflict`, 409) to delete one that at least one `Domain` currently names — an *application-level* guard computed at request time via `count_domains_by_registrar` (not a stored column), not enforced by SQLite — see `CLAUDE.md`'s `Registrar` Convention and `docs/api.md`'s `domain_count`/`account_count` Convention. `name` required; `notes` optional free text, no format validation. |
| `Quote` | id, organisation_id, account_id, number, status, currency, issue_date, expiry_date, created_at | `status`: `draft \| sent \| accepted \| rejected \| expired \| converted`. `number` (`Q-0001`, ...) is assigned on `send`, not on creation, and is unique per-`organisation_id`, not globally (see migration 4 above) — two organisations' first quotes can both be `Q-0001`. `issue_date` defaults to today but is settable at creation; `expiry_date` is always computed as `issue_date + BusinessProfile.quote_validity_days`, not independently settable. |
| `Invoice` | id, organisation_id, account_id, quote_id, number, status, currency, issue_date, due_date, created_at | `status`: `draft \| sent \| paid \| overdue \| void`. `quote_id` is set when created via conversion, `NULL` otherwise. `number` (`INV-0001`, ...) and `due_date` are assigned on `send`, and — same as `Quote.number` — unique per-`organisation_id`, not globally. `due_date` is `issue_date + payment_terms_days`, not "today" + `payment_terms_days`. `issue_date` defaults to today but is settable at conversion time (`QuoteService.convert_to_invoice`, the only place an `Invoice` is ever created), allowing a backdated invoice. `paid` is assigned by `InvoiceService.pay()`, only from `sent` — `overdue` is a defined enum value nothing ever actually sets (see "Not yet modelled"). |
| `LineItem` | id, description, quantity, unit_price, tax_rate, position | One shape, shared by quotes, invoices, and expenses; associated via `quote_line_items`/`invoice_line_items`/`expense_line_items` join tables (`quote_id`/`invoice_id`/`expense_id` + the same columns). `tax_rate` is a fraction (`0.20` = 20% UK VAT; `0` = none), independently set per line. `net_total`/`tax_amount`/`total` (`net_total + tax_amount`, gross) are derived properties, never stored — `tax_amount` is rounded to the minor currency unit, `net_total` is not (see `CLAUDE.md`). |
| `ActivityEvent` | id, event_type, from_status, to_status, occurred_at | The audit trail for a `Quote`/`Invoice` — creation and status changes only, not every field edit. Same "one shape, two parent tables" pattern as `LineItem`: associated via `quote_events`/`invoice_events` join tables (`quote_id`/`invoice_id` + the same columns), not one polymorphic table. `event_type`: `created \| status_changed`; `from_status` is `NULL` for a `created` event. Fetched newest-first (`ORDER BY rowid`, not `occurred_at` — see `CLAUDE.md`). |
| `Expense` | id, organisation_id, account_id, number, currency, issue_date, expense_date, created_at | A cost incurred against an `Account` (e.g. a domain renewal paid on the client's behalf) — see `CLAUDE.md`. Unlike `Quote`/`Invoice`, no `status` column: there's no draft/sent lifecycle, so `number` (`EXP-0001`, ..., same per-`organisation_id` composite-unique-index pattern as `Quote.number`/`Invoice.number` — see migration 8) is `NOT NULL` and assigned by `ExpenseService.create_expense` immediately, not deferred to a later `send()`. `issue_date` (recorded, fixed) and `expense_date` (when the money was actually spent, defaults to today, the one field here editable after creation via `ExpenseService.update_expense_date`) answer different questions — `monthly_totals` buckets by `expense_date`, not `issue_date`. |
| `ExpenseAttachment` | id, expense_id, filename, content_type, size, created_at | A supplementary PDF (e.g. a scanned receipt) uploaded against an `Expense` — see `CLAUDE.md`. **Metadata only**: the bytes live on the filesystem (`attachments.py`'s `AttachmentStore`, keyed by `id`), not in this row — `filename`/`content_type`/`size` exist purely for display/validation. Addable at any time, same no-lifecycle reasoning as `Expense.line_items`. No `organisation_id` column, same as `quote_line_items`/`expense_line_items` — tenant ownership is always resolved via the parent `expense_id` first (`ExpenseService.get_attachment_bytes`/`delete_attachment` both call `_get_expense` before touching an attachment). |
| `BusinessProfile` | id, user_id, title, first_name, last_name, business_name, address_line1, address_line2, town_or_city, county, postcode, payment_terms_days, quote_validity_days, currency, utr, vat_number, bank_account_name, bank_sort_code, bank_account_number, quote_document_header, quote_document_footer, invoice_document_header, invoice_document_footer, expense_document_header, expense_document_footer, quote_number_prefix, quote_number_digits, invoice_number_prefix, invoice_number_digits, expense_number_prefix, expense_number_digits, accent_color, created_at, updated_at | The logged-in user's *own* details, in four groups (see `CLAUDE.md`), presented as tabs on the Settings page: user settings (`title`/`first_name`/`last_name` all optional - `first_name`/`last_name` have no sensible default, so unlike most other required fields elsewhere in this app they're not validated as non-blank either, see `docs/api.md`'s Convention of the same name), business settings (`business_name` optional too, same "no sensible default" reasoning; `address_line1`/`address_line2`/`town_or_city`/`county`/`postcode` — a UK GOV.UK Design System-style address, each line independently optional), payment and tax settings (`payment_terms_days`; `quote_validity_days` — the quote equivalent, drives `QuoteService.create_quote`'s calculated `expiry_date`; `currency` — the home dashboard's *reporting* currency, defaults `"GBP"`, independent of any quote/invoice's own `currency` — `utr`/`vat_number` purely informational, not rendered on a PDF; `bank_account_name`/`bank_sort_code`/`bank_account_number` render as a "Payment details" section on generated **invoices only**, never quotes or expenses — see `pdf.py`'s `bank_details_lines()`), document settings (three **independent** pairs, one per document type, not one shared pair — `quote_document_header`/`quote_document_footer`, `invoice_document_header`/`invoice_document_footer`, `expense_document_header`/`expense_document_footer`, each free text, each field independently optional — inserted into the matching quote/invoice/expense PDF this user generates, see `pdf.py`'s `quote_header_lines()`/`quote_footer_lines()` and its `invoice_`/`expense_` equivalents, and the invariants below — plus, also per document type, `quote_number_prefix`/`quote_number_digits` (default `"Q-"`/`4`), `invoice_number_prefix`/`invoice_number_digits` (default `"INV-"`/`4`), and `expense_number_prefix`/`expense_number_digits` (default `"EXP-"`/`4`), which control how that type's number is formatted when assigned (`f"{prefix}{value:0{digits}d}"`) — only affects numbers issued from then on, never rewrites an already-issued one, see `docs/api.md`'s number-prefix/digits convention — plus `accent_color`, one shared `#RRGGBB` hex colour across all three document types, the one field on this row whose format is actually validated rather than accepted as free text, since it's interpolated directly into a CSS declaration in the rendered PDF template — see `pdf.py`'s `_render()` and `CLAUDE.md`). Not `Account` (the client being billed). One per `user_id` (`UNIQUE`), which is sessionkit's `User.id` — a plain column, not an enforced FK (see `CLAUDE.md`, "Login accounts" below). Deliberately still per-*user*, not per-`Organisation` — see "Multi-tenancy" below. Every optional field: blank input is normalised to `NULL`, never stored as `""` — **except** `first_name`/`last_name`/`business_name`, which stay a plain `TEXT NOT NULL DEFAULT ''` column each (not nullable) and store a blank value literally as `""`, since nothing downstream needs to distinguish "never set" from "set to blank" for these three. |
| `RegistrationInvite` | token, created_at, expires_at, used_at | A single-use, time-limited token gating the public `/register` page — see `CLAUDE.md`'s invite-gated registration convention and `docs/api.md`. `token` (a UUID4) is the primary key; nothing else ever looks one up. **No `organisation_id` and no email column** — not scoped to a tenant (an invite exists before any `Organisation` does) and not tied to a specific email (whoever holds a valid token can register with any one). `used_at` is `NULL` until consumed; `RegistrationInviteService.check_invite` treats an unknown token, an expired one, and an already-used one identically. Created **only** via `invoice-system-cli invite create` — no API route creates one. |
| counters (internal) | name, value | Backs `next_quote_number`/`next_invoice_number`/`next_expense_number`; not a domain entity, not exposed via API/CLI. `name` is `"<organisation_id>:quote"`/`"<organisation_id>:invoice"`/`"<organisation_id>:expense"`, not a bare `"quote"`/`"invoice"`/`"expense"` — each organisation gets its own independent sequence starting from one. |

`MonthlyInvoiceTotals` (`month`, `paid_total`, `unpaid_total`),
`MonthlyExpenseTotals` (`month`, `total` — no paid/unpaid split, an
`Expense` has no status), and `Stats` (`account_count`, `quote_count`,
`invoice_count`, `quotes_sent_count`, `quotes_converted_count`,
`total_paid`) are **not** stored tables — they're
`InvoiceService.monthly_totals()`/`ExpenseService.monthly_totals()`/
`StatsService.get_stats()`'s return shapes, computed on read for the home
dashboard. See the invariants below for exactly what the two `monthly_totals`
methods include/exclude.

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
a timestamp, notably under a frozen/fake clock in tests). This stable order
is also what makes `LIMIT`/`OFFSET` pagination well-defined across two
separate requests a page apart (see `docs/api.md`'s pagination convention)
- a page boundary that could reshuffle between calls would make "page 2"
meaningless. `list_accounts`/`list_quotes`/`list_invoices` all support
`limit=None` (skipping `LIMIT`/`OFFSET` entirely) for the handful of
internal callers - `StatsService.get_stats`,
`InvoiceService.monthly_totals` - that genuinely need every row rather than
one page; migration 10 added the `(organisation_id, ...)` indexes backing
both that full-scan case and the paginated one (see the migrations list
below).

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
Quote   1──* ActivityEvent  (via quote_events)
Quote   0/1──0/1 Invoice  (conversion; quote.status becomes "converted")
Invoice 1──* LineItem   (via invoice_line_items)
Invoice 1──* ActivityEvent  (via invoice_events)
Expense 1──* LineItem   (via expense_line_items)
Expense 1──* ExpenseAttachment
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
- Every `Quote`/`Invoice` creation and status change appends an
  `ActivityEvent` row — enforced by `QuoteService`/`InvoiceService`
  themselves (a private `_record_event()` on each), not by storage; nothing
  stops a caller going around the service layer and leaving history gaps,
  same as every other service-layer invariant in this list.
- `Quote.expiry_date` and `Invoice.due_date` are always derived at write
  time (`issue_date + quote_validity_days`/`payment_terms_days`
  respectively), never independently settable — a stale/inconsistent
  `expiry_date`/`due_date` relative to `issue_date` can't be written
  through the service layer.
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
- `ExpenseService.add_attachment` requires `content_type ==
  "application/pdf"` or a `.pdf` filename extension (either is enough — a
  browser's own `Content-Type` guess for an unfamiliar extension isn't
  always trustworthy), a non-empty file, and a size at or under
  `MAX_ATTACHMENT_SIZE` (10MB) — otherwise `ValidationFailed`. The file is
  written to disk (`AttachmentStore.save`) *before* the metadata row is
  inserted; `delete_attachment` removes the DB row *before* the file — in
  both cases, whichever order leaves at worst an orphaned file (harmless,
  just wasted disk space) rather than a DB row pointing at bytes that were
  never written or no longer exist.
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
- `ExpenseService.monthly_totals(organisation_id, currency, months=12)` is
  the same aggregation, over `Expense.issue_date`/`.currency`, with no
  status to split on - every expense in a matching month/currency sums
  into that month's single `total`. Months with no matching expenses still
  appear, with `total` `Decimal("0")` - same "always 12 rows" guarantee as
  `InvoiceService.monthly_totals`.
- Fetching another organisation's `Account`/`Quote`/`Invoice` by id raises
  `NotFound` (`AccountService.get_account`/`QuoteService.get_quote`/
  `InvoiceService.get_invoice` all filter by `organisation_id` at the
  storage layer, not just by id) — the same error as "doesn't exist",
  deliberately, so a cross-tenant lookup never reveals *that* a given id
  belongs to someone else, only that it isn't visible to you.
- `BusinessProfile`'s document header/footer is three independent pairs —
  `quote_document_header`/`quote_document_footer`,
  `invoice_document_header`/`invoice_document_footer`,
  `expense_document_header`/`expense_document_footer` — rendered into the
  matching quote/invoice/expense PDF this user generates (`pdf.py`'s
  `quote_header_lines()`/`quote_footer_lines()` and its `invoice_`/
  `expense_` equivalents; `_render()` takes plain `header_lines`/
  `footer_lines` params rather than deciding which field to read itself,
  and each of `render_quote_pdf`/`render_invoice_pdf`/`render_expense_pdf`
  passes in its own pair) — the header above the title, the footer below
  the totals table, each split into its non-blank lines. Deliberately not
  a per-page running header/footer (that needs CSS `position: running()`/
  `@page` margin-box content); just fixed text once at the top and bottom
  of the document.

## Multi-tenancy

`Organisation` is the tenant boundary (see its docstring in `models.py`).
Every `Account`/`Quote`/`Invoice`/`Expense`/`Domain`/`Registrar`
create/get/list call takes an `organisation_id` — there is no "admin"
bypass anywhere in `core.py`. `Domain` only gained its own
`organisation_id` in migration 21 — before that, tenant ownership was
resolved through its parent `Account` instead, back when a domain always
had to have one (see the `Domain` row above).

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
(`storage/db/auth.db` by default — see `docs/development.md`'s "Where
persistent data lives") with their own schema, owned and migrated by the
`sessionkit` package itself — not listed here, not touched by
`storage/schema.py`. See `CLAUDE.md` for why `User`, `Account`, and
`BusinessProfile` are three deliberately different things.

## Demo data

`invoice-system-cli init-db` seeds a demo login user, a `BusinessProfile`,
several `Account`s, a 12-month spread of `Quote`/`Invoice` statuses, and a
handful of `Expense`s across a few accounts (one with a synthetic PDF
`ExpenseAttachment` generated on the fly via reportlab, standing in for a
real upload) (`src/invoice_system/demo_data.py`) unless `--no-demo` is
passed. It's
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
