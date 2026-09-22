# CLAUDE.md

Invoice System: a freelancer/small-business billing tool. Domain shape is
Account (the business you provide a service to — business name, contact,
address; editable after creation) → Quote → Invoice, where a Quote converts
into an Invoice rather than the two being independently created. Each line
item can carry its own UK VAT rate. Quotes and Invoices are each
independently viewable (an in-page preview) or downloadable as PDFs, and a
sent invoice can be marked `paid` (a single status flag, not a payment
ledger). An Account can also have `Expense`s recorded against it (e.g. a
domain renewal paid on the client's behalf) — unlike Quote/Invoice, an
Expense has no draft/sent lifecycle: it's a record of money already spent,
so it gets its `EXP-0001` number immediately at creation rather than at a
later "send" step, and line items can be added at any time, not gated
behind a status check (see ExpenseService). A `BusinessProfile` holds the
logged-in user's *own* business
details (name/address/payment terms/reporting currency/UTR/VAT/bank
details/a separate document header & footer per document type - quote,
invoice, expense - shown on the matching PDFs they generate/an accent
colour used across all three) — see below for why that's a third,
deliberately separate thing from both `Account` and sessionkit's `User`.
Every `Account`/`Quote`/`Invoice`/`Expense` also belongs to exactly one
`Organisation` — the tenant boundary, auto-created per login user, so one
user's data is never visible to another (see below and
`docs/data-model.md`'s "Multi-tenancy"). A fresh `invoice-system-cli
init-db` seeds a year of demo data (accounts, quotes, invoices, a demo
login) by default — see Commands and `demo_data.py`.

## Where things are

- Design docs: `docs/` — start with `docs/development.md` (how to run it) and
  `docs/architecture.md`. `docs/data-model.md`, `docs/api.md`, `docs/roadmap.md`
  are the reference. `docs/deployment.md` covers the `Jenkinsfile`/`deploy/`
  pipeline (build/test/deploy to a Proxmox LXC container). **Keep these in
  sync when code changes** (roadmap phases, endpoint tables, model tables) —
  a stale doc is worse than no doc, because an agent reads it as ground truth.
- `Jenkinsfile` (repo root) + `deploy/` — CI/CD: build, test, and (on `main`)
  deploy both the backend and the web client to a Proxmox LXC container over
  SSH. `deploy/deploy.sh` does the actual rsync/ssh work;
  `deploy/invoice-system-api.service` and `deploy/nginx-invoice-system.conf`
  are one-time-setup reference config for the container, not applied by the
  pipeline itself. See `docs/deployment.md`.
- `src/invoice_system/` — flat top level holds the load-bearing modules
  (`core.py` all domain logic — `AccountService`, `QuoteService`,
  `InvoiceService`, `ExpenseService`, `BusinessProfileService`,
  `StatsService`; `models.py`,
  `errors.py`, `clock.py`, `ids.py`, `attachments.py` (filesystem storage
  for uploaded expense-attachment PDFs, see the ExpenseService Conventions
  bullet below), `paths.py` (where persistent data lives on disk - a
  CLI/API entry-point concern, not domain logic - see the Gotchas bullet
  below), `repository.py` the storage Protocol,
  `factory.py` wiring, `pdf.py` PDF rendering used by both entry points,
  `auth.py` wiring for the login/session cross-cutting concern,
  `demo_data.py` the seed data `init-db` loads by default — see below).
  Subpackages: `storage/` (schema + migrations, the concrete
  `SqliteRepository`), `api/` (thin FastAPI layer — `app.py` the domain
  routes, `auth.py` the login/session routes and the `get_current_user`
  dependency), `cli/` (thin Click layer). `tests/` mirrors the package 1:1
  (`tests/{core,api,cli,storage}/`) + a root `conftest.py` with shared
  fixtures.
- `web/` — React 19 + TypeScript + Vite SPA, a sibling of `src/`, its own
  test runner (Vitest) and build, its own README (`web/README.md`). Pins its
  own Node version in `web/.node-version` (nodenv-style) — see gotchas.

Login/sessions are [sessionkit](https://github.com/atownsend247/bb-py-sessionkit)
(a separate PyPI-style dependency, pinned by git tag in `pyproject.toml`),
wired in by `src/invoice_system/auth.py` + `api/auth.py` — **not** a
hand-rolled module here. Its `User` is a login identity, stored in its own
SQLite file (`storage/db/auth.db` by default, `INVOICE_SYSTEM_AUTH_DB` to
override - see `paths.py`) —
do not confuse it with this app's own `Account` (a client business being
billed). `core.py` never imports `sessionkit` — see architecture rules.
Manage users with the bundled `sessionkit` CLI (`uv run sessionkit add ...`),
not through this app; there is no *unconditional* public signup route —
`POST /auth/register` (below) is a narrow, invite-gated exception to that,
not a general one.

Four separate things are easy to conflate here — don't:
- **`Account`** (this app's own domain table) — a *client* business being
  billed via quotes/invoices.
- **sessionkit's `User`** (`auth.db`) — a *login* identity. Has no business
  details at all beyond email/name.
- **`Organisation`** (this app's own domain table) — the *tenant boundary*.
  Every `Account`/`Quote`/`Invoice` belongs to exactly one; a login `User`
  belongs to exactly one too (`organisation_members`, `UNIQUE` on
  `user_id`), auto-created on that user's first domain request/CLI command
  (`OrganisationService.get_or_create_for_user`). Not a business's own
  details (that's `BusinessProfile`, below) — currently just an id/name/
  timestamp, existing purely so `AccountService`/`QuoteService`/
  `InvoiceService`/`StatsService` can scope every query to "this caller's
  data only." See `docs/data-model.md`'s "Multi-tenancy" for the "multiple
  users per organisation" future work this is already shaped for.
- **`BusinessProfile`** (this app's own domain table, `business_profiles`) —
  the logged-in user's *own* details, in four groups matching the Settings
  page's tabs: user settings (name — **never shown on a PDF**), business
  settings (business name + address), payment and tax settings (payment
  terms, reporting currency, UTR/VAT, bank details), document settings
  (per-document-type header/footer pairs, plus a shared `accent_color`) —
  see `docs/data-model.md`'s `BusinessProfile` entity row for the full
  field list and `docs/api.md`'s Conventions for how the document/
  accent-colour fields behave on a generated PDF. One per
  user, keyed by `user_id` = sessionkit's `User.id` — deliberately still
  per-*user*, not per-`Organisation`, even after `Organisation` was
  introduced (see `docs/data-model.md`'s "Multi-tenancy": today it's a
  distinction without a difference since each user has exactly one
  organisation, but it stops being one the day an organisation gains a
  second member, and "whose business card is this" should stay an
  individual's answer even then). That's a **plain
  integer column, not an enforced foreign key** — `business_profiles` lives
  in `invoice_system.db`, `users` lives in the separate `auth.db`, and
  SQLite can't enforce a cross-database constraint. Deleting a user via
  `sessionkit delete` leaves its `business_profiles` row orphaned; nothing
  cleans it up automatically (there's no hook for sessionkit to call into
  the domain db, and it shouldn't gain one — see
  `docs/extracting-reusable-packages.md` on why a vendored concern stays
  ignorant of the host app).

## Commands

- Tests: `uv run pytest --cov=src/invoice_system --cov-report=term-missing`
  (run the **full** suite before finishing a change; CI enforces a 90%
  coverage floor, see gotchas).
- Lint/format: `uv run ruff check .` / `uv run ruff format .` (CI runs both,
  the latter with `--check`; `ruff format` first if `ruff check` complains
  about a line-length issue a format pass would resolve).
- First-run / bootstrap: `uv sync && uv run invoice-system-cli init-db` —
  creates the domain SQLite file, applies migrations, and (by default)
  seeds a year of demo data: accounts, quotes/invoices in a mix of statuses,
  and a demo login (`demo@example.test` / `demo-password-123`, both in
  `demo_data.py`) — log in with that immediately, no separate signup step.
  Pass `--no-demo` for an empty database instead, then create your own
  login with `uv run sessionkit add you@example.com`. Re-running `init-db`
  is safe either way — demo seeding is a no-op once the demo user exists.
  `init-db --reset` wipes all domain data (accounts/quotes/invoices/
  expenses/business profiles/organisations — the whole domain database
  file) and every uploaded expense-attachment PDF, then reinitialises from
  scratch — irreversible, so it prompts for confirmation unless `--yes`/
  `-y` is also given. Deliberately leaves `auth.db` untouched (existing
  logins, demo included, are kept) — see the Gotchas bullet below for why
  that needed a small `seed_demo_data` fix, not just a CLI-layer change.
- Serve: `uv run uvicorn invoice_system.api.app:app --reload` (API on
  `:8000`; everything persistent defaults under `storage/` -
  `INVOICE_SYSTEM_STORAGE_DIR` moves that whole base directory,
  `INVOICE_SYSTEM_DB` / `INVOICE_SYSTEM_AUTH_DB` /
  `INVOICE_SYSTEM_ATTACHMENTS_DIR` override an individual path within it -
  see `paths.py` and `docs/development.md`'s "Where persistent data
  lives").
- CLI: `uv run invoice-system-cli --help` (or the installed
  `invoice-system-cli` entry point) — mirrors the API one-for-one over the
  same storage. **Not** behind login — it's a local, trusted tool; only the
  HTTP API is gated (see architecture rules). Where the API resolves "which
  user"/"which organisation" from the Bearer token, the CLI takes an
  explicit `--user-id` instead — **required** on every
  account/quote/invoice/expense
  command (`account create/list/update`, `quote
  create/update/add-item/update-item/delete-item/send/convert/pdf`, `invoice
  list/send/void/pay/monthly-totals/pdf`, `expense
  create/list/add-item/pdf`, `expense attachment
  add/list/download/delete`, `stats`), since there's no session
  to resolve an organisation from otherwise (see "Four separate things"
  above). `settings show/set`, `invoice send`, `quote pdf`/`invoice pdf`/
  `expense pdf`
  additionally use that same `--user-id` for their pre-existing purpose
  (payment-terms-driven due dates, the PDF "from" party). `--attachments-dir`
  (top-level, alongside `--db`) points at the uploaded expense-attachment
  storage directory (default `attachments/`).
- Web: `cd web && npm install && npm run dev` (Vite on `:5173`, or whatever
  port it lands on if that one's taken — it logs the actual one; note it
  binds `localhost`, which may resolve to the IPv6 loopback only, so prefer
  `localhost` over `127.0.0.1` when hitting it directly). `VITE_API_BASE_URL`
  points it at the API if set; unset, `api.ts`'s `defaultApiBaseUrl()`
  derives it from whatever host the page itself was loaded from instead of
  a hardcoded one (see the `npm run dev:lan` gotcha below). `npm test` /
  `npm run test:e2e` (Playwright; spins up its own throwaway backend + this
  app, see `web/README.md`) / `npm run build` in `web/`. `npm run dev:lan`
  (`vite --host`) plus `uvicorn ... --host 0.0.0.0` serves both to other
  devices on the same network — opt-in, not the default; see
  `docs/development.md`.
- CI: `.github/workflows/ci.yml` — `backend`, `frontend`, `e2e` (the last
  gated on the first two passing), on every push/PR. See
  `docs/testing-and-ci.md`.

## Architecture rules (don't violate)

- **Domain logic lives only in `invoice_system.core`.** Everything else (API
  routes, CLI commands, background jobs) is a thin translation layer — no
  rules, no validation logic, no aggregation outside `core`. This is the
  single rule worth enforcing hardest: it's what keeps the domain testable
  without spinning up a web server, and keeps two entry points (the REST API
  and the CLI) from silently disagreeing on a rule.
- **Cross-cutting concerns that aren't the domain** (login/sessions,
  payment-provider integration, email delivery...) **get their own module or
  package**, not bolted onto core. `pdf.py` is the current example: it turns
  a `Quote`/`Invoice` into bytes for the CLI/API to hand back, but it isn't a
  domain rule, so `core.py` never imports it — only `cli/` and `api/` do. If
  a concern is generic enough to be useful in an unrelated project, it's a
  strong candidate to extract as a standalone package from day one — see
  `docs/extracting-reusable-packages.md`.
- **All storage access goes through a `Repository` Protocol**
  (`repository.py`). The concrete implementation is persistence only — it
  does not decide business rules, generate ids, or validate input. This is
  what makes the domain layer testable against a fake/in-memory
  implementation instead of a real database. Every id in this app is a
  UUID4 string, generated by the service layer *before* constructing the
  dataclass passed to `Repository.create_*` (see the next bullet -
  `new_id: IdGenerator`, the same injectable-ambient-dependency pattern as
  `clock`) — `SqliteRepository.create_*` only ever persists whatever id
  it's given (never `cursor.lastrowid`), so this rule is stricter now than
  it used to be ("beyond what the DB gives it" no longer applies: the DB
  doesn't generate ids here at all).
- **Injectable `clock`** (and any other ambient, hard-to-test dependency — a
  password hasher, a random invoice-number generator, a PDF/email client)
  **on every service that needs one.** Tests supply a fake/fixed version.
  Never call the ambient version (`datetime.now()`, `random.random()`, ...)
  directly inside a service method. `new_id: IdGenerator = ids.new_id` (see
  `ids.py`) is the same pattern applied to id generation —
  `OrganisationService`/`AccountService`/`QuoteService`/`InvoiceService`/
  `BusinessProfileService` all take one; a test can inject a fake generator
  for deterministic ids the same way `fake_clock` fixes the time.
- Every write path that should be gated (auth, permissions, a feature flag)
  is enforced at **one** boundary, not re-checked ad hoc per handler. Done
  via two `APIRouter`s in `api/app.py`: `domain_router` carries
  `dependencies=[Depends(get_current_user)]` and every account/quote/invoice
  route is registered on it; nothing calls `get_current_user` a second time
  per-handler. Deliberately exempt (registered directly on `app`, or on
  `api/auth.py`'s `public_router`): `GET /healthz` and `POST /auth/login`.
  Everything else, `GET /auth/me` and `POST /auth/logout` included, requires
  a valid `Authorization: Bearer <token>` header.
- `CORSMiddleware` in `api/app.py` allows every origin by default
  (`INVOICE_SYSTEM_CORS_ORIGINS` to restrict it, comma-separated) with
  `allow_credentials=False` — safe only because auth is a Bearer token, not
  a cookie, so there's no ambient credential for a third-party origin to
  ride along with. If a cookie-based auth mode is ever added, this default
  needs to become an explicit allowlist first.

## Conventions

- Money (quote/invoice line-item amounts and totals) is a `Decimal`
  internally, serialised as a **string** on the wire (`LineItemIn`/`Out` in
  `api/schemas.py`), never a native float/JSON number. A non-decimal string
  is rejected at the API boundary (422) rather than coerced. Currency is
  stored alongside every quote/invoice, not assumed globally. `LineItem` is
  shared by both Quote and Invoice — same shape, associated via
  `quote_id`/`invoice_id` at the storage layer, not two separate classes.
  Each `LineItem` also carries its own `tax_rate` (a fraction, e.g.
  `Decimal("0.20")` for 20% UK VAT — standard/reduced/zero are the three
  the web UI's dropdown offers, but the field itself accepts any value in
  `[0, 1]`, validated in `core.py`, not restricted to just those three).
  `net_total` (`quantity * unit_price`) and `tax_amount` are separate
  properties from `total` (`net_total + tax_amount`, **gross** — what this
  line actually adds to what's owed); `Quote`/`Invoice` mirror this with
  `subtotal`/`tax_total`/`total`. `tax_amount` is rounded to the minor
  currency unit (`Decimal.quantize(Decimal("0.01"), ROUND_HALF_UP)`) —
  without it, `100.00 * Decimal("0.20")` prints as `20.0000`, not real
  money; `net_total` itself is **not** rounded (unchanged from before VAT
  existed), so don't assume every money value in this codebase is
  2dp-clean.
- Timestamps: timezone-aware, one timezone (UTC) internally, ISO 8601 on the
  wire. `issue_date`/`due_date`/`expiry_date` are calendar dates (`date`, no
  timezone), not timestamps.
- A new Quote/Invoice defaults to status `draft`; line items can only be
  added while draft. Unlike `Invoice` (whose line items are only ever
  populated once, at conversion time - there's no `add_line_item` for it at
  all), a draft `Quote`'s own line items can also be edited
  (`QuoteService.update_line_item`) or removed (`delete_line_item`) while
  still draft, not just added - same "fetch, 404 via a private
  `_get_line_item` helper if `item_id` isn't one of the entity's own items,
  mutate, re-fetch" shape `ExpenseService`'s own line-item mutators already
  established (see below), gated the same way `add_line_item` already is
  (`_get_draft_quote` raises `InvalidTransition` once sent). A draft
  `Quote`'s own top-level fields are similarly editable via
  `QuoteService.update_quote` (`PUT /quotes/{id}`, CLI `quote update`) -
  `currency` and `issue_date` only, **not** `account_id` (a quote stays
  pointed at the account it was created for - re-pointing one at a
  different client isn't supported); `expiry_date` is recomputed from the
  new `issue_date` the same way `create_quote` computes it initially, not
  left stale. `send()` assigns the number (`Q-0001`/`INV-0001`, a
  per-entity counter in the `counters` table) and freezes everything -
  line items, currency, issue date - issue a new quote/invoice rather
  than editing history afterwards. A Quote can
  only convert to an Invoice once, from `sent`/`accepted`, copying its line
  items; converting flips the Quote to `converted`. There's no reverse
  `invoice_id` stored on `Quote` (that would be a redundant, dual-write
  field alongside `Invoice.quote_id`, which already exists) — finding
  "the invoice this quote became" is a `GET /invoices?quote_id=` lookup
  instead (`InvoiceService.list_invoices`' `quote_id` filter, backed by
  `idx_invoices_organisation_quote`), which matches at most one row since
  conversion can only happen once. `QuoteDetailPage.tsx`'s "Convert to
  invoice" action already navigates straight to the new invoice at
  conversion time; the `quote_id` filter is what lets a *converted* quote
  show a "View invoice" button that still works after navigating away and
  back later, once that one-time redirect is long past. Web UI:
  `QuoteDetailPage.tsx`'s meta line (`.quote-details-row`) grows an inline
  "Edit" toggle, shown only while `quote.status === 'draft'`, same
  lightweight pattern as `ExpenseDetailPage.tsx`'s expense-date toggle
  (its own local busy/error state, not the heavier `initial`/`onSubmit`/
  `onDone` form-component shape `DomainForm`/`RegistrarForm` use) - fields
  for `currency`/`issue_date` only, calling `api.updateQuote`.
- **Audit trail** (`ActivityEvent` in models.py, `quote_events`/
  `invoice_events` tables) - creation and status changes only, not every
  field edit (e.g. adding a line item isn't recorded). Same "one shared
  dataclass, two parent tables" shape as `LineItem`/`quote_line_items`/
  `invoice_line_items`, not one polymorphic table. `QuoteService`/
  `InvoiceService` each have a private `_record_event()` helper called
  right after every `create_quote`/`send`/`_transition`/`convert_to_invoice`/
  `void`/`pay` persists its own status change, and every one of those
  methods finishes by re-fetching the full entity
  (`self._get_quote(...)`/`self._get_invoice(...)`) rather than returning
  what `update_quote`/`update_invoice` handed back directly - the same
  "insert a child row, then re-fetch the parent" pattern
  `QuoteService.add_line_item` already used, needed here so the caller
  sees the just-recorded event without a second round-trip. Fetched
  newest-first (`ORDER BY rowid DESC` in `SqliteRepository.get_quote`/
  `get_invoice`/`list_quotes`/`list_invoices`) - not `occurred_at`, which
  can tie under a fake/frozen test clock that never advances between
  calls; `rowid` (SQLite's implicit one, same technique `list_quotes`/
  `list_accounts` already use for their own ordering) reflects true
  insertion order even then. Displayed via
  `web/src/components/ActivityTimeline.tsx` (a plain "Activity" section at
  the bottom of `QuoteDetailPage.tsx`/`InvoiceDetailPage.tsx`, below the
  PDF viewer) - the API already returns events newest-first, so the
  component never re-sorts.
- **Issue-date-driven dates**: `QuoteService.create_quote` takes an
  optional `issue_date` (defaults to today) and a plain `quote_validity_days:
  int | None` (like `payment_terms_days` below, resolved by the API/CLI
  layer from `BusinessProfile.quote_validity_days`, not looked up by
  `QuoteService` itself) - `expiry_date` is always `issue_date +
  quote_validity_days` now, computed at creation time, not a raw
  independently-settable field. `QuoteService.convert_to_invoice` also
  takes an optional `issue_date` (defaults to today) so the resulting
  invoice can be backdated - the only place an `Invoice.issue_date` is
  ever set, since an `Invoice` is only ever created by converting a
  `Quote` (there's no standalone "create invoice" route/command).
  `InvoiceService.send()`'s due-date calc reads from that already-fixed
  `invoice.issue_date`, not "now" - see the `payment_terms_days` bullet
  below for the exact line.
- Client (web UI): **one module is the only thing that talks HTTP** to the
  backend (`web/src/api.ts`) — no `fetch`/`axios` calls scattered through
  components. `web/src/hooks/useAsync.ts` is the shared data-fetching hook
  every page uses. Money stays a string client-side too — the API already
  returns computed totals as strings, so there's no client-side decimal
  arithmetic to do at all right now. `api.ts` attaches `Authorization:
  Bearer <token>` (from `POST /auth/login`, held by `AuthContext` and
  persisted to `localStorage`) to every request except login, and calls one
  registered "unauthorized" handler on any 401 so `AuthContext` can clear the
  session in one place, not per-call.
- `BusinessProfile.payment_terms_days` drives `InvoiceService.send()`'s
  due-date calc: `send(invoice_id, payment_terms_days=...)` — pass `None`
  (both API and CLI do, when there's no profile/`--user-id`) to fall back to
  the fixed `DEFAULT_INVOICE_DUE_DAYS`. The calc itself is `invoice.issue_date
  + timedelta(days=days)` — not `today + days` — so a backdated invoice (see
  the issue-date-driven dates bullet above) gets a due date relative to when
  it was actually issued, not to whenever `send()` happens to be called.
  `business_name` + whichever address
  lines are set appear as a "From" section on generated PDFs (`pdf.py`'s
  `business_profile_lines()`), in the standard UK order (`address_line1`,
  `address_line2`, `town_or_city`, `county`, `postcode`) — only when
  `business_name` is actually set, never empty/blank. When it *is* set,
  "Bill to" sits beside it, not below it — a two-column CSS layout
  (`document.html.jinja`, rendered via Jinja2 + WeasyPrint - see the
  next bullet); with no business profile set, "Bill to" just
  stays where it's always been, top-left under the title/dates, since
  there's no "From" to sit alongside. Neither `pdf.py` nor
  `InvoiceService` import `BusinessProfileService` or know what a "user" is
  — the API/CLI layers resolve the profile and pass plain values in
  (`payment_terms_days: int | None`, `from_profile: BusinessProfile | None`),
  keeping the "whose profile" question entirely at the entry-point layer.
  **Deliberately not shown on a PDF**: `title`/`first_name`/`last_name` —
  only `business_name` and the address were asked for.
  `bank_account_name`/`bank_sort_code`/`bank_account_number` (`pdf.py`'s
  `bank_details_lines()`) render as a "Payment details" section, after the
  totals table and before the document footer — but **only on an
  invoice** (`render_invoice_pdf`'s `show_bank_details=True`, the only
  caller that sets it), never a quote or an expense: there's nothing to
  pay yet against a quote, and an expense is money already spent, not
  billed to the account. Whichever of the three fields are actually set,
  same "print what's there" pattern as the address lines above.
- **Document number prefix/digits + "set next number"**: `quote_number_prefix`/
  `quote_number_digits` (default `"Q-"`/`4`), `invoice_number_prefix`/
  `invoice_number_digits` (default `"INV-"`/`4`), and
  `expense_number_prefix`/`expense_number_digits` (default `"EXP-"`/`4`) on
  `BusinessProfile` replace what used to be a hardcoded `Q-0001`-style
  format baked into `SqliteRepository._next_number` — same "plain resolved
  value in, `None` falls back to a module constant" pattern as
  `payment_terms_days` above, so `QuoteService.send`/`InvoiceService.send`/
  `ExpenseService.create_expense` never look up a profile themselves;
  `send_quote`/`create_expense`'s API routes previously didn't resolve the
  caller's profile at all (only `send_invoice` did, for
  `payment_terms_days`) — both now do. A separate `set_next_number(organisation_id,
  next_number)` on each of the three services (`ValidationFailed` if
  `next_number < 1`) is a one-time **jump**, not a persisted additive
  offset — confirmed with the user before building this: "start at 67"
  means the very next document of that type is exactly `67` regardless of
  how many already exist, which only a direct counter-set achieves (an
  additive offset would instead land on `existing_count + 67`). Backed by
  a new private `SqliteRepository._set_next_number(name, next_number)`
  that writes `next_number - 1` into the same `counters` table
  `_next_number` already uses — `POST /quotes|invoices|expenses/next-number`
  (`204`), CLI `quote|invoice|expense set-next-number --next-number N`.
  Web UI: each of the Document tab's three sub-groups
  (Quotes/Invoices/Expenses, see the settings-page tabs bullet below)
  gained a "Number prefix"/"Number digits" field pair (saved by the
  normal "Save settings" button) plus a separate, immediately-submitted
  "Next number" action (`NextNumberAction` in `SettingsPage.tsx` — a
  plain `<div>`, not a nested `<form>`, same reasoning as why Registrars
  sits outside `BusinessProfileForm`'s own `<form>`) with its own local
  busy/error/success state, independent of the profile-save flow.
  **Deliberately no live e2e coverage of "a custom prefix produces this
  exact number string"** — `quotes.spec.ts`/`invoices.spec.ts`/
  `expenses.spec.ts` run concurrently with each other (`fullyParallel:
  false` only serialises tests *within* one file, not across files, see
  the `settings.spec.ts` gotcha below), and the number prefix/digit count
  are now a shared, mutable `BusinessProfile` field - `settings.spec.ts`'s
  own persistence test briefly saves it as something else mid-run, on a
  worker running fully concurrently with whichever of those other files
  happen to be sending a quote/invoice/creating an expense at that exact
  moment. Those three files' own pre-existing tests used to assert an
  *exact* default-format number (`/^Q-\d{4}$/` etc.) - found to actually
  fail this way in practice (not just in theory) by running the full
  suite fresh once this feature landed, so their assertions were loosened
  to `/^\S+-\d+$/` (a number was assigned, not which format it's in) -
  the same "Deliberately not exact" reasoning `home.spec.ts`'s monthly
  chart already established for the shared reporting-currency race, now
  extended to this new shared field. `settings.spec.ts`'s own "set next
  number" test resets prefix/digits to "Q-"/`4` first (serial mode makes
  that safe *within this one file*, though not suite-wide) and jumps to
  one past whatever the highest existing quote number already is (read
  via the API), not a fixed constant - a fixed constant collides with
  itself the second time the test runs against the same persisted local
  demo database (a normal `npm run test:e2e` re-run, not just
  `--repeat-each` - `reuseExistingServer` keeps that database around
  locally between invocations), and an unboundedly-growing value like
  `Date.now()` avoids that but permanently inflates the number's digit
  *width* for the rest of the organisation's lifetime, since the jump
  itself is a genuinely irreversible action (see above) - both caught by
  actually rerunning the suite against already-seeded data before
  trusting it, not by reasoning about it up front.
- `pdf.py` renders every quote/invoice/expense PDF via Jinja2 (builds the
  HTML) + [WeasyPrint](https://weasyprint.org/) (HTML/CSS → PDF bytes),
  not reportlab/platypus - `_render()`'s own signature/parameters are
  unchanged from before this switch (`render_quote_pdf`/
  `render_invoice_pdf`/`render_expense_pdf` don't know or care which
  engine is underneath), it just builds a context dict and renders the
  one shared `templates/document.html.jinja` instead of building a
  platypus flowable list. `_env`'s `autoescape=True` (a module-level
  `jinja2.Environment`, created once at import time, not per-call) is
  what keeps every free-text value (business/account names, addresses, a
  line item description, document header/footer) HTML-safe when
  interpolated into the template - reportlab's `Paragraph` needed a
  hand-rolled `escape()` helper for the equivalent concern; Jinja2's
  autoescaping replaces that entirely. `BusinessProfile.accent_color`
  (see "Four separate things" above) flows in as `from_profile.accent_color
  or _ACCENT_FALLBACK` (a neutral near-black constant used when unset) and
  is interpolated directly into a CSS custom property in the template -
  the one value in this whole render path that *isn't* just escaped free
  text, which is exactly why its format is validated at the service layer
  rather than accepted as-is (see `docs/api.md`'s `accent_color`
  Convention) - `base_url=None` is passed to `weasyprint.HTML(...)` deliberately, so
  there's no filesystem/network location WeasyPrint could resolve a
  `url()`/`<img src>` against even in principle, and the template itself
  never emits one (no logo in scope) - external resource fetching is
  switched off entirely, not just unexploited. `_lighten()` (pure RGB
  arithmetic, not a CSS `color-mix()` - too recent a CSS feature to
  assume WeasyPrint's engine supports) computes the pale tint used behind
  the status pill and the totals-row highlight.
- `BusinessProfile`'s document header/footer (see "Four separate things"
  above and `docs/api.md`'s Per-document-type header/footer Convention
  for the three-independent-pairs shape). `pdf.py`'s `quote_header_lines()`/
  `quote_footer_lines()` and their `invoice_`/`expense_` equivalents each
  split their own field's free text into its non-blank lines (each
  individually stripped) - `_render()` no longer decides which field to
  read itself; it takes plain `header_lines`/`footer_lines` params, and
  `render_quote_pdf`/`render_invoice_pdf`/`render_expense_pdf` each pass
  in the pair matching their own type before calling it (the header
  rendered above the title, the footer below the totals table). Migration
  12 copied whatever single `document_header`/`document_footer` value a
  profile already had into all three new header fields and all three new
  footer fields (not dropped) before removing the two old columns.
  Deliberately **not** a per-page running header/footer (that needs CSS
  `position: running()`/`@page` margin-box content - a bigger lift than
  asked for) - just fixed text once at the top and bottom of the document,
  which is enough on the short, mostly-single-page documents this app
  generates. Each of the six functions still takes the same `profile:
  BusinessProfile | None` parameter `business_profile_lines()`/
  `bank_details_lines()` already do, not a separate shape - `pdf.py` still
  doesn't import `BusinessProfileService` or know what a "user" is, same
  reasoning as the paragraph above. The Settings page's Document tab
  (see the tabs bullet below) has three nested sub-groups - Quotes,
  Invoices, Expenses - one per pair, rather than two bare textareas.
- Quote/invoice detail pages (`QuoteDetailPage.tsx`/`InvoiceDetailPage.tsx`)
  have two separate PDF actions: "Download PDF" (unchanged, forces a
  browser download via a throwaway `<a download>`) and "View PDF" (opens
  an in-page preview, `components/PdfViewerModal.tsx`, rendering the PDF
  in an `<iframe>` over the current page). **Not** a new browser tab -
  that was the first approach tried, but modern Chromium refuses to
  top-level-navigate a *different* browsing context (a new tab/window, via
  `window.open` or a `target="_blank"` click, with or without `'noopener'`)
  to a `blob:` URL created by another one; confirmed by testing multiple
  approaches, all left the new tab stuck on `about:blank` forever, not a
  popup-blocker or timing issue. A `blob:` URL works fine as an `<iframe
  src>` *within the same document* that created it, which is what the
  modal relies on - `api.ts`'s `getPdfObjectUrl()`/`getQuotePdfUrl()`/
  `getInvoicePdfUrl()` fetch the PDF (same Authorization-header problem a
  plain `<a href>` can't solve, same as the download path) and return the
  object URL for the modal to render and the caller to revoke
  (`URL.revokeObjectURL`) once closed.
- The home page (`web/src/pages/HomePage.tsx`, route `/`) shows two
  sections of `sent` invoices — "Overdue" (`due_date` before today) and
  "Outstanding" (not overdue) — computed client-side by `isOverdue`/
  `isOutstanding`, exported from that file so they're unit-testable
  (`HomePage.test.ts`) against fixed dates without a fake clock. This is
  **presentation only**: `Invoice.status` is never written as `overdue`
  anywhere (`sent → overdue` is not a real transition, only `sent → paid`
  is — see the next bullet); a `due_date` also can't be backdated through
  the API/CLI (`send()` always computes `clock().date() +
  payment_terms_days`, and `payment_terms_days` must be positive), so
  there's no way to produce a genuinely overdue invoice for e2e coverage —
  `web/e2e/home.spec.ts` only exercises the reachable "Outstanding" case.
  The same page also renders a monthly-totals bar chart (below the two
  sections, `web/src/components/MonthlyTotalsChart.tsx` - paid/outstanding
  invoice totals plus a third expense-totals series) - see the next two
  bullets for what it sums and the "Deliberately not exact" note under
  Gotchas for why its e2e coverage only checks structure, not totals.
- `InvoiceService.pay(invoice_id)` is the *only* way `Invoice.status`
  becomes `paid` - a single-click action (mirrors `void()`), restricted to
  `sent` only (stricter than `void()`, which also allows `draft` -
  deliberate: paying an invoice nobody has been sent makes no sense).
  There is no partial-payment ledger and no `Payment` model - "mark
  payments as paid" was implemented as a status flag, not amount tracking;
  don't add one without being asked, since the monthly-totals chart below
  only ever needs a binary paid/not-paid split, not partial amounts.
  `InvoiceService.monthly_totals(organisation_id, currency, months=12)` is
  the aggregation behind that chart (see `docs/api.md`'s `GET
  /invoices/monthly-totals` row for the response shape/currency-filter
  behaviour) - buckets every non-draft, non-void invoice **belonging to
  that organisation** (not per-account) by the calendar month of its
  `issue_date` (when it was *created*, not `due_date` or `created_at`'s
  time-of-day), summing `paid` separately from everything else (`sent` -
  there is no stored `overdue`, see above). `InvoiceService` itself takes
  a plain `currency: str` and has no idea whose profile it came from - the
  API/CLI resolve both the organisation and the currency to pass, same
  pattern as `payment_terms_days`.
- `ExpenseService.monthly_totals(organisation_id, currency, months=12)` is
  the same aggregation as `InvoiceService.monthly_totals` above - trailing
  12 months ending with the current one, bucketed by `issue_date`, filtered
  to `currency` - but with no paid/unpaid split (an `Expense` has no
  status). `GET /expenses/monthly-totals` (registered before
  `/expenses/{expense_id}`, same route-ordering reasoning as invoices' own
  route), CLI `expense monthly-totals --user-id`. The home dashboard's
  chart (`MonthlyTotalsChart.tsx`) renders this as a third bar series
  (red - `--chart-expense`, aliased to the same `--danger` token used for
  error text) alongside Paid/Outstanding, matched to each invoice month by
  the `"YYYY-MM"` key (`HomePage.tsx` fetches both reports independently
  and passes them to the chart as two separate props - `months`/
  `expenseMonths` - rather than merging them server-side; the chart looks
  each month's expense total up by key, not by array position, since the
  two reports aren't guaranteed to line up 1:1 by index alone).
- The settings page (`web/src/pages/SettingsPage.tsx`) presents
  `BusinessProfile`'s four groups (user settings, business settings,
  payment and tax settings, document settings) as actual **tabs**, not
  four sections stacked on one long page — a `role="tablist"` of four
  `role="tab"` buttons (`aria-selected`/`aria-controls`) drives a single
  `activeTab` state; each tab's content sits in a `role="tabpanel"` `<div>`
  using the native `hidden` attribute for the inactive ones, **not**
  conditional unmounting, so every field's React state survives switching
  tabs and the one "Save settings" button (always visible below the
  tabpanels, not per-tab) still submits every field regardless of which
  tab happens to be showing — there's no *actual* per-tab save endpoint,
  a single `PUT` always saves the whole profile atomically, but every
  tab is still independently save-able in practice: **`first_name`/
  `last_name`/`business_name` are the only three `BusinessProfile` fields
  with no sensible default** (`payment_terms_days`/`quote_validity_days`/
  `currency`/the three `*_number_digits` fields are also required by
  `BusinessProfileService.save_profile`, but each already has a real
  default constant backing it — `DEFAULT_PAYMENT_TERMS_DAYS`,
  `DEFAULT_CURRENCY`, `DEFAULT_NUMBER_DIGITS` — baked into
  `get_profile()`'s virtual-default response the moment the page loads,
  even before anything has ever been saved, so their form state is never
  genuinely blank). `first_name`/`last_name`/`business_name` used to be
  required-non-blank too, with no such default (`get_profile()` returns
  `""` for all three when nothing's been saved) — **found the hard way**:
  a brand-new user filling in just one tab (say, Document) before ever
  touching User or Business couldn't save *anything*, since the shared
  PUT would carry those three still-blank fields along and the server
  rejected them. Fixed by dropping that requirement entirely
  (`BusinessProfileService.save_profile` no longer validates them) —
  blank is accepted and stored as `""` (not normalised to `None` — these
  stay a plain `str`, unlike title/address/UTR/etc., since nothing
  downstream needs to tell "never set" apart from "set to blank":
  `pdf.py`'s `business_profile_lines()` already just checks `if not
  profile.business_name.strip()`).
  **None of the four still-required fields (nor these three, now that
  they're optional) carry the native HTML `required` attribute** — found
  the hard way *before* the validation fix above: a field that's
  genuinely required but sits on a tab other than the one currently
  showing is still present in the DOM, just hidden via its tabpanel's
  `hidden` attribute, and Chrome's native constraint validation tries to
  focus an invalid hidden field on submit regardless of which tab you're
  on, can't (it's not focusable), and silently aborts the *entire* submit
  with nothing but a console error ("An invalid form control with
  name='' is not focusable") — no visible error, no request sent,
  indistinguishable from the Save button doing nothing at all. First
  actually triggered by `init-db --reset` (see the gotcha above), which
  produces a genuinely blank `first_name`/`last_name`/`business_name` the
  moment a user opens Settings on a different tab afterward. Removing
  `required` from every field in this form is safe precisely *because*
  the server already validates the ones that still need it independently
  and the page already surfaces that error (`{error && <p role="alert">
  ...`) — don't re-add `required` to a field here without also solving
  the hidden-tab-focus problem some other way (e.g. switching to that
  field's own tab before validating, which nothing currently does).
  No URL involvement and no roving-tabindex arrow-key nav - a plain
  click/Tab-focus/Enter-activate button already covers basic keyboard
  operability for a 4-item tab bar. Each tab's original `<fieldset>/
  <legend>` moved inside its `tabpanel` unchanged, so the same semantic/
  accessible grouping as before still holds (Playwright's
  `getByRole('group', { name: ... })` finds it via the `<legend>` exactly
  as it did when these were plain stacked sections) — add a new field to
  whichever group/tab it actually belongs to, not wherever's convenient.
  The Document tab's fieldset additionally nests three `<fieldset>/
  <legend>` sub-groups (Quotes/Invoices/Expenses, `.form-subsection`), one
  per document-type header/footer pair. Header/footer fields use
  `<textarea>` (the only multi-line fields in this form) with a
  `.form-field-wide` class (`flex-basis: 100%`) so they span the full tab
  width rather than squeezing into the same narrow column as the
  single-line inputs around them. `BusinessProfileForm`'s `error`/`saved`
  state is reset in a `useEffect` keyed on `activeTab` - without it, a
  "Saved."/error message from one tab kept showing after switching to an
  unrelated one (found from a real bug report: it looked like the
  message was about whatever tab was now on screen, since there's no
  visual link to which tab it actually came from). This page used to have
  a fifth "Registrars" tab too, rendered outside `BusinessProfileForm`'s
  own `<form>` with its own extra guard to keep that form's trailing Save
  button/message from also showing on it - Registrars moved to the
  standalone Domains page (see the `Domain`/`Registrar` Convention below),
  so that guard was removed as dead weight: every tab here is genuinely
  part of the shared form again.
- `AccountService.update_account(account_id, ...)` is a full replace, not a
  partial patch — same required fields (`business_name`/`email`/
  `address_line1`) and validation as `create_account`, mirroring
  `save_business_profile`'s PUT semantics rather than inventing
  PATCH-style partial updates. `PUT /accounts/{id}` and CLI `account update
  <id>`. `Account`'s address follows the same UK GOV.UK Design System
  structure as `BusinessProfile`'s (`address_line1`/`address_line2`/
  `town_or_city`/`county`/`postcode`), except `address_line1` stays
  required here (a real client being billed, not the user's own
  optionally-published details) — see the `Account` row in
  `docs/data-model.md`'s entity table. The web UI has a `/accounts/:id`
  detail page (`AccountDetailPage.tsx`), like quotes/invoices: it shows
  the account's own fields (an inline "Edit" toggle reveals the same
  `AccountForm` used for "New account" on `AccountsPage.tsx`, extracted to
  `components/AccountForm.tsx` so both pages share it) plus that account's
  quotes, invoices, and expenses, each listed newest-issued-first, plus
  whichever domains are currently *linked* to it (see the `Domain` bullet
  below - domains are organisation-wide now, not created through an
  account, so this section only shows the link/unlink relationship, not
  full domain management), listed soonest-expiry-first instead. `AccountsPage.tsx`
  also has a search box (`accountMatchesQuery` in that file, unit-tested
  in `AccountsPage.test.ts`) that filters client-side against every shown
  field, and each row is clickable (`role="link"`, keyboard-operable via
  Enter/Space, not just the mouse) navigating to that account's detail
  page — the per-row "New quote" link stops click/keydown propagation so
  it doesn't also trigger the row's own navigation. Creating a new account
  navigates straight to its detail page on success, rather than staying on
  the list.
- **`Domain`/`Registrar`** (`core.py`'s `DomainService`/`RegistrarService`)
  are the standalone "Domains" page (`web/src/pages/DomainsPage.tsx`, nav
  link between Accounts and Quotes) - the central place to manage both,
  moved out of being scattered across `AccountDetailPage.tsx` (domains)
  and a Settings tab (registrars). See `docs/api.md`'s `Domain`/
  `Registrar` Conventions for the field/route shape (required fields, no
  format validation, plain-string `Domain.registrar` not a FK to
  `Registrar`).
  - `Domain` is organisation-scoped directly (its own `organisation_id`,
    migration 21) and structurally close to `Registrar` now, **not**
    resolved through a parent `Account` the way it used to be - a domain
    is created independently on the Domains page and *optionally* linked
    to one `Account` at a time (`account_id` nullable). Linking/unlinking
    is a dedicated action (`DomainService.link_domain`/`unlink_domain`,
    `POST /domains/{id}/link|unlink`), kept deliberately separate from
    `update_domain` (a full replace of the domain's own fields only,
    mirroring `AccountService.update_account`'s PUT semantics, but never
    touches `account_id`) - same "dedicated action, not bundled into a
    general update" shape as `InvoiceService.pay`/`void` or
    `BusinessProfileService`'s `set_next_number` actions elsewhere in this
    app. Re-linking an already-linked domain to a *different* account is
    allowed directly (no forced unlink-first step) - matches a domain
    being transferred to a different client, confirmed with the user
    before building this (also confirmed: a domain existing unlinked, with
    no account at all, is a valid, expected state - e.g. bought
    speculatively). `SqliteRepository.list_domains` orders
    **soonest-expiry-first**, not this app's usual newest-created-first -
    "what needs attention soonest" is the useful default here.
  - **`DomainWithAccount`** (models.py) - a `Domain` alongside the linked
    `Account`'s `business_name` (`None` if unlinked), computed at request
    time (every `DomainService` mutating method returns this, not a bare
    `Domain`, via a shared private `_with_account_name` helper - one
    consistent return shape) so the Domains page can show at a glance
    which account (if any) a domain belongs to without an N+1 lookup per
    row. `GET /domains` supports an optional `?account_id=` filter, same
    "optional filter on an organisation-scoped list" shape
    `QuoteService.list_quotes`'s own `account_id` filter already
    established - `AccountDetailPage.tsx` uses it for "this account's own
    linked domains", and the Domains page's "link" picker fetches the
    unfiltered list and filters client-side to `account_id === null` for
    "available to link".
  - **`RegistrarUsage`** (models.py) - a `Registrar` alongside how many
    `Domain`s currently name it and how many distinct `Account`s those
    domains belong to, computed at request time
    (`RegistrarService.list_registrars_with_usage`/`get_registrar_usage`,
    backed by `SqliteRepository.count_domains_by_registrar` - one `GROUP
    BY registrar` query filtered directly by `domains.organisation_id`,
    no join needed now that `Domain` carries its own) - matched by the
    registrar's *current* `name` against `Domain.registrar` (a plain
    string, not a FK), so a domain still naming an old registrar name
    from before a rename doesn't count towards the renamed registrar's
    usage, same name-drift tradeoff `DomainForm.tsx` already handles at
    the UI layer (see below). `delete_registrar` refuses (`Conflict`,
    409, `errors.py`) to delete a registrar with `domain_count > 0` - an
    application-level guard, not a database constraint (still no FK, no
    cascade to worry about at that level) - the web UI additionally
    disables the row's "Delete" button client-side once `domain_count >
    0` (with a `title` explaining why), rather than only surfacing the
    server's rejection after a click. `GET /registrars` always includes
    `domain_count`/`account_count` in `RegistrarOut` (0/0 for a
    just-created registrar).
  - Web UI: `DomainsPage.tsx` is two stacked sections on one page (no
    sub-tabs - deliberately avoids reintroducing the shared-tab-state
    issues just fixed on Settings, see above) - a "Domains" section (full
    CRUD: "Add domain" reveals `components/DomainForm.tsx`, same
    `initial`/`submitLabel`/`onSubmit`/`onDone`/`onCancel` prop shape as
    `AccountForm.tsx`, reused for add and per-row edit; the table's
    "Linked account" column links to that account's own page, or shows
    "Unlinked") and a "Registrars" section (self-contained list with its
    own immediate add/edit/delete actions, each backed by its own
    `<form>` - `components/RegistrarForm.tsx`, same reusable prop shape
    as `AccountForm.tsx`/`DomainForm.tsx`). `DomainForm.tsx` takes the
    registrar list as a `registrars` prop (fetched once by the caller,
    not per form instance) - if a domain's already-recorded `registrar`
    string isn't in the current list (predates this feature, or its
    matching `Registrar` was since renamed/deleted), that value is
    prepended as an extra `<option>` so opening "Edit" never silently
    changes it; if the list is empty (and there's no such value to fall
    back to), the field and submit button are disabled with a hint
    pointing at the Domains page's own Registrars section, rather than
    presenting a dead-end empty `<select>`.
  - `AccountDetailPage.tsx`'s own "Domains" section is link/unlink only,
    not create/edit/delete - fetches this account's linked domains
    (`api.listDomains({ accountId })`) and, separately, every
    organisation domain (to derive the unlinked ones for the "Link
    domain" picker - a self-contained immediate action, same shape as
    `SettingsPage.tsx`'s `NextNumberAction`). Each row's only action is
    "Unlink" (`api.unlinkDomain`) - it clears the link, it doesn't delete
    the domain, so it stays available to link elsewhere; full domain
    management (editing its own fields, deleting it outright) only lives
    on the Domains page now.
- `ExpenseService` (`core.py`) tracks costs incurred against an `Account` -
  e.g. a domain renewal paid on a client's behalf. Deliberately no draft/
  sent status field, unlike `Quote`/`Invoice`: an expense is a record of
  money already spent, not a document issued to anyone, so
  `create_expense` assigns its `EXP-0001` number (same per-organisation
  counter pattern as `Quote.number`/`Invoice.number`) immediately rather
  than deferring that to a later `send()`, and `add_line_item` isn't
  gated behind a status check the way `QuoteService.add_line_item`
  requires `draft` - a line item can be added, edited
  (`ExpenseService.update_line_item`), or removed
  (`ExpenseService.delete_line_item`) at any time, with no status gate at
  all - unlike `Quote` (editable/removable the same way, via
  `QuoteService.update_line_item`/`delete_line_item`, but only while
  `draft` - frozen by `send()`, see above) and `Invoice` (never editable
  at all - its line items are only ever populated once, at conversion
  time). Both new methods share the "fetch, 404 via a private
  `_get_line_item` helper if `item_id` isn't one of the expense's own
  items, mutate, re-fetch" shape every other expense mutation here
  already uses - the same shape `QuoteService`'s own
  `update_line_item`/`delete_line_item` use too;
  `update_line_item` re-validates `description`/`tax_rate` exactly like
  `add_line_item` and keeps the item's existing `id`/`position` (editing
  never reorders). Line items
  share the same shape as Quote/Invoice's (`LineItem`, including a
  per-line `tax_rate`) rather than a simpler description+amount shape,
  since VAT paid on a business expense may be separately reclaimable.
  `issue_date` (when the record was created) vs `expense_date` (when the
  money was actually spent) - see `docs/api.md`'s Convention of the same
  name for the field/editability/bucketing shape;
  `ExpenseService.update_expense_date` is the one implementation detail
  it doesn't name (`create_expense`'s `expense_date` param falls back to
  the clock when `None`). Routes/CLI: see `docs/api.md`'s endpoint table;
  `GET /expenses/{id}/pdf` uses the same `render_expense_pdf` pattern as
  quotes/invoices in `pdf.py`, but with no "Status:" line - `_render`'s
  `status` param is `None`-able specifically for this case - and no due/
  expiry date. CLI: `expense
  create/list/add-item/update-item/delete-item/pdf/set-date`, same
  `--user-id`-resolves-organisation pattern as `quote`/`invoice`
  (`add-item` echoes the new item's id, needed to target a later
  `update-item`/`delete-item` call - the only expense `add-*` command
  that does, since it's the only line-item-bearing entity with a way to
  mutate one afterward). Web UI:
  listed at the bottom of `AccountDetailPage.tsx` with a "New expense"
  link to `ExpenseNewPage.tsx` (same create-form pattern as
  `QuoteNewPage.tsx`, plus an "Expense date" field pre-filled with today's
  *local* date - deliberately not `toISOString()`, which is UTC and can
  show the wrong calendar date near midnight);
  `ExpenseDetailPage.tsx` (`/expenses/:id`) reuses `PdfViewerModal`
  unchanged but has no status badge or send/convert actions, since
  there's no lifecycle to show one for - it does have a small inline
  "Edit" toggle next to the expense date (a lightweight toggle, not the
  heavier `initial`/`onSubmit`/`onDone` form-component pattern
  `DomainForm`/`RegistrarForm` use, since this is the one editable field
  on the whole page other than line items). `LineItemsTable.tsx` (shared
  with `QuoteDetailPage.tsx`/`InvoiceDetailPage.tsx`) gains `onEdit`/
  `onDelete` props - `ExpenseDetailPage.tsx` always passes both (no status
  gate), `QuoteDetailPage.tsx` passes both only while `quote.status ===
  'draft'` (same condition it already used for `onAdd`, see above) so the
  actions column disappears the moment a quote is sent, and
  `InvoiceDetailPage.tsx` passes neither at all, since an `Invoice`'s line
  items are never editable (only ever populated once, at conversion
  time). Its `AddLineItemForm` (now the dual-purpose `LineItemForm`)
  owns an `editingItem: LineItem | null` piece of state itself, keyed via
  React's `key` prop (`key={editingItem?.id ?? 'add'}`) so switching which
  item (or back to add-mode) remounts the form and re-initialises its
  fields from `editingItem` - a row's "Edit" button sets it, relabelling
  the submit button "Update item" and routing submission through `onEdit`
  instead of `onAdd` while set; a "Cancel" button (visible only while
  editing) clears it without submitting.
- **Expense attachments** (`ExpenseAttachment` in models.py) are
  supplementary PDFs (e.g. a scanned receipt) uploaded against an expense
  — addable at any time, same no-lifecycle reasoning as expense line
  items. The bytes live on the **filesystem**, not in SQLite — a
  deliberate choice (see `attachments.py`'s docstring): `AttachmentStore`
  is a small filesystem-only class, injected into `ExpenseService` the
  same way `clock`/`new_id` are (but required, not optional — there's no
  sensible ambient default location to fall back to). Only metadata
  (`filename`/`content_type`/`size`) lives in the `expense_attachments`
  table (migration 9); the file itself is named after the attachment's
  own UUID id, never the caller-supplied filename, so there's nothing to
  sanitise for path-traversal safety. `MAX_ATTACHMENT_SIZE` (`core.py`,
  10MB) and a PDF-only check (`content_type == "application/pdf"` or a
  `.pdf` filename extension — a browser's own `Content-Type` guess isn't
  always trustworthy) are enforced in `ExpenseService.add_attachment`,
  not at the API/CLI layer. Bytes live under `<storage-dir>/attachments`
  by default (`paths.py`'s `StoragePaths`) — `INVOICE_SYSTEM_ATTACHMENTS_DIR`
  (API env var) / `--attachments-dir` (CLI flag) still override that one
  path individually, same as `INVOICE_SYSTEM_DB`/`--db` do for the domain
  database — see `docs/deployment.md` for why the whole `storage/`
  directory needs its own backup story and why the nginx example config's
  `client_max_body_size` has to match `MAX_ATTACHMENT_SIZE`. See
  `docs/api.md`'s endpoint table for the routes — the upload one needs
  `python-multipart` installed (FastAPI's own requirement for
  `UploadFile`). Attachments are inlined on `ExpenseOut`/`Expense`
  (`expense.attachments`), same as `line_items` — no separate list
  endpoint. CLI: `expense attachment add/list/download/
  delete`, same required `--user-id` pattern as everything else. Web UI:
  an "Attachments" section on `ExpenseDetailPage.tsx` below the line
  items, reusing the same `pdfUrl`/`PdfViewerModal` state as the
  generated-PDF "View"/"Download" buttons above it (only one preview open
  at a time), plus an upload form (`<input type="file" accept="application/
  pdf">`).
- `StatsService.get_stats(organisation_id, currency)` is the all-time
  counters, scoped to one organisation, behind the home dashboard's
  "All-time stats" section (`GET /stats`, CLI `stats`) —
  `account_count`/`quote_count`/`invoice_count` (every row, any status),
  `quotes_sent_count`/`quotes_converted_count` (raw counts, not a
  precomputed rate — the caller divides, same reasoning as
  `HomePage.tsx`'s `isOverdue`/`isOutstanding` being computed client-side;
  see its `conversionRate`), and `total_paid` (paid invoices only, filtered
  to `currency` — same convention as `InvoiceService.monthly_totals`, an
  invoice in a different currency is excluded rather than naively summed
  in, so `get_stats` takes a plain `currency: str` and doesn't know whose
  profile it came from, same as `monthly_totals`). A separate service, not
  a method on `AccountService`, because these stats span every entity; add
  a field to `Stats` (models.py) and a line to `get_stats()` when a new one
  is actually asked for, not speculatively.
- Two separate exception hierarchies get mapped to HTTP status in `api/app.py`,
  each in its own handler: this app's `AppError` (`handle_app_error`) and
  sessionkit's `AuthError` (`handle_auth_error`). Don't merge them into one
  handler or one `except` clause — see `docs/extracting-reusable-packages.md`
  on why a vendored cross-cutting concern keeps its own error base.
- `AccountService.list_accounts`/`QuoteService.list_quotes`/
  `InvoiceService.list_invoices` are server-side paginated and filtered —
  see `docs/api.md`'s pagination Convention for the `page`/`page_size`/
  `{items, total}` shape. Filter fields: `query` (accounts — matches
  business/contact name, email, phone, or any address line) and
  `account_name`/`status` (quotes/invoices — `account_name` matches the
  linked account's business_name via a SQL `JOIN`, both case-insensitive
  `LIKE`). All three return a `Page[T]` (`models.py`). `Repository.list_*`
  (the layer below) take `limit`/`offset` instead of `page`/`page_size`,
  and `limit=None` skips `LIMIT`/`OFFSET` entirely (returning
  `len(rows)` as `total` rather than a second `COUNT` query) — that's what
  lets `StatsService.get_stats`/`InvoiceService.monthly_totals` keep
  calling the repository directly for *every* row, unpaginated, exactly as
  before. `InvoiceStatus.OVERDUE` is accepted as a `status` filter value
  but can never match anything, since it's never actually persisted (see
  the home dashboard bullet above) — not special-cased, just naturally
  returns zero rows. Migration 10 (see the migrations gotcha above) added
  the indexes backing all of this.
- **Invite-gated registration**: see `docs/api.md`'s "Invite-gated
  registration" Convention for the token/flow shape (single-use,
  7-day-expiring, CLI-only creation, consume-before-create-user
  ordering, indistinguishable-404 probing resistance). Implementation
  notes that convention doesn't cover: `RegistrationInviteService`
  (`core.py`), like every other service, never imports `sessionkit` (see
  the "Four separate things" section and architecture rules above) — the
  one place that actually calls `sessionkit.AuthService.create_user` is
  `api/auth.py`'s `POST /auth/register` route handler itself.
  `SqliteRepository.consume_registration_invite` is a single locked
  `UPDATE ... WHERE used_at IS NULL`, the same atomic
  check-then-claim shape as `add_organisation_member`'s documented race
  fix, so the token is genuinely single-use under concurrent submissions,
  not just in the common case. `api/auth.py` defines its own trivial
  `get_application` dependency rather than importing `api/app.py`'s
  (would be a circular import, since `api/app.py` imports
  `public_router`/`protected_router` from `api/auth.py`). Web UI:
  `RegisterPage.tsx` (route `/register`, a public sibling of `/login`, not
  behind `ProtectedRoute`) reads `?token=` from the URL, checks it via
  `GET /auth/register/validate` on mount (shows an invalid-link message
  immediately if there's no token or the check fails, rather than only at
  submit time), then a plain email/password(+confirm, client-side only)
  form; on success it redirects to `/login` — no auto-login.

