# Roadmap

## Phase 0 — Project scaffolding (done)

- [x] Adopt the CLAUDE.md/docs primer, filled in for this project's domain.
- [x] `pyproject.toml`, `src/invoice_system/` skeleton (core, models, errors,
      repository, factory, clock, pdf), `storage/` with baseline schema +
      migration runner, `api/` and `cli/`.
- [x] `tests/` mirror + `conftest.py` (`FakeClock`, per-test SQLite fixture).
- [x] CI: backend job running the full suite with the coverage floor
      (`.github/workflows/ci.yml`).

## Phase 1 — Core invoicing (done)

- [x] `Account`/`Quote`/`Invoice`/`LineItem` models and migrations (see
      `data-model.md`).
- [x] `AccountService`, `QuoteService`, `InvoiceService`: create account,
      create/edit/send draft quote, convert quote → invoice, send/void
      invoice.
- [x] CLI covering the same operations, over the same service
      (`invoice-system-cli`).
- [x] FastAPI routes per `api.md`, thin per `architecture.md`.
- [x] PDF export for quotes and invoices, independently (`pdf.py`, viewable
      via both the CLI and the API).

## Phase 2 — Payments and status

- [ ] `Payment` model + recording partial/full payments against an invoice.
- [ ] Status derivation (`sent → paid` once payments cover the total;
      `sent → overdue` once past `due_date`).

## Phase 3 — Login/sessions and web client

- [x] Login/sessions via [sessionkit](https://github.com/atownsend247/bb-py-sessionkit)
      (distinct from the domain `Account` — see `CLAUDE.md`), wired in
      `auth.py` + `api/auth.py`; every route gated by
      `Depends(get_current_user)` except `/healthz` and `POST /auth/login`.
- [ ] TOTP/2FA endpoints (sessionkit already supports it; not exposed via
      `api/auth.py` yet).
- [x] React/Vite SPA in `web/`: login screen, account list/create, quote
      list/detail (create, add line items, send, convert to invoice),
      invoice list/detail (send, void), PDF download. `web/src/api.ts`
      attaches `Authorization: Bearer <token>` to every call except login.
      Payment recording waits on Phase 2's `Payment` model.
- [x] CORS enabled on the API (`CORSMiddleware` in `api/app.py`, see
      `CLAUDE.md`) so the SPA (a different origin/port in dev) can call it.

## Phase 4 — Delivery

- [ ] Email delivery of quote/invoice PDFs on send.
- [x] CI: coverage table in job summary, cancel superseded runs (see
      `testing-and-ci.md`) — `.github/workflows/ci.yml`: backend
      (pytest+coverage), frontend (vitest+build), e2e (Playwright, gated on
      the other two passing first).
- [ ] CI: a "Test Results" check run from JUnit/equivalent output (see
      `testing-and-ci.md`) — not done; currently only the raw job logs +
      the coverage summary.

## Phase 5 — User settings (business profile) (done)

- [x] `BusinessProfile` (title/first/last name, business name/address,
      payment terms, UTR/VAT), one per user, stored in `invoice_system.db`
      keyed by sessionkit's `User.id` (a plain column, not an enforced FK —
      see `CLAUDE.md`). Backend (`BusinessProfileService`, `GET`/`PUT
      /settings/business-profile`) and a `web/` settings page + nav link,
      with its own e2e spec (`web/e2e/settings.spec.ts`).
- [x] `payment_terms_days` drives `InvoiceService.send()`'s due-date calc
      (`send(invoice_id, payment_terms_days=...)`, falling back to the
      fixed `DEFAULT_INVOICE_DUE_DAYS` when `None`).
- [x] `business_name`/`business_address` appear as a "From" section on
      generated PDFs (`pdf.py`'s `business_profile_lines()`), above "Bill
      to", when `business_name` is set.
- [x] CLI: `settings show`/`settings set --user-id`, and `--user-id` on
      `invoice send`/`quote pdf`/`invoice pdf` — the answer to "the CLI has
      no current user" was an explicit flag, not a guess (see `docs/api.md`).
- [ ] `title`/`first_name`/`last_name` are captured but not surfaced
      anywhere yet (not on a PDF, not elsewhere in the UI) - deliberately
      out of scope; only business name/address were asked to appear on
      documents.

Update the checkboxes and phase status as work lands — this file is read as
ground truth for "what's done," not aspirational copy.
