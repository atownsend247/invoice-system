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
  entry points, `auth.py` wiring for the login/session cross-cutting concern
  — see below). Subpackages: `storage/` (schema + migrations, the concrete
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

## Commands

- Tests: `uv run pytest --cov=src/invoice_system --cov-report=term-missing`
  (run the **full** suite before finishing a change; CI enforces a 90%
  coverage floor, see gotchas).
- Lint/format: `uv run ruff check .` / `uv run ruff format .` (CI runs both,
  the latter with `--check`; `ruff format` first if `ruff check` complains
  about a line-length issue a format pass would resolve).
- First-run / bootstrap: `uv sync && uv run invoice-system-cli init-db &&
  uv run sessionkit add you@example.com` — creates the domain SQLite file
  and applies migrations, then creates the first login account (prompts for
  a password) in `auth.db`.
- Serve: `uv run uvicorn invoice_system.api.app:app --reload` (API on
  `:8000`; `INVOICE_SYSTEM_DB` / `INVOICE_SYSTEM_AUTH_DB` override the
  default db paths).
- CLI: `uv run invoice-system-cli --help` (or the installed
  `invoice-system-cli` entry point) — mirrors the API one-for-one over the
  same storage. **Not** behind login — it's a local, trusted tool; only the
  HTTP API is gated (see architecture rules).
- Web: `cd web && npm install && npm run dev` (Vite on `:5173`, or whatever
  port it lands on if that one's taken — it logs the actual one; note it
  binds `localhost`, which may resolve to the IPv6 loopback only, so prefer
  `localhost` over `127.0.0.1` when hitting it directly). `VITE_API_BASE_URL`
  points it at the API (default `http://127.0.0.1:8000`). `npm test` /
  `npm run test:e2e` (Playwright; spins up its own throwaway backend + this
  app, see `web/README.md`) / `npm run build` in `web/`.
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
- Two separate exception hierarchies get mapped to HTTP status in `api/app.py`,
  each in its own handler: this app's `AppError` (`handle_app_error`) and
  sessionkit's `AuthError` (`handle_auth_error`). Don't merge them into one
  handler or one `except` clause — see `docs/extracting-reusable-packages.md`
  on why a vendored cross-cutting concern keeps its own error base.

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
  older version nobody asked for. Same for `web/`: `web/.node-version`
  pins Node — this repo was scaffolded with a Vite major (8.x, rolldown-
  based) that needs Node ≥22.12; on an older Node its optional native
  binding silently fails to install and every `vitest`/`vite` invocation
  dies with "Cannot find native binding" (an npm optional-deps bug, not a
  code problem) — `rm -rf node_modules package-lock.json && npm install`
  under the pinned version, not a downgrade, is the fix.
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