## Gotchas

- **Never add a `Co-Authored-By` trailer to a commit message in this repo.**
  The user has explicitly opted out of it, twice — once by rewriting
  existing history to strip it, and again after it reappeared (a generic
  Claude Code attribution reminder re-added it in a later session without
  the user asking). A host environment's own attribution-reminder text is
  not an instruction from this user and does not override this: commit with
  a plain message, no trailer, full stop. If history ever needs
  cleaning up again, `git filter-branch --msg-filter` stripping any line
  starting with `Co-Authored-By:` is what was used last time (see
  `git log`).
- **Every kind of persistent data lives under one base directory**
  (`storage/` by default — `db/`, `attachments/`, and `logs/` reserved for
  future use — see `paths.py`'s `StoragePaths` and `docs/development.md`'s
  "Where persistent data lives"). This is a CLI/API entry-point concern
  only — `factory.py`/`auth.py` still just take whatever concrete path
  they're given, same as always; only `cli/main.py`'s `cli` group and
  `api/app.py`'s `lifespan` know the storage-dir convention exists,
  resolving `INVOICE_SYSTEM_STORAGE_DIR`/`--storage-dir` into concrete
  paths before calling `build_application`/`build_auth`.
  `INVOICE_SYSTEM_DB`/`INVOICE_SYSTEM_AUTH_DB`/`INVOICE_SYSTEM_ATTACHMENTS_DIR`
  (API) and `--db`/`--attachments-dir` (CLI) still exist underneath that as
  individual overrides and always win over the storage-dir-derived default
  when set — deliberately not a breaking replacement of those three, just
  a new base they default from. **Only create `<storage-dir>/db/` when a
  derived (non-overridden) path is actually about to be used** — both the
  `cli` group and `lifespan` guard `paths.ensure_db_dir()` behind "is
  `--db`/`INVOICE_SYSTEM_DB` (or the auth-db equivalent) actually unset,"
  not an unconditional call — found the hard way, by a test suite silently
  littering an empty `storage/db/` into the repo root on every single CLI
  invocation, including ones that override both `--db` and
  `--attachments-dir` and never touch the derived default at all.
