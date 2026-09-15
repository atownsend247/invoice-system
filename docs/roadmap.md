# Roadmap

## Phase 0 — Project scaffolding (current)

- [x] Adopt the CLAUDE.md/docs primer, filled in for this project's domain.
- [ ] `pyproject.toml`, `src/invoice_system/` skeleton (core, models, errors,
      repository, factory), `storage/` with baseline schema + migration
      runner, empty `api/` and `cli/` packages.
- [ ] `tests/` mirror + `conftest.py` (FakeClock, in-memory SQLite fixture).
- [ ] CI: backend job running the full suite with a coverage floor.

## Phase 1 — Core invoicing

- [ ] `Account`/`Client`/`Invoice`/`LineItem` models and migrations (see
      `data-model.md`).
- [ ] `InvoiceService`: create draft, edit draft, add/remove line items,
      send (assigns invoice number, freezes line items), void.
- [ ] CLI covering the same operations, over the same service.

## Phase 2 — Payments and status

- [ ] `Payment` model + recording partial/full payments.
- [ ] Status derivation (`sent → paid` once payments cover the total;
      `sent → overdue` once past `due_date`).

## Phase 3 — API + web client

- [ ] FastAPI routes per `api.md`, thin per `architecture.md`.
- [ ] Accounts/sessions cross-cutting module (`accounts.py`) + auth
      dependency applied by default.
- [ ] React/Vite SPA in `web/`: client list, invoice list/detail, payment
      recording.

## Phase 4 — Delivery

- [ ] Invoice PDF generation.
- [ ] Email delivery on send.

Update the checkboxes and phase status as work lands — this file is read as
ground truth for "what's done," not aspirational copy.
