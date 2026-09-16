# CLAUDE.md

Invoice System: a freelancer/small-business billing tool. Domain shape is
Account (the business you provide a service to — business name, contact,
address; editable after creation) → Quote → Invoice, where a Quote converts
into an Invoice rather than the two being independently created. Each line
item can carry its own UK VAT rate. Quotes and Invoices are each
independently viewable/exportable as PDFs, and a sent invoice can be marked
`paid` (a single status flag, not a payment ledger). A `BusinessProfile`
holds the logged-in user's *own* business details (name/address/payment
terms/reporting currency/UTR/VAT) — see below for why that's a third,
deliberately separate thing from both `Account` and sessionkit's `User`.
Every `Account`/`Quote`/`Invoice` also belongs to exactly one
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
  `InvoiceService`, `BusinessProfileService`, `StatsService`; `models.py`,
  `errors.py`, `clock.py`, `repository.py` the storage Protocol,
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
SQLite file (`auth.db` by default, `INVOICE_SYSTEM_AUTH_DB` to override) —
do not confuse it with this app's own `Account` (a client business being
billed). `core.py` never imports `sessionkit` — see architecture rules.
Manage users with the bundled `sessionkit` CLI (`uv run sessionkit add ...`),
not through this app; there is no public signup route.

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
  the logged-in user's *own* details, in three groups (also how the
  settings page presents them - see Conventions): **user settings**
  (`title` optional, `first_name`, `last_name` — the account holder's
  personal name, **never shown on a PDF**); **business settings**
  (`business_name`, and a UK GOV.UK Design System-style address —
  `address_line1`/`address_line2`/`town_or_city`/`county`/`postcode`, each
  independently optional, no "all or nothing" rule); **payment and tax
  settings** (`payment_terms_days`, `currency` - the *reporting* currency
  the home dashboard's monthly-totals chart sums in, defaults `"GBP"`,
  independent of the currency chosen per quote/invoice - `utr`/`vat_number`
  optional). One per
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
- Serve: `uv run uvicorn invoice_system.api.app:app --reload` (API on
  `:8000`; `INVOICE_SYSTEM_DB` / `INVOICE_SYSTEM_AUTH_DB` override the
  default db paths).
- CLI: `uv run invoice-system-cli --help` (or the installed
  `invoice-system-cli` entry point) — mirrors the API one-for-one over the
  same storage. **Not** behind login — it's a local, trusted tool; only the
  HTTP API is gated (see architecture rules). Where the API resolves "which
  user"/"which organisation" from the Bearer token, the CLI takes an
  explicit `--user-id` instead — **required** on every account/quote/invoice
  command (`account create/list/update`, `quote
  create/add-item/send/convert/pdf`, `invoice
  list/send/void/pay/monthly-totals/pdf`, `stats`), since there's no session
  to resolve an organisation from otherwise (see "Four separate things"
  above). `settings show/set`, `invoice send`, `quote pdf`/`invoice pdf`
  additionally use that same `--user-id` for their pre-existing purpose
  (payment-terms-driven due dates, the PDF "from" party).
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
  does not decide business rules, generate ids beyond what the DB gives it,
  or validate input. This is what makes the domain layer testable against a
  fake/in-memory implementation instead of a real database.