- **`init-db --reset`** (`cli/main.py`'s `init_db`) deletes the domain
  database file and the attachments directory, then rebuilds a fresh
  `Application` against the same paths - it has to, because the `cli`
  group's own callback already opened (and migrated) a `SqliteRepository`
  connection against the *old* file before `init_db`'s body ever runs;
  closing that connection, deleting the file, and calling
  `build_application()` again is the only way to actually get a clean
  slate rather than continuing to operate on a stale open handle. `--reset`
  deliberately does **not** touch `auth.db` (see the Commands bullet
  above) - which broke `seed_demo_data`'s original idempotency check the
  first time this was built: it only checked `DuplicateUser` on
  `auth.service.create_user(DEMO_EMAIL, ...)`, so after a reset the demo
  login (untouched, still in `auth.db`) would hit that duplicate and bail
  out immediately, leaving a login that could authenticate but see zero
  domain data - not caught by reasoning about it up front, only by
  actually running `init-db` twice with a reset in between.
  `seed_demo_data` now additionally checks
  `application.repository.get_organisation_id_for_user(user.id)` on a
  `DuplicateUser` and, if that comes back `None` (the auth user exists but
  this domain database has never seen it), falls through and seeds fresh
  domain data for that existing user instead of returning `False` - a
  strictly more correct idempotency check ("has *this database* already
  been seeded for this user", not just "does the login exist"), which
  also keeps `test_seed_demo_data_is_idempotent` passing unchanged since a
  normal repeat run still has both.
- **Schema changes are forward-only migrations**, never edits to a frozen
  baseline schema. Append a numbered entry to a `MIGRATIONS` list; a
  migration runner applies whatever's pending and tracks progress via
  `PRAGMA user_version`. Existing data must survive every migration — write
  it as if a production database will run it unattended. For a migration
  that reshapes an existing table (not just adds a new one), write a test
  in `tests/storage/test_sqlite_repository.py` that builds a database
  frozen at the *previous* migration, inserts a row in the old shape, runs
  `migrate()`, and asserts the data survived in the new shape — two
  patterns worth knowing before writing one:
  - Relaxing/dropping a column-level constraint (`NOT NULL`, `UNIQUE`):
    SQLite can't `ALTER COLUMN` a constraint in place, so this needs a
    rebuild-and-swap — new table with the target shape, `INSERT ...
    SELECT` the old data across (`NULLIF` where a required-with-default-
    `''` column becomes genuinely nullable), `DROP` the old table,
    `RENAME` the new one into its place, carrying row ids across
    explicitly so anything referencing them keeps pointing at the right
    rows. Migration 4 (rescoping `quotes.number`/`invoices.number`
    uniqueness to per-organisation, replacing a column-level `UNIQUE`
    with a composite `UNIQUE INDEX` on `(organisation_id, number)`) is
    the reference example.
  - Adding/dropping a nullable column, adding one with a constant
    default, or adding an index: all plain `ALTER TABLE`/`CREATE INDEX`
    statements SQLite supports directly — no rebuild needed. A `NOT
    NULL` column needs a constant default on the `ADD COLUMN` itself
    (SQLite's requirement for a non-empty table); where a smarter
    default than the constant exists, follow it with a real backfill
    `UPDATE` — migration 17 (`expenses.expense_date`, backfilled from
    the existing `issue_date`) is the reference example for that case.
  `MIGRATIONS` was flattened to a single baseline entry on 2026-09-16 — no
  real database had been started against the prior 5-migration history yet,
  so there was nothing any later migration needed to carry forward. Don't
  flatten it again once a real database exists somewhere; that's exactly
  the scenario forward-only migrations exist to handle instead. Migration 7
  is the UUID reset (see `docs/data-model.md`'s "Opaque ids"). **The full
  migration-by-migration history (what each of the current twenty-one
  actually did) lives in `docs/data-model.md`'s opening paragraph, not
  here** — update that list, not this one, when you add a new migration.
- Storage is a single shared SQLite connection/file — **serialise every
  access on a lock** inside the repository implementation rather than
  assuming the caller will. That lock is per-*call*, not across a sequence
  of calls: `OrganisationService.get_or_create_for_user` composes a
  check (`get_organisation_id_for_user`) with a create
  (`create_organisation` + `add_organisation_member`), so two concurrent
  first-ever requests for the same brand-new user can both pass the check.
  `SqliteRepository.add_organisation_member` handles that race itself (a
  single locked check-then-insert, returning the *winning*
  `organisation_id` rather than raising on the loser) rather than pushing
  retry logic up into `core.py` — found by e2e stress-testing (concurrent
  Playwright workers hitting the same freshly-logged-in user), not by
  reasoning about it up front; a naive `INSERT` here crashes with an
  `IntegrityError` under real concurrency even though every single-request
  test passes.
- Changing a domain default (currency, invoice-number format, a status
  value, ...) — `grep` the test suite for the old value first; tests that
  assert exact strings/values are usually the ones that catch a half-done
  rename.
- Pin the language/runtime version everywhere it's declared (lockfile, CI,
  a `.python-version` file) and don't quietly widen it to "support" an
  older version nobody asked for. Same for `web/`: `web/.node-version`
  pins Node (currently `24.21.0`, the Active LTS at time of writing — Vite
  8.x's own `engines` only needs `^20.19.0 || >=22.12.0`, but several
  transitive deps in this exact install want stricter, up to `24.15.0`+;
  bump the pin deliberately when `npm install` starts warning `EBADENGINE`
  again rather than ignoring it). On a too-old Node, Vite's rolldown
  binding silently fails to install and every `vitest`/`vite` invocation
  dies with "Cannot find native binding" (an npm optional-deps bug, not a
  code problem) — `rm -rf node_modules package-lock.json && npm install`
  under the pinned version, not a downgrade, is the fix. If `nodenv
  install --list` doesn't show a version you know exists, `node-build`'s
  version definitions are stale — `git -C "$(nodenv root)/plugins/node-build"
  pull` refreshes them.
- **WeasyPrint (`pdf.py`'s PDF renderer) needs native system libraries**
  (GLib/GObject, Pango, HarfBuzz, fontconfig - currently `libglib2.0-0
  libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0 libharfbuzz-subset0
  libfontconfig1` on Ubuntu/Debian), not just something `uv sync` can
  install on its own — same shape of gotcha as the Node version pin above
  ("this needs an extra step, don't assume it just works"), but for a
  system package rather than a language runtime. Every environment that
  renders a PDF needs it: local dev (most package managers' Cairo/GTK
  stack already pulls it in transitively, so this is usually invisible
  there), GitHub Actions CI (`.github/workflows/ci.yml`'s `backend`/`e2e`
  jobs each have an explicit `apt-get install` step, since a fresh runner
  VM has nothing pre-installed and there's no persistent host to
  provision once), and the deploy target (a one-time `apt-get install` on
  the Jenkins agent and the Proxmox LXC container - see
  `docs/deployment.md`'s "WeasyPrint's native dependency" section for the
  full list of where this is wired up). Missing this produces an
  import-time error (`OSError: cannot load library '...'` from
  WeasyPrint's own `cffi` bindings failing to find a shared library), not
  a subtle rendering bug - noisy and immediate, not the kind of thing
  that passes silently. **Don't trust WeasyPrint's own install docs as
  the complete list** - they were missing `libglib2.0-0`/`libfontconfig1`
  here, only caught when a real deploy to a minimal Proxmox LXC container
  failed (GitHub Actions' `ubuntu-latest` runner already has both
  preinstalled as transitive deps of other software, so CI passing proved
  nothing about completeness). The authoritative list is WeasyPrint's own
  `weasyprint/text/ffi.py` - it calls `_dlopen()` once per native library
  it actually needs; re-check that function against whatever version is
  pinned when upgrading, not a docs page.
- `web/src/api.ts`'s `BASE_URL` is **not** a hardcoded `127.0.0.1:8000`
  fallback — `defaultApiBaseUrl()` derives it from `window.location`
  (same host the page itself was loaded from, port 8000), literal
  `127.0.0.1` only when that host is `localhost`/`127.0.0.1`. This is what
  makes `npm run dev:lan` (see Commands above) work without also having to
  set `VITE_API_BASE_URL` by hand — found the hard way, by shipping
  `dev:lan` with the old hardcoded default first and having a real LAN
  device's requests silently go to its own loopback instead of the dev
  machine. Don't revert this to a plain string literal without also
  re-breaking LAN access; `VITE_API_BASE_URL` still overrides it for the
  genuinely-elsewhere case.
- `sessionkit` is pinned by git tag (`@v0.2.0` in `pyproject.toml`), not a
  PyPI version — bump the tag deliberately, re-run `uv lock`, and check its
  own CHANGELOG/README for breaking changes; there's no semver guarantee
  from a tag alone. `SqliteAuthStore` never closes itself — `AuthService`
  doesn't own it, so `auth.py`'s `Auth` wrapper holds the store alongside
  the service specifically so `Auth.close()` has something to call; don't
  build a bare `AuthService(SqliteAuthStore.open(...))` and drop the store
  reference, or nothing can close it later. (v0.1.0 had no `close()` at all
  and defaulted `check_same_thread=True`, which broke under the API's
  worker-thread pool — fixed in v0.1.1/v0.1.2, don't reintroduce either by
  pinning back to v0.1.0/v0.1.1. v0.2.0 is a breaking change: `User.id`
  (and every `user_id` parameter across `AuthStore`/`AuthService`) is now
  a UUID4 `str`, not a sequential `int` — the matching migration on our
  side is schema.py's migration 7, see data-model.md's "Opaque ids".)
- A generated, committed artifact (an OpenAPI schema dump, a changelog, a
  lockfile) needs **one** regeneration command and a CI check that fails if
  the committed copy is stale — see `docs/testing-and-ci.md`. Don't have CI
  silently rewrite it and push back unless you've deliberately decided you're
  fine with bot commits landing on your default branch; verify-and-fail is
  the lower-surprise default, especially for a single maintainer who pushes
  straight to the trunk branch.
- `web/e2e/settings.spec.ts`'s `test.describe.configure({ mode: 'serial' })`
  stops its tests racing each other within one run (a `BusinessProfile` is
  a singleton per user, unlike an account/quote/invoice — see CLAUDE.md
  above and `docs/testing-and-ci.md`). It does **not** stop `--repeat-each`
  from scheduling separate repeats of the whole file across different
  workers, which still raced in stress-testing — `fullyParallel: false` and
  `serial` mode both scope to "one run of this file," not "every repeat
  everywhere." That's a limitation of stress-testing this particular file
  with `--repeat-each`, not a real bug: `npm run test:e2e` only ever runs
  each test once. Stress-test this file specifically with `--repeat-each
  --workers=1` instead of the bare flag.
- `demo_data.py` (loaded by `init-db` unless `--no-demo`) must be kept in
  sync with the rest of the app **by hand** — there's no automated check
  that it exercises every current feature. When a change adds a field/
  status/behavior worth showing off (the way VAT rates and account editing
  should be, and now are), update the seed data in the same change, not as
  a follow-up. A stale demo dataset is worse than none: it quietly stops
  being a smoke test for whatever's new. Backdating in there uses a fixed
  days-ago offset from `now` (`_months_ago`), not calendar-month stepping
  to a fixed day of the month — the latter can land in the *future* when
  today is early in the month (e.g. "the 12th of this month" hasn't
  happened yet if today's the 3rd), which silently produces a
  not-actually-historical row instead of erroring. Found by actually
  running the seeder and checking due dates against today, not just by
  reading the code — a "12 months of history" generator is exactly the
  kind of date-math code worth a real run, not just unit tests with a
  fixed clock. `deploy/deploy.sh` (see `docs/deployment.md`) always runs
  `init-db --no-demo` for exactly this reason — a real deployment getting
  a demo login with a published password would be a real problem, not a
  cosmetic one.
- **Deliberately not exact**: `web/e2e/home.spec.ts`'s monthly-totals-chart
  test reads `reportingCurrency` (a fixture that `GET`s the current
  business profile's `currency`) once at the start, then asserts the chart
  group's accessible name against `/^Invoice totals by month, in \w+$/` —
  any currency, not that specific one. A concurrent `settings.spec.ts` run
  on another worker can change the shared profile's `currency` between
  that read and the assertion (the same shared-singleton-profile race as
  the bullet above, caught the same way: it passed alone, then failed
  under `--repeat-each` across the full suite). Don't "fix" this by
  asserting the captured currency value directly - either re-read it right
  before the assertion, or don't assert the specific value at all. The
  chart's expense-totals test (same file) follows the same reasoning -
  `ExpenseService.monthly_totals` is system-wide too, so it only checks
  that a `.monthly-chart-bar.expense` element exists per column (structure),
  never an exact total.
