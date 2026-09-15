# Roadmap

## Phase 0 — Project scaffolding (done)

- [x] Adopt the CLAUDE.md/docs primer, filled in for this project's domain.
- [x] `pyproject.toml`, `src/invoice_system/` skeleton (core, models, errors,
      repository, factory, clock, pdf), `storage/` with baseline schema +
      migration runner, `api/` and `cli/`.
- [x] `tests/` mirror + `conftest.py` (`FakeClock`, per-test SQLite fixture).
- [ ] CI: backend job running the full suite with the coverage floor.

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
- [ ] CI: coverage table in job summary, cancel superseded runs (see
      `testing-and-ci.md`).

Update the checkboxes and phase status as work lands — this file is read as
ground truth for "what's done," not aspirational copy.