- **Injectable `clock`** (and any other ambient, hard-to-test dependency — a
  password hasher, a random invoice-number generator, a PDF/email client)
  **on every service that needs one.** Tests supply a fake/fixed version.
  Never call the ambient version (`datetime.now()`, `random.random()`, ...)
  directly inside a service method.
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
  added while draft. `send()` assigns the number (`Q-0001`/`INV-0001`, a
  per-entity counter in the `counters` table) and freezes line items — issue
  a new quote/invoice rather than editing history afterwards. A Quote can
  only convert to an Invoice once, from `sent`/`accepted`, copying its line
  items; converting flips the Quote to `converted`.
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
  the fixed `DEFAULT_INVOICE_DUE_DAYS`. `business_name` + whichever address
  lines are set appear as a "From" section on generated PDFs (`pdf.py`'s
  `business_profile_lines()`), **above** "Bill to", in the standard UK
  order (`address_line1`, `address_line2`, `town_or_city`, `county`,
  `postcode`) — only when `business_name` is actually set, never
  empty/blank. Neither `pdf.py` nor
  `InvoiceService` import `BusinessProfileService` or know what a "user" is
  — the API/CLI layers resolve the profile and pass plain values in
  (`payment_terms_days: int | None`, `from_profile: BusinessProfile | None`),
  keeping the "whose profile" question entirely at the entry-point layer.
  **Deliberately not shown on a PDF**: `title`/`first_name`/`last_name` —
  only `business_name` and the address were asked for.
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
  sections, `web/src/components/MonthlyTotalsChart.tsx`) - see the next
  bullet for what it sums and the "Deliberately not exact" note under
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
  the aggregation behind that chart: it buckets every non-draft, non-void
  invoice **belonging to that organisation** (not per-account) by the
  calendar month of its `issue_date` (when it was *created*, not `due_date`
  or `created_at`'s time-of-day), summing `paid` separately from everything
  else (`sent` - there is no stored `overdue`, see above), and **only for
  invoices whose `currency` matches the `currency` argument** - an invoice
  in a different currency is silently excluded rather than naively summed
  in with it (see `BusinessProfile.currency` above). The API/CLI resolve
  both the organisation (from the Bearer token/`--user-id`, see "Four
  separate things" above) and which currency to pass from the caller's own
  business profile (`GET /invoices/monthly-totals`, CLI `invoice
  monthly-totals --user-id`); `InvoiceService` itself takes a plain
  `currency: str` and has no idea whose profile it came from, same pattern
  as `payment_terms_days`.
- The settings page (`web/src/pages/SettingsPage.tsx`) groups
  `BusinessProfile` fields into three `<fieldset>`/`<legend>` sections
  matching the model's own three groups (user settings, business settings,
  payment and tax settings) — a real semantic/accessible grouping (Playwright's
  `getByRole('group', { name: ... })` finds them via the `<legend>`), not
  just a visual one. Add a new field to whichever group it actually belongs
  to, not wherever's convenient.
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
  quotes and invoices, both listed newest-issued-first. `AccountsPage.tsx`
  also has a search box (`accountMatchesQuery` in that file, unit-tested
  in `AccountsPage.test.ts`) that filters client-side against every shown
  field, and each row is clickable (`role="link"`, keyboard-operable via
  Enter/Space, not just the mouse) navigating to that account's detail
  page — the per-row "New quote" link stops click/keydown propagation so
  it doesn't also trigger the row's own navigation. Creating a new account
  navigates straight to its detail page on success, rather than staying on
  the list.
- `StatsService.get_stats(organisation_id)` is the all-time counters,
  scoped to one organisation, behind the home dashboard's "All-time stats"
  section (`GET /stats`, CLI `stats`) — currently just `account_count`. A
  separate service, not a method on `AccountService`, because these stats
  are expected to grow beyond accounts; add a field to `Stats` (models.py)
  and a line to `get_stats()` when a new one is actually asked for, not
  speculatively.
- Two separate exception hierarchies get mapped to HTTP status in `api/app.py`,
  each in its own handler: this app's `AppError` (`handle_app_error`) and
  sessionkit's `AuthError` (`handle_auth_error`). Don't merge them into one
  handler or one `except` clause — see `docs/extracting-reusable-packages.md`
  on why a vendored cross-cutting concern keeps its own error base.

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
  - Relaxing a `NOT NULL` constraint: SQLite can't `ALTER COLUMN` a
    constraint in place, so this needs a rebuild-and-swap — new table with
    the target shape, `INSERT ... SELECT` the old data across (`NULLIF`
    where a required-with-default-`''` column becomes genuinely nullable),
    `DROP` the old table, `RENAME` the new one into its place.
  - Adding/dropping a nullable column, or adding one with a constant
    default: both are plain `ALTER TABLE` statements SQLite supports
    directly — no rebuild needed.
  (`MIGRATIONS` was flattened to a single baseline entry on 2026-09-16 —
  no real database had been started against the prior 5-migration history
  yet, so there was nothing any later migration needed to carry forward.
  Don't flatten it again once a real database exists somewhere; that's
  exactly the scenario forward-only migrations exist to handle instead.
  Migration 2, added the same day, is the current reference example of the
  "adding a column with a constant default" case above: `quote_line_items`/
  `invoice_line_items` both get `tax_rate TEXT NOT NULL DEFAULT '0'`.
  Migration 3 added `Organisation`/`organisation_members` plus nullable
  `organisation_id` on `accounts`/`quotes`/`invoices` (nullable, not a
  constant default, since there's no sensible organisation to backfill
  existing rows with — see `docs/data-model.md`'s "Multi-tenancy" on the
  consequence: old rows become invisible, not an error). Migration 4 is the
  other rebuild-and-swap reference example, alongside the `NOT NULL`
  case above: `quotes.number`/`invoices.number` had a column-level
  `UNIQUE`, wrong once numbering became per-organisation (two
  organisations' first quotes can both legitimately be `Q-0001`) — SQLite
  can't drop a column constraint via `ALTER TABLE` any more than it can add
  one, so this rebuilds both tables and replaces it with a composite
  `UNIQUE INDEX` on `(organisation_id, number)` instead, carrying row ids
  across explicitly so `quote_line_items`/`invoice_line_items` and
  `invoices.quote_id` keep pointing at the right rows. Migration 5 split
  `accounts.address` into `address_line1`/`address_line2`/`town_or_city`/
  `county`/`postcode` (same structure as `business_profiles`' - see
  data-model.md) — this one's a plain `ADD COLUMN` × 5 + `UPDATE ... SET
  address_line1 = address` + `DROP COLUMN address`, no rebuild needed
  (SQLite supports dropping a column directly, including a `NOT NULL`
  one, as long as it isn't part of an index/constraint or the table's last
  column); the old free-text value moves into `address_line1` wholesale,
  not guessed-at-split, same reasoning as `business_profiles`' own
  historical address split.)
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
- `sessionkit` is pinned by git tag (`@v0.1.2` in `pyproject.toml`), not a
  PyPI version — bump the tag deliberately, re-run `uv lock`, and check its
  own CHANGELOG/README for breaking changes; there's no semver guarantee
  from a tag alone. `SqliteAuthStore` never closes itself — `AuthService`
  doesn't own it, so `auth.py`'s `Auth` wrapper holds the store alongside
  the service specifically so `Auth.close()` has something to call; don't
  build a bare `AuthService(SqliteAuthStore.open(...))` and drop the store
  reference, or nothing can close it later. (v0.1.0 had no `close()` at all
  and defaulted `check_same_thread=True`, which broke under the API's
  worker-thread pool — fixed in v0.1.1/v0.1.2; don't reintroduce either by
  pinning back to v0.1.0/v0.1.1.)
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
  before the assertion, or don't assert the specific value at all.
