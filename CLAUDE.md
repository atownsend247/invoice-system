# CLAUDE.md

Invoice System: a small business/freelancer billing tool. Domain shape is
Client → Invoice → LineItem, with an Invoice moving through a status
lifecycle (`draft → sent → paid`, with `overdue`/`void` as branches) as
Payments are recorded against it.

## Where things are

- Design docs: `docs/` — start with `docs/development.md` (how to run it) and
  `docs/architecture.md`. `docs/data-model.md`, `docs/api.md`, `docs/roadmap.md`
  are the reference. **Keep these in sync when code changes** (roadmap phases,
  endpoint tables, model tables) — a stale doc is worse than no doc, because an
  agent reads it as ground truth.
- `src/invoice_system/` — flat top level holds the load-bearing modules
  (`core.py` all domain logic, `accounts.py` auth/sessions cross-cutting,
  `models.py`, `errors.py`, `repository.py` the storage Protocol, `factory.py`
  wiring). Subpackages: `storage/` (schema + migrations, the concrete
  repository), `api/` (thin web layer), `cli/` (thin command-line layer).
  `tests/` mirrors the package 1:1 (`tests/{core,api,cli,storage}/`) + a root
  `conftest.py` with shared fixtures.
- `web/` — the React/Vite SPA, a sibling of `src/`, its own test runner and
  build, its own README.

**Status: pre-code.** Only this primer (CLAUDE.md + docs) exists so far — no
`src/` or `web/` yet. Treat the sections below as the plan the first
scaffolding change should implement, not as a description of code that
already runs; update anything here that turns out wrong once real code lands.

## Commands

Not runnable yet (see Status above) — these are the intended commands for
the stack chosen in `docs/architecture.md` (Python 3.13 + FastAPI + SQLite,
managed with `uv`), to be verified/corrected the moment `pyproject.toml`
exists.
- Tests: `uv run pytest --cov=src/invoice_system --cov-report=term-missing`
  (run the **full** suite before finishing a change; CI enforces a coverage
  floor, see gotchas).
- First-run / bootstrap: `uv sync && uv run invoice-system-cli init-db` —
  creates the SQLite file and applies migrations; no seed data by default.
- Serve: `uv run uvicorn invoice_system.api.app:app --reload` (API) and
  `npm run dev` in `web/` (SPA).
- Build: `npm run build` in `web/` (also runs `tsc --noEmit`).

## Architecture rules (don't violate)

- **Domain logic lives only in `invoice_system.core`.** Everything else (API
  routes, CLI commands, background jobs) is a thin translation layer — no
  rules, no validation logic, no aggregation outside `core`. This is the
  single rule worth enforcing hardest: it's what keeps the domain testable
  without spinning up a web server, and keeps two entry points (the REST API
  and the CLI) from silently disagreeing on a rule.
- **Cross-cutting concerns that aren't the domain** (accounts/sessions,
  billing/payment-provider integration, email/PDF delivery...) **get their
  own module or package**, not bolted onto core. If one is generic enough to
  be useful in an unrelated project, it's a strong candidate to extract as a
  standalone package from day one — see `docs/extracting-reusable-packages.md`.
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
  handler. Deliberately exempt: the health check endpoint and login itself.

## Conventions

- Money (invoice/line-item amounts, totals, payments) is a `Decimal`
  internally, serialised as a **string** on the wire, never a native
  float/JSON number. Reject a float at the API boundary rather than coercing
  it. Currency is stored alongside every money value, not assumed globally.
- Timestamps: timezone-aware, one timezone (UTC) internally, ISO 8601 on the
  wire.
- A new Invoice defaults to status `draft` and is only mutable by its owning
  account while in that status; once `sent`, line items are frozen (issue a
  correction/credit note instead of editing history).
- Client (web UI): **one module is the only thing that talks HTTP** to the
  backend (`web/src/api.ts`) — no `fetch`/`axios` calls scattered through
  components. A shared data-fetching hook wraps it. Money stays a string
  client-side too — parse to a decimal library only at the point of doing
  arithmetic, never just to render it.

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
