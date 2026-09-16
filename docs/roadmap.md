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
- [x] `AccountService`, `QuoteService`, `InvoiceService`: create/edit
      account, create/edit/send draft quote, convert quote → invoice,
      send/void invoice.
- [x] CLI covering the same operations, over the same service
      (`invoice-system-cli`).
- [x] FastAPI routes per `api.md`, thin per `architecture.md`.
- [x] PDF export for quotes and invoices, independently (`pdf.py`, viewable
      via both the CLI and the API).

## Phase 2 — Payments and status (partially done)

- [x] Marking an invoice fully paid: `InvoiceService.pay()`, `sent → paid`
      only (409 otherwise), mirroring `void()`. A single status flag, not a
      ledger — implemented instead of a `Payment` model because nothing so
      far has needed partial-payment amounts or dates, only "is this paid
      or not" (see the home dashboard's chart, Phase 7). `POST
      /invoices/{id}/pay`, CLI `invoice pay`, and a "Mark as paid" button
      on `web/src/pages/InvoiceDetailPage.tsx`.
- [ ] `Payment` model + recording partial/full payments against an invoice
      (amounts, dates) — not needed yet; add only when something actually
      requires it (e.g. partial payments, a payment history/audit trail).
- [ ] `sent → overdue` as a real, persisted status transition once past
      `due_date`. Still only derived for display (`HomePage.tsx`'s
      `isOverdue`, see Phase 7) — `Invoice.status` is never written as
      `overdue` anywhere in the codebase.

## Phase 3 — Login/sessions and web client

- [x] Login/sessions via [sessionkit](https://github.com/atownsend247/bb-py-sessionkit)
      (distinct from the domain `Account` — see `CLAUDE.md`), wired in
      `auth.py` + `api/auth.py`; every route gated by
      `Depends(get_current_user)` except `/healthz` and `POST /auth/login`.
- [ ] TOTP/2FA endpoints (sessionkit already supports it; not exposed via
      `api/auth.py` yet).
- [x] React/Vite SPA in `web/`: login screen, account list/create, quote
      list/detail (create, add line items, send, convert to invoice),
      invoice list/detail (send, void, mark as paid), PDF download.
      `web/src/api.ts` attaches `Authorization: Bearer <token>` to every
      call except login. Partial-payment recording (amounts/dates) still
      waits on Phase 2's `Payment` model.
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

- [x] `BusinessProfile` (title/first/last name, business name, a
      UK-standard structured address — `address_line1`/`address_line2`/
      `town_or_city`/`county`/`postcode`, each independently optional —
      payment terms, reporting currency (defaults `GBP`, see Phase 7),
      UTR/VAT), one per user, stored in `invoice_system.db`
      keyed by sessionkit's `User.id` (a plain column, not an enforced FK —
      see `CLAUDE.md`). Backend (`BusinessProfileService`, `GET`/`PUT
      /settings/business-profile`) and a `web/` settings page — three
      `<fieldset>`/`<legend>` sections ("User settings" / "Business
      settings" / "Payment and tax settings") + nav link, with its own e2e
      spec (`web/e2e/settings.spec.ts`).
- [x] `payment_terms_days` drives `InvoiceService.send()`'s due-date calc
      (`send(invoice_id, payment_terms_days=...)`, falling back to the
      fixed `DEFAULT_INVOICE_DUE_DAYS` when `None`).
- [x] `business_name` and the structured address lines (in UK order) appear
      as a "From" section on generated PDFs (`pdf.py`'s
      `business_profile_lines()`), above "Bill to", when `business_name` is
      set.
- [x] CLI: `settings show`/`settings set --user-id`, and `--user-id` on
      `invoice send`/`quote pdf`/`invoice pdf` — the answer to "the CLI has
      no current user" was an explicit flag, not a guess (see `docs/api.md`).
- [ ] `title`/`first_name`/`last_name` are captured but not surfaced
      anywhere yet (not on a PDF, not elsewhere in the UI) - deliberately
      out of scope; only business name/address were asked to appear on
      documents.

## Phase 6 — Home dashboard (done)

- [x] A `web/` home page (`/`, `HomePage.tsx`, replacing the old bare
      redirect to `/accounts`) listing `sent` invoices under "Overdue" and
      "Outstanding" sections. This is a **presentational** derivation only
      (`isOverdue`/`isOutstanding` compare `due_date` against today
      client-side) — it does not implement Phase 2's `sent → overdue`
      status transition; `Invoice.status` itself is never written as
      `overdue` anywhere. Covered by `web/src/pages/HomePage.test.ts` (the
      date-comparison logic, unit-tested against fixed dates) and
      `web/e2e/home.spec.ts` (only the reachable "Outstanding" case — no
      code path can backdate a `due_date` to produce a genuinely overdue
      invoice through the API/CLI/UI, see `web/README.md`).

## Phase 7 — Monthly totals chart (done)

- [x] `BusinessProfile.currency` (`NOT NULL DEFAULT 'GBP'`, part of the
      flattened baseline schema — see `CLAUDE.md`'s migrations gotcha) —
      the *reporting* currency the chart below sums in, independent of any
      quote/invoice's own `currency`. Surfaced in
      the "Payment and tax settings" section of `web/`'s settings page and
      pre-fills the "New quote" form's currency field (previously a
      hardcoded `'USD'` default).
- [x] `InvoiceService.monthly_totals(currency, months=12)`: every non-draft,
      non-void invoice system-wide, bucketed by `issue_date`'s month, split
      into `paid_total`/`unpaid_total`, filtered to invoices in `currency`
      only (a different-currency invoice is excluded, never naively summed
      in — see `CLAUDE.md`). `GET /invoices/monthly-totals` and CLI
      `invoice monthly-totals --user-id` resolve `currency` from the
      caller's own business profile.
- [x] A bar chart on the home dashboard (`web/src/components/
      MonthlyTotalsChart.tsx`, plain CSS bars, no charting library) showing
      12 months of paid (green) vs outstanding (blue) totals, below the
      Overdue/Outstanding sections. Unit-tested (`MonthlyTotalsChart.test.tsx`)
      for the height/scaling math; e2e coverage (`web/e2e/home.spec.ts`)
      only checks structure and that paying an invoice removes it from
      Outstanding — not exact chart totals, since the chart sums
      system-wide across whatever else is running concurrently in e2e (see
      `web/README.md` and the CLAUDE.md gotcha on this).

## Phase 8 — Editing accounts (done)

- [x] `AccountService.update_account(account_id, ...)` — a full replace,
      same required fields/validation as `create_account`, 404 if the
      account doesn't exist. `PUT /accounts/{id}`, CLI `account update
      <id>`.
- [x] `web/`: `AccountsPage.tsx`'s `NewAccountForm` generalised into
      `AccountForm` (shared by create and edit), with a per-row "Edit"
      button that swaps that row for the form in place, Save/Cancel — no
      separate `/accounts/:id` route, matching the page's existing flat-list
      convention rather than adding a detail page just for this.

## Phase 9 — Per-line VAT/tax rate (done)

- [x] `LineItem.tax_rate` (a fraction, `[0, 1]`, default `0`) plus
      `net_total`/`tax_amount`/`total` (gross) properties; `Quote`/`Invoice`
      gained matching `subtotal`/`tax_total`/`total`. `tax_amount` is
      rounded to the minor currency unit — see `CLAUDE.md` for the
      `20.0000`-vs-`20.00` bug this fixes and why `net_total` itself stays
      unrounded.
- [x] `POST /quotes/{id}/line-items` accepts `tax_rate` (defaults `"0"`);
      CLI `quote add-item --tax-rate`. `QuoteService.convert_to_invoice`
      carries it across to the new `Invoice`'s line items.
- [x] `web/`: a VAT-rate `<select>` in `LineItemsTable.tsx`'s add-item form
      (Standard 20% / Reduced 5% / Zero 0% — the UK's three rates; the field
      itself isn't restricted to just those server-side), a VAT column per
      line, and a Subtotal/VAT/Total footer replacing the old single-Total
      row. `pdf.py`'s line-item table gained the same VAT column and
      three-row summary, shared by both quote and invoice PDFs.

## Phase 10 — All-time stats (done)

- [x] `StatsService.get_stats()` (currently just `account_count`,
      system-wide) — a separate service from `AccountService` since more
      stats are expected later. `GET /stats`, CLI `stats`.
- [x] An "All-time stats" section on the home dashboard
      (`web/src/pages/HomePage.tsx`), below the monthly-totals chart.

## Phase 11 — Demo data (done)

- [x] `src/invoice_system/demo_data.py`: a demo login user
      (`demo@example.test`), a `BusinessProfile`, 5 accounts, and ~14
      quotes/invoices spread across the trailing 12 months in a mix of
      statuses (draft/sent/rejected/expired quotes; draft/outstanding/
      overdue/paid/void invoices) and VAT rates — seeded by
      `invoice-system-cli init-db` unless `--no-demo` is passed. Idempotent
      (checked via sessionkit's `DuplicateUser`), goes through the real
      service layer with a backdated clock rather than hand-crafted storage
      rows. **Must be kept in sync with new features by hand** — see
      `CLAUDE.md`.

## Phase 12 — CI/CD (basic, done)

- [x] `Jenkinsfile`: build + test (mirrors `.github/workflows/ci.yml` -
      backend and frontend in parallel, e2e after both pass) and, on `main`
      only, deploy both the backend and the built frontend to a Proxmox LXC
      container over SSH (`deploy/deploy.sh`). `deploy/
      invoice-system-api.service` and `deploy/nginx-invoice-system.conf`
      are one-time-setup reference config for the container (systemd unit,
      nginx reverse-proxying `/api/` to the backend same-origin), not
      applied by the pipeline itself. Always deploys with `init-db
      --no-demo` — see `CLAUDE.md`. See `docs/deployment.md` for the full
      one-time Jenkins/container setup this assumes.
- [ ] Infrastructure provisioning (the container itself, TLS, `nginx`/`uv`
      installation) is manual, not Terraform/Ansible/cloud-init-managed.
- [ ] No rollback automation, no staging environment, no secrets management
      beyond the one SSH credential — see `docs/deployment.md`'s "Not done
      yet".

## Phase 13 — Per-user data isolation (multi-tenancy) (done)

- [x] `Organisation` model + `organisation_members` join table (`UNIQUE` on
      `user_id`), the tenant boundary — see `data-model.md`'s
      "Multi-tenancy". Migration 3 (adds both, plus nullable
      `organisation_id` on `accounts`/`quotes`/`invoices`) and migration 4
      (rescopes `Quote.number`/`Invoice.number` uniqueness from a global
      column constraint to a composite `(organisation_id, number)` index —
      numbering is per-organisation, so two organisations' first
      quote/invoice can both be `Q-0001`/`INV-0001`).
- [x] `OrganisationService.get_or_create_for_user` — auto-creates an
      `Organisation` the first time a login user needs one; atomic at the
      storage layer (`SqliteRepository.add_organisation_member` does a
      locked check-then-insert) so two concurrent first-ever requests for
      the same brand-new user can't crash each other.
- [x] `AccountService`/`QuoteService`/`InvoiceService`/`StatsService`: every
      create/get/list/update method (and `monthly_totals`) now takes
      `organisation_id`; fetching another organisation's row by id is a 404
      (`NotFound`), same as a nonexistent one, deliberately — never a
      distinct 403 that would confirm the id belongs to someone else.
- [x] API: `organisation_id` resolved server-side from the Bearer token
      (`api/app.py`'s `get_organisation_id` dependency) — never part of any
      request/response schema.
- [x] CLI: `--user-id` is now a **required** option on every
      account/quote/invoice command (breaking change) — the CLI has no
      login session to resolve an organisation from.
- [x] `demo_data.py` seeds into the demo user's own auto-created
      `Organisation`, same as any other user.
- [x] Fixed the bug that prompted this: every login user previously saw the
      first-ever created user's data (no tenant scoping existed at all).

Not done: **multiple users sharing one organisation** (inviting a colleague
to see the same business's data) — the schema is deliberately already
shaped for it (`organisation_members` is a proper join table), so this is
expected to be "drop the `UNIQUE` on `user_id`, add an invite/add-member
flow," not a restructuring, whenever it's actually needed.

Update the checkboxes and phase status as work lands — this file is read as
ground truth for "what's done," not aspirational copy.
