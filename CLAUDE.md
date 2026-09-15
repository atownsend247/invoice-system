# CLAUDE.md

Invoice System: a freelancer/small-business billing tool. Domain shape is
Account (the business you provide a service to — business name, contact,
address) → Quote → Invoice, where a Quote converts into an Invoice rather
than the two being independently created. Quotes and Invoices are each
independently viewable/exportable as PDFs.

## Where things are

- Design docs: `docs/` — start with `docs/development.md` (how to run it) and
  `docs/architecture.md`. `docs/data-model.md`, `docs/api.md`, `docs/roadmap.md`
  are the reference. **Keep these in sync when code changes** (roadmap phases,
  endpoint tables, model tables) — a stale doc is worse than no doc, because an
  agent reads it as ground truth.
- `src/invoice_system/` — flat top level holds the load-bearing modules
  (`core.py` all domain logic — `AccountService`, `QuoteService`,
  `InvoiceService`; `models.py`, `errors.py`, `clock.py`, `repository.py` the
  storage Protocol, `factory.py` wiring, `pdf.py` PDF rendering used by both
  entry points). Subpackages: `storage/` (schema + migrations, the concrete
  `SqliteRepository`), `api/` (thin FastAPI layer), `cli/` (thin Click
  layer). `tests/` mirrors the package 1:1 (`tests/{core,api,cli,storage}/`)
  + a root `conftest.py` with shared fixtures.
- `web/` — not created yet. When a web UI is added, keep it a sibling of
  `src/`, its own test runner and build, its own README.

No accounts/sessions (login) module exists yet — every `Account` in this
codebase means "a client business being billed," not a login identity. If/when
authentication is added (see `docs/roadmap.md`), give it its own
cross-cutting module rather than overloading `Account`.

## Commands

- Tests: `uv run pytest --cov=src/invoice_system --cov-report=term-missing`
  (run the **full** suite before finishing a change; CI enforces a 90%
  coverage floor, see gotchas).
- First-run / bootstrap: `uv sync && uv run invoice-system-cli init-db` —
  creates the SQLite file and applies migrations; no seed data by default.
- Serve: `uv run uvicorn invoice_system.api.app:app --reload` (API on
  `:8000`; set `INVOICE_SYSTEM_DB` to override the default db path).
- CLI: `uv run invoice-system-cli --help` (or the installed
  `invoice-system-cli` entry point) — mirrors the API one-for-one over the
  same storage.
- Build: no `web/` yet — nothing to build.

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
  is enforced at **one** boundary (a single dependency/middleware the web
  layer applies to every route by default), not re-checked ad hoc per
  handler. **No such boundary exists yet** — there is no auth of any kind
  today, so every route in `api/app.py` is effectively public. Do not bolt
  per-route checks on ad hoc when auth is added; wire the one boundary first.

## Conventions

- Money (quote/invoice line-item amounts and totals) is a `Decimal`
  internally, serialised as a **string** on the wire (`LineItemIn`/`Out` in
  `api/schemas.py`), never a native float/JSON number. A non-decimal string
  is rejected at the API boundary (422) rather than coerced. Currency is
  stored alongside every quote/invoice, not assumed globally. `LineItem` is
  shared by both Quote and Invoice — same shape, associated via
  `quote_id`/`invoice_id` at the storage layer, not two separate classes.
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
  components. A shared data-fetching hook wraps it. Money stays a string
  client-side too — parse to a decimal library only at the point of doing
  arithmetic, never just to render it. (No `web/` exists yet.)

## Gotchas

- **Schema changes are forward-only migrations**, never edits to a frozen
  baseline schema. Append a numbered entry to a `MIGRATIONS` list; a
  migration runner applies whatever's pending and tracks progress via
  `PRAGMA user_version`. Existing data must survive every migration — write
  it as if a production database will run it unattended.
- Storage is a single shared SQLite connection/file — **serialise every
  access on a lock** inside the repository implementation rather than
  assuming the caller will.
- Changing a domain default (currency, invoice-number format, a status
  value, ...) — `grep` the test suite for the old value first; tests that
  assert exact strings/values are usually the ones that catch a half-done
  rename.
- Pin the language/runtime version everywhere it's declared (lockfile, CI,
  a `.python-version` file) and don't quietly widen it to "support" an
  older version nobody asked for.
- A generated, committed artifact (an OpenAPI schema dump, a changelog, a
  lockfile) needs **one** regeneration command and a CI check that fails if
  the committed copy is stale — see `docs/testing-and-ci.md`. Don't have CI
  silently rewrite it and push back unless you've deliberately decided you're
  fine with bot commits landing on your default branch; verify-and-fail is
  the lower-surprise default, especially for a single maintainer who pushes
  straight to the trunk branch.
