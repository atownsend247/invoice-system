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
      `AccountForm` (shared by create and edit). Originally a per-row
      "Edit" button that swapped that row for the form in place, no
      separate `/accounts/:id` route — superseded by Phase 14's
      `AccountDetailPage`, below.

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

- [x] `StatsService.get_stats(organisation_id, currency)` — a separate
      service from `AccountService` since stats span every entity.
      `account_count`/`quote_count`/`invoice_count` (every row, any
      status), `quotes_sent_count`/`quotes_converted_count` (raw counts, a
      conversion rate is derived client-side), `total_paid` (paid invoices
      only, filtered to `currency` — same convention as
      `InvoiceService.monthly_totals`). `GET /stats`, CLI `stats`.
- [x] An "All-time stats" section on the home dashboard
      (`web/src/pages/HomePage.tsx`), below the monthly-totals chart:
      accounts registered, quotes created, quote conversion rate
      (`conversionRate`, unit-tested in `HomePage.test.ts`), invoices
      created, total paid.

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

## Phase 14 — Account detail page (done)

- [x] `web/`: `AccountDetailPage.tsx` (`/accounts/:id`) — an account's own
      fields (an "Edit" toggle reveals `AccountForm`, now extracted to
      `components/AccountForm.tsx` so `AccountsPage.tsx` and this page
      share one implementation instead of two), plus that account's quotes
      and invoices, each listed newest-`issue_date`-first. Replaces Phase
      8's inline per-row editing: `AccountsPage.tsx`'s list-row "Edit" is
      now a `Link` to this page, and creating a new account there
      navigates straight to its detail page on success rather than staying
      on the list.

## Phase 15 — Structured account addresses, account search, clickable rows (done)

- [x] `Account.address` split into `address_line1`/`address_line2`/
      `town_or_city`/`county`/`postcode`, matching `BusinessProfile`'s UK
      GOV.UK Design System structure (`address_line1` required, the rest
      independently optional) — migration 5, threaded through
      `AccountService`, `api/schemas.py`, `cli/main.py`'s `account
      create`/`update` (now `--address-line1` + optional `--address-line2`/
      `--town-or-city`/`--county`/`--postcode`), `pdf.py`'s new
      `account_address_lines()` (the "Bill to" section), and
      `demo_data.py`'s seed accounts. See `data-model.md`'s entity table
      and CLAUDE.md's migrations gotcha.
- [x] `web/`: `AccountForm.tsx` grew the same five address fields (labels
      matching `SettingsPage.tsx`'s); `AccountDetailPage.tsx`'s read-only
      view and `AccountsPage.tsx`'s list column both render them via a new
      shared `accountAddressLines()` (`src/accountAddress.ts`).
- [x] `web/`: a search box on `AccountsPage.tsx` (`accountMatchesQuery`,
      unit-tested) filters the list client-side against business/contact
      name, email, phone, and every set address line.
- [x] `web/`: each row in the accounts list is now clickable (and
      keyboard-operable via Enter/Space) to open that account's detail
      page — the per-row "New quote" link stops click/keydown propagation
      so it isn't swallowed by the row's own navigation.

## Phase 16 — PDF preview, bank details, document header/footer (done)

- [x] Quote/invoice detail pages now have two PDF actions instead of one:
      "Download PDF" (unchanged) and "View PDF", an in-page preview
      (`web/src/components/PdfViewerModal.tsx`, an `<iframe>` over an
      overlay). **Not** a new browser tab — the first approach tried, but
      modern Chromium refuses to top-level-navigate a different browsing
      context to a `blob:` URL created by another one (confirmed several
      ways: `window.open` with a synchronous reservation + deferred
      `location.href`, with and without `'noopener'`, and a synthetic
      `<a target="_blank">` click all left the new tab stuck on
      `about:blank`/blank forever). A `blob:` URL works fine as an
      `<iframe src>` in the *same* document, which the modal relies on. No
      new API route — same `GET /quotes|invoices/{id}/pdf`, just a second
      way of handling the response client-side. See CLAUDE.md and
      `web/README.md`.
- [x] `BusinessProfile` gained three optional, purely-informational bank
      fields in the existing "payment and tax settings" group —
      `bank_account_name`/`bank_sort_code`/`bank_account_number` — and a
      new "document settings" group with `document_header`/
      `document_footer` (free text, multi-line). Migration 6. Threaded
      through `BusinessProfileService.save_profile`, `api/schemas.py`,
      `cli/main.py`'s `settings set`/`show`, and `demo_data.py`'s seed
      profile.
- [x] `document_header`/`document_footer` are the one part of this phase
      that actually changes generated PDFs: `pdf.py`'s new
      `document_header_lines()`/`document_footer_lines()` (mirroring
      `business_profile_lines()`'s pattern) insert the header above the
      title and the footer below the totals table on every quote/invoice
      PDF this user generates. Deliberately not a per-page running
      header/footer (reportlab page templates/canvas callbacks — a bigger
      lift than asked for) — fixed text once at the top and bottom, which
      is enough for the short, mostly-single-page documents this app
      generates. Bank details are **not** currently rendered on any PDF —
      settings-only for now.
- [x] `web/`: `SettingsPage.tsx` gained the three bank inputs in its
      existing "Payment and tax settings" `<fieldset>`, and a new
      "Document settings" `<fieldset>` with two `<textarea>` fields
      (`.form-field-wide`, spanning the full form width rather than the
      narrow single-line-input column).

## Phase 17 — UUID ids (done)

- [x] Every primary key/foreign-key-shaped column across the app
      (`Organisation`, `Account`, `Quote`, `Invoice`, `LineItem`,
      `BusinessProfile.user_id`, and sessionkit's own `User.id`) is now a
      random UUID4 string instead of a sequential `INTEGER AUTOINCREMENT` —
      closes a secondary leak the multi-tenancy work in Phase 13 didn't:
      even with real access control in place, a global autoincrementing
      sequence across every organisation's rows still revealed system-wide
      activity volume to any single tenant. See `data-model.md`'s "Opaque
      ids".
- [x] sessionkit bumped `v0.1.2 → v0.2.0` (a breaking change — `User.id`
      becomes a UUID4, generated by `SqliteAuthStore.add_user()`, not the
      `users` table's rowid).
- [x] New injectable `IdGenerator` (`src/invoice_system/ids.py`), the same
      ambient-dependency pattern as `clock` (see CLAUDE.md's Architecture
      rules): every `core.py` service takes a `new_id` that generates an
      entity's id *before* constructing it, so `SqliteRepository.create_*`
      only ever persists an id it's given, never `cursor.lastrowid`.
- [x] Migration 7: a full `DROP`/`CREATE` reset of every table to
      `TEXT`-typed ids (not an in-place integer→UUID remap-and-rewrite) —
      explicitly an authorized one-time reset given no production data
      existed yet, not a pattern to reuse once real user data exists. Side
      effect: `organisation_id` on `accounts`/`quotes`/`invoices` is now
      `NOT NULL` (a fresh `CREATE TABLE` has no need for the nullability
      migration 3 required).
      `list_accounts`/`list_quotes`/`list_invoices` moved from `ORDER BY
      id`/`ORDER BY created_at, id` to `ORDER BY rowid` — a UUID has no
      relationship to insertion order, unlike the old autoincrementing int
      which doubled as one; SQLite's implicit per-row `rowid` still gives a
      stable creation order without reintroducing a leaked sequence, since
      it's never selected or exposed to any caller.
- [x] `web/`: every `id` field (`types.ts`) and id-typed `api.ts` parameter
      is now `string`, not `number`; route params (`useParams()`) are used
      as-is instead of `Number(id)`-converted.
- [x] Full backend (168 tests, 97.54% coverage), frontend (29 unit tests),
      and e2e (34 tests) suites updated and passing against real UUIDs
      end-to-end.

## Phase 18 — Expense tracking (done)

- [x] `Expense` model (`id`, `organisation_id`, `account_id`, `number`,
      `currency`, `issue_date`, `created_at`, `line_items`) - a cost
      incurred against an `Account`, e.g. a domain renewal paid on a
      client's behalf. Deliberately no `status`/lifecycle field, unlike
      `Quote`/`Invoice`: it's a record of money already spent, not a
      document issued to anyone, so `ExpenseService.create_expense`
      assigns its `EXP-0001` number (same per-organisation counter
      pattern as `Q-`/`INV-`) immediately at creation rather than
      deferring to a later `send()`, and `add_line_item` isn't gated
      behind any status check - a line item can be added at any time.
      Line items share `LineItem` (including a per-line `tax_rate`)
      rather than a simpler description+amount shape, since VAT on a
      business expense may be separately reclaimable. Migration 8:
      `expenses`/`expense_line_items`, two brand new tables (a plain
      `CREATE TABLE` each, no rebuild needed).
- [x] `POST /expenses`, `GET /expenses` (optionally `?account_id=`), `GET
      /expenses/{id}`, `POST /expenses/{id}/line-items`, `GET
      /expenses/{id}/pdf`. CLI: `expense create/list/add-item/pdf`, same
      required `--user-id` pattern as `quote`/`invoice`.
- [x] `pdf.py`'s `render_expense_pdf` reuses `_render` (now taking an
      optional `status: str | None` - `None` omits the "Status:" line
      entirely, since an `Expense` has none) with no due/expiry date.
- [x] `web/`: `AccountDetailPage.tsx` gained a third "Expenses" section
      below Quotes/Invoices, newest-issued-first, with a "New expense"
      link to `ExpenseNewPage.tsx` (same create-form pattern as
      `QuoteNewPage.tsx`). `ExpenseDetailPage.tsx` (`/expenses/:id`)
      reuses `LineItemsTable`/`PdfViewerModal` unchanged, but has no
      status badge or send/convert actions - there's no lifecycle to
      show one for, and its add-item form is always shown (no draft
      gate).
- [x] `demo_data.py` seeds a handful of `Expense`s (domain renewal,
      software subscription, stock photography) across a few demo
      accounts, spread over the last 12 months like the quote/invoice
      scenarios.
- [x] Full backend (196 tests, 97.85% coverage), frontend (33 unit
      tests), and e2e (40 tests, new `expenses.spec.ts`) suites updated
      and passing.

## Phase 19 — Expense attachments (done)

- [x] `ExpenseAttachment` (id, expense_id, filename, content_type, size,
      created_at) - supplementary PDFs (e.g. a scanned receipt) uploaded
      against an expense, addable at any time (no lifecycle to gate on,
      same as expense line items). **Metadata only** in SQLite (migration
      9, `expense_attachments`) - the uploaded bytes live on the
      filesystem instead, via a new small `attachments.py` module
      (`AttachmentStore`, injected into `ExpenseService` the same way
      `clock`/`new_id` are, but required rather than optional). Filed
      under the attachment's own UUID id, never the caller's filename, so
      there's nothing to sanitise for path-traversal safety.
      `ExpenseService.add_attachment` enforces a PDF-only check
      (`content_type == "application/pdf"` or a `.pdf` extension - a
      browser's own guessed Content-Type isn't always trustworthy) and a
      10MB cap (`MAX_ATTACHMENT_SIZE`).
- [x] `POST /expenses/{id}/attachments` (`multipart/form-data`, needs the
      new `python-multipart` dependency FastAPI's `UploadFile` requires),
      `GET /expenses/{id}/attachments/{attachment_id}` (view/download,
      one route for both, same pattern as the generated PDF routes), and
      `DELETE /expenses/{id}/attachments/{attachment_id}`. Attachments
      are inlined on `ExpenseOut`/`Expense.attachments`, same as
      `line_items` - no separate list endpoint. CLI: `expense attachment
      add/list/download/delete`, same required `--user-id` pattern as
      everything else; a new `--attachments-dir`/`INVOICE_SYSTEM_
      ATTACHMENTS_DIR` (default `attachments/`) points the CLI/API at the
      storage directory.
- [x] `web/`: an "Attachments" section on `ExpenseDetailPage.tsx` below
      the line items - a table of uploaded files (name, size, upload
      date) each with View/Download/Delete, reusing the same
      `PdfViewerModal`/object-URL state as the generated-PDF "View"/
      "Download" buttons above it, plus an upload form
      (`<input type="file" accept="application/pdf">`). `api.ts` gained a
      dedicated `uploadFile()` helper (multipart, not the shared
      JSON-only `request()`).
- [x] `deploy/`: `nginx-invoice-system.conf`'s `client_max_body_size` set
      to match `MAX_ATTACHMENT_SIZE`; `invoice-system-api.service` gained
      `INVOICE_SYSTEM_ATTACHMENTS_DIR`, a sibling of the two `.db` files
      (not inside `src/`) so `deploy.sh`'s rsync never deletes it on
      redeploy - see `docs/deployment.md`'s new "Where uploaded expense
      attachments live" section for the backup implication.
- [x] `demo_data.py` seeds one synthetic PDF attachment (via reportlab,
      generated on the fly) against the first demo expense.
- [x] Full backend (225 tests, 98.05% coverage), frontend (36 unit
      tests), and e2e (45 tests, new attachment specs in
      `expenses.spec.ts`) suites updated and passing.

## Phase 20 — Consolidated storage directory (done)

- [x] `paths.py` (new module): `StoragePaths`, deriving every persistent
      file's location from one base directory (`storage/` by default) -
      `storage/db/invoice_system.db`, `storage/db/auth.db`,
      `storage/attachments/`, and `storage/logs/` (reserved for future
      logging output - nothing writes there yet, kept in the layout so it
      doesn't need a fifth base path bolted on later). A CLI/API
      entry-point concern only - `factory.py`/`auth.py` are unchanged,
      still just taking whatever concrete path they're given.
- [x] `INVOICE_SYSTEM_STORAGE_DIR` (API env var) / `--storage-dir` (CLI
      flag, on the top-level `cli` group) move the whole base directory.
      `INVOICE_SYSTEM_DB`/`INVOICE_SYSTEM_AUTH_DB`/
      `INVOICE_SYSTEM_ATTACHMENTS_DIR` (API) and `--db`/`--attachments-dir`
      (CLI) still exist underneath that as individual overrides, always
      winning over the storage-dir-derived default when set - not a
      breaking replacement, an additional base default. `init-db`'s CLI
      command needed `ctx.meta` (not `ctx.obj`, which stays the
      `Application` every other subcommand already receives via
      `@click.pass_obj`) to reach the resolved `StoragePaths` for its own
      `INVOICE_SYSTEM_AUTH_DB` default.
- [x] Both the `cli` group and the API's `lifespan` only call
      `StoragePaths.ensure_db_dir()` when a derived (non-overridden) path
      is actually about to be used - found the hard way, via a test suite
      that silently littered an empty `storage/db/` into the repo root on
      every CLI invocation before this guard existed, including ones that
      override both `--db` and `--attachments-dir` and never touch the
      derived default at all.
- [x] `web/e2e/start-backend.sh` demonstrates the consolidated layout for
      real: one `INVOICE_SYSTEM_STORAGE_DIR` instead of three separate env
      vars pointed at the same directory by hand.
- [x] `deploy/invoice-system-api.service` now sets one
      `INVOICE_SYSTEM_STORAGE_DIR=/opt/invoice-system/storage` instead of
      three separate `Environment=` lines; `docs/deployment.md`'s "Where
      persistent data lives" section covers the backup implication (one
      directory to back up as a unit, still never touched by
      `deploy.sh`'s rsync).
- [x] Full backend (235 tests, 98.09% coverage) and e2e (45 tests, still
      all passing against the new consolidated layout) suites updated;
      new `tests/test_paths.py` for `StoragePaths` itself.

## Phase 21 — Expense totals on the home dashboard chart (done)

- [x] `ExpenseService.monthly_totals(organisation_id, currency, months=12)`
      - the same trailing-12-months, currency-filtered aggregation as
      `InvoiceService.monthly_totals`, but summing every expense into one
      `total` per month rather than splitting paid/unpaid (an `Expense`
      has no status). New `MonthlyExpenseTotals` model.
- [x] `GET /expenses/monthly-totals` (registered before
      `/expenses/{expense_id}`, same route-ordering reasoning as
      `/invoices/monthly-totals`), CLI `expense monthly-totals --user-id`.
- [x] `web/`: `MonthlyTotalsChart.tsx` gained a third bar series -
      expenses, in red (`--chart-expense`, aliased to the existing
      `--danger` token rather than a new near-duplicate color). Takes the
      invoice and expense monthly reports as two separate props
      (`months`/`expenseMonths`) and matches them up per month by the
      `"YYYY-MM"` key, not array position, since they come from two
      independent API calls that aren't guaranteed to align 1:1 by index.
      `HomePage.tsx` fetches both with their own `useAsync` and only
      renders the chart once both have loaded.
- [x] Full backend (243 tests, 98.14% coverage), frontend (38 unit tests),
      and e2e (46 tests, new expense-chart spec in `home.spec.ts`) suites
      updated and passing.

## Phase 22 — List-page filters and pagination (done)

- [x] `AccountsPage.tsx`'s per-row "New quote" link now renders as a
      `.button` (`className="button"`), matching every other "New X" action
      in the app (`QuotesPage`'s/`AccountDetailPage`'s own "New quote"/"New
      expense") instead of being the one plain text link left over from
      Phase 15.
- [x] `QuotesPage.tsx`/`InvoicesPage.tsx` gained an account-name text filter
      and a status dropdown, both client-side over the already-fetched full
      list (same pattern as `AccountsPage`'s search box) rather than new
      API query params — `quoteMatchesFilters`/`invoiceMatchesFilters`
      (unit-tested, exported the same way `accountMatchesQuery` is).
      `InvoicesPage`'s status dropdown deliberately excludes `overdue` —
      it's presentation-only (see Phase 7/CLAUDE.md) and never actually
      written to `Invoice.status`, so it would only ever match zero rows.
- [x] `AccountsPage.tsx`/`QuotesPage.tsx`/`InvoicesPage.tsx` are now paged
      client-side, 20 rows at a time (`hooks/usePagedList.ts` +
      `components/Pagination.tsx`, shared by all three rather than
      duplicated per page) — filtering first, then paging the filtered
      result, with the current page clamped back into range whenever a
      filter shrinks the list rather than needing an explicit reset. Still
      no `limit`/`offset` on the list endpoints themselves: every list page
      in this app already fetches its full result set up front (small
      account/quote/invoice volumes for a freelancer/small-business tool),
      so pagination only needed to slice what's already in memory.
- [x] `web/e2e/accounts.spec.ts`: two pre-existing tests that asserted a
      specific row was visible on `/accounts` without searching first now
      filter via the search box before asserting — needed once the list
      could paginate a row out of view in a full parallel e2e run (every
      test shares one organisation, see CLAUDE.md's Storage gotcha). New
      test creates 25 accounts to force a second page and exercises
      Previous/Next. `quotes.spec.ts`/`invoices.spec.ts` each gained one
      filter test.
- [x] Full backend (243 tests, 98.14% coverage, unchanged - this phase is
      frontend-only), frontend (46 unit tests), and e2e (49 tests) suites
      updated and passing.

## Phase 23 — Header icon buttons, manual light/dark toggle (done)

- [x] `Layout.tsx`'s "Settings" link is now an icon-only button (a cog,
      `components/icons.tsx`'s `CogIcon`) instead of a text link — `.button
      icon-button`, same brand-filled look as every other "New X" button in
      the app (Phase 22), just square instead of a text pill. Accessible
      name preserved via `aria-label="Settings"` (plus a `title` tooltip),
      so nothing that finds it by role/name broke.
- [x] A second icon button next to it toggles light/dark mode
      (`hooks/useTheme.ts` + `SunIcon`/`MoonIcon`) — shows the *current*
      theme (sun in light mode, moon in dark), `aria-label`/`title`
      describing the action a click takes ("Switch to dark/light mode").
      Falls under the existing `.user-menu button` rule (transparent,
      bordered) that already styled "Log out", so it reads as a lesser
      utility action next to the brand-colored Settings button without a
      new CSS variant.
- [x] No new dependency for the three icons — hand-written inline SVGs
      (stroke-based, 24×24 viewBox, `aria-hidden` on the `<svg>` since the
      wrapping button/link carries the accessible name) rather than pulling
      in an icon library for three glyphs.
- [x] `index.css`'s dark palette, previously only reachable via
      `@media (prefers-color-scheme: dark)`, gained an explicit
      `:root[data-theme="dark"]` override (plus a `:not([data-theme="light"])`
      guard on the media-query block) so a manual choice can override the
      OS setting without losing the no-JS/pre-hydration fallback. `useTheme`
      applies the choice as `document.documentElement.dataset.theme` and
      persists it to `localStorage` (guarded against private-browsing/
      storage-blocked exceptions) — once toggled, it stops following the OS
      setting for that browser, by design.
- [x] New `web/e2e/theme.spec.ts`: toggling flips `data-theme` and survives
      a reload; the icon-only Settings button still navigates to
      `/settings` by its accessible name.
- [x] Full backend (243 tests, 98.14% coverage, unchanged - this phase is
      frontend-only), frontend (46 unit tests), and e2e (51 tests) suites
      updated and passing.

## Phase 24 — Server-side pagination for accounts/quotes/invoices (done)

- [x] Phase 22's pagination/filtering was entirely client-side - fetch
      everything, slice/filter in the browser. Moved to the server instead,
      since that only scales to demo-data-sized organisations:
      `AccountService.list_accounts`/`QuoteService.list_quotes`/
      `InvoiceService.list_invoices` now take `page`/`page_size` (default
      `1`/`20`, capped at `MAX_PAGE_SIZE`=200, `ValidationFailed` outside
      range) and return a new `Page[T]` dataclass (`models.py`) instead of
      a bare list. Filtering moved server-side alongside it, since a "page"
      only means something *after* filtering: `query` (accounts - the same
      multi-field match `accountMatchesQuery` used to do client-side) and
      `account_name`/`status` (quotes/invoices - `account_name` via a SQL
      `JOIN` onto `accounts.business_name`).
- [x] `Repository.list_accounts`/`list_quotes`/`list_invoices` gained
      `limit`/`offset`/filter kwargs and now return `tuple[list[T], int]`
      (rows, total matching count) - `limit=None` skips `LIMIT`/`OFFSET`
      and returns `len(rows)` as the total instead of a second `COUNT`
      query, which is what let `StatsService.get_stats`/
      `InvoiceService.monthly_totals` keep calling the repository directly
      for *every* row, completely unpaginated, unchanged from before.
      Migration 10: five plain `CREATE INDEX` statements
      (`idx_accounts_organisation`, `idx_quotes_organisation_account`/
      `idx_invoices_organisation_account`,
      `idx_quotes_organisation_status`/`idx_invoices_organisation_status`)
      - every one of these list queries filtered by `organisation_id` (and
      optionally `account_id`/`status`) with no supporting index until now.
- [x] `GET /accounts`/`GET /quotes`/`GET /invoices` gained `?page=`/
      `?page_size=` and `?query=` / `?account_name=&status=` respectively,
      and their response shape changed from a bare `list[XOut]` to
      `{items, total}` (`AccountListOut`/`QuoteListOut`/`InvoiceListOut`) -
      a breaking change, acceptable since this repo's own web client and
      CLI are the only consumers. `account list`/`invoice list` (the CLI's
      only two list-style commands - there's no `quote list`) gained
      matching `--page`/`--page-size` options.
- [x] `web/`: `api.ts`'s `listAccounts`/`listQuotes`/`listInvoices` take an
      options object and return a new `PagedResult<T>` (`types.ts`).
      `AccountsPage.tsx`/`QuotesPage.tsx`/`InvoicesPage.tsx` dropped
      `usePagedList` (deleted) and their client-side filter functions
      (`accountMatchesQuery`/`quoteMatchesFilters`/`invoiceMatchesFilters`,
      along with the unit tests that covered them) in favour of passing
      `page`/filters straight into the fetch call; free-text inputs
      (accounts' search box, quotes/invoices' account-name filter) go
      through a new `useDebouncedValue` hook (~300ms) first, so typing
      doesn't fire a request per keystroke - the status dropdown and page
      clicks stay immediate. `Pagination`/`StatusBadge` unchanged.
- [x] Every other caller of `listAccounts`/`listQuotes`/`listInvoices` had
      to move to the new `{items, total}` shape too:
      `AccountDetailPage.tsx`'s three `?account_id=`-scoped sub-lists,
      `HomePage.tsx`'s Overdue/Outstanding sections (now also filtered
      server-side to `status: 'sent'`, since both derived checks require
      it anyway - shrinking "every invoice this organisation has ever
      issued" down to "invoices currently awaiting payment", which stays
      small regardless of total history), and the "select an account"
      dropdowns on `QuoteNewPage.tsx`/`ExpenseNewPage.tsx`. All of these
      request `page_size=200` explicitly - each is inherently bounded (one
      client's history, currently-unpaid invoices, this organisation's own
      account list) rather than something that grows with the
      organisation's total data over time, so 200 is a deliberately
      generous cap, not real pagination; found by an e2e run that hung
      waiting for a `<select>` no longer populated correctly, not by
      review - the fix landed in the same change as the pagination
      migration itself, not a follow-up.
- [x] Full backend (266 tests, 98.22% coverage), frontend (32 unit tests -
      down from 46, since the client-side filter functions and their tests
      were deleted, not just moved), and e2e (51 tests, updated for real
      server pagination rather than client-side slicing) suites updated
      and passing. Manually verified against a running instance
      (`GET /accounts?page=&page_size=`, `GET
      /quotes?status=&account_name=&page=&page_size=`) before wiring the
      frontend up, per the plan's verification step.
- [x] Follow-up: shipping server-side pagination didn't automatically make
      the demo instance *show* it - the original demo dataset (5 accounts,
      14 curated quote/invoice scenarios) never crossed the 20-row page
      size, so pagination stayed invisible outside e2e (which builds its
      own bulk data per test). `demo_data.py`'s `_filler_accounts()` adds
      20 more accounts (25 total) and `_FILLER_INVOICE_TYPES` adds one
      more invoice-producing scenario per filler account (34 quotes/28
      invoices total) - enumerated combinations of a name/location/contact,
      not randomly generated, so re-running `init-db` still seeds
      byte-for-byte the same data. The filler scenarios deliberately only
      use draft/paid/void outcomes, not overdue/outstanding - those two are
      timing-sensitive against `months_ago`, and the fourteen curated
      scenarios already guarantee at least one of each without needing to
      re-derive that timing math for twenty more. Verified against a
      running instance (`GET /accounts|quotes|invoices?page_size=1` →
      `total` 25/34/28); full backend suite (266 tests, 98.24% coverage,
      100% on `demo_data.py`) still passing.

## Phase 25 — Invite-gated public registration (done)

- [x] Until now there was no public signup at all - a login could only be
      created via the bundled `sessionkit` CLI. Added a narrow, controlled
      exception: `RegistrationInvite` (models.py) - a single-use, 7-day-
      expiring UUID4 token, stored in `invoice_system.db` (migration 11,
      `registration_invites` - plain `CREATE TABLE`, no rebuild needed).
      Deliberately not tied to a specific email or an `Organisation` -
      whoever holds a valid token can register with any email, and their
      own `Organisation` is created lazily on first login exactly like
      every other user.
- [x] `RegistrationInviteService` (`core.py`, wired into `Application` via
      `factory.py` like every other service) manages the token itself and
      - per the architecture rules - never imports `sessionkit`:
      `create_invite`/`check_invite`/`consume_invite`. `check_invite`/
      `consume_invite` raise the same `NotFound` for an unknown, expired,
      *or already-used* token, deliberately, so neither the API nor an
      attacker probing tokens can tell which. `SqliteRepository.
      consume_registration_invite` is a single locked `UPDATE ... WHERE
      used_at IS NULL` - the same atomic check-then-claim shape as
      `add_organisation_member`'s documented race fix - covered by a
      dedicated test that monkeypatches the repository to simulate a
      concurrent winner, not just the common single-request case.
- [x] `api/auth.py` (the one place that actually calls
      `sessionkit.AuthService.create_user`) gained `GET
      /auth/register/validate` and `POST /auth/register`, both public
      (added to `api/app.py`'s public-routes comment). Registration
      consumes the invite *before* creating the login - if `create_user`
      then fails (409 duplicate email, 422 short password), the invite is
      burned but two concurrent submissions of the same token can never
      both succeed. No auto-login on success (no token in the response) -
      matches the decision to redirect to `/login` instead. `api/auth.py`
      defines its own trivial `get_application` dependency rather than
      importing `api/app.py`'s, to avoid a circular import (`api/app.py`
      imports `public_router`/`protected_router` from `api/auth.py`).
- [x] CLI: `invoice-system-cli invite create [--expires-in-days N]`
      (default 7) - the **only** way to create an invite, matching the
      "no unconditional public signup" posture; prints the token and a
      relative `/register?token=...` link.
- [x] `web/`: new `RegisterPage.tsx` (route `/register`, a public sibling
      of `/login`, not behind `ProtectedRoute`) - reads `?token=`, checks
      it via `GET /auth/register/validate` on mount (shows an invalid-link
      message immediately if there's no token or the check fails, rather
      than only at submit time), then an email/password(+confirm,
      client-side only) form; redirects to `/login` on success. Styled
      with `LoginPage.tsx`'s existing `login-page`/`login-form` classes -
      no new CSS.
- [x] Since invite creation is deliberately CLI-only with no API route,
      `web/e2e/fixtures.ts`'s new `inviteToken` fixture shells out to the
      real CLI (`uv run invoice-system-cli --storage-dir <same .tmp
      start-backend.sh uses> invite create`) and parses the token from
      stdout - the same "set up state the HTTP API doesn't expose"
      pattern `start-backend.sh` itself already uses for the e2e login
      user. New `register.spec.ts`: no token / an unknown token / an
      already-consumed token all show the same invalid-link message;
      mismatched passwords are caught client-side; a full register →
      redirect-to-login → log-in-with-new-credentials loop works.
- [x] Full backend (285 tests, 98.25% coverage), frontend (32 unit tests,
      unchanged - no new pure client-side logic to unit-test), and e2e
      (56 tests) suites updated and passing; `tests/api/test_routes.py`'s
      `client` fixture was split to expose the underlying `application`
      object too, since setting up an invite for a test means calling
      `application.registration_invites.create_invite(...)` directly
      (there's no HTTP route to do it). Manually verified against a
      running instance (`invoice-system-cli invite create`, then the
      no-token/invalid-token/valid-token-and-submit/reused-token cases)
      before trusting the e2e coverage alone.

## Phase 26 — PDF layout: Bill to beside From, bank details on invoices (done)

- [x] "Bill to" no longer stacks below "From" on generated PDFs - when a
      business profile with a name is set, `pdf.py`'s `_render()` now
      lays the two out as a single-row, two-column `Table` (each side's
      `Paragraph`s as a cell's flowable list, not text - platypus table
      cells accept either), From on the left where it's always been, Bill
      to alongside it on the right. With no business profile set, Bill to
      just stays exactly where it was before this change - top-left,
      right after the title/dates - since there's nothing to sit it
      beside.
- [x] `bank_account_name`/`bank_sort_code`/`bank_account_number` - set in
      Settings but never rendered anywhere until now - appear as a new
      "Payment details" section, after the totals table and before the
      document footer, on **invoices only** (`pdf.py`'s new
      `bank_details_lines()`, wired in via `_render()`'s new
      `show_bank_details` param - `render_invoice_pdf` is the only caller
      that sets it `True`; quotes and expenses are unaffected - there's
      nothing to pay yet against a quote, and an expense is money already
      spent, not billed to the account). Whichever of the three fields
      are actually set is what prints, same "print what's there" pattern
      as `business_profile_lines`/`account_address_lines`.
- [x] Full backend suite (292 tests, 98.31% coverage, 100% on `pdf.py`)
      updated and passing; visually verified by rendering a real demo
      invoice PDF via the CLI and reading it back.

## Phase 27 — Per-document-type header/footer, tabbed Settings page (done)

- [x] `BusinessProfile.document_header`/`document_footer` was one shared
      pair used on every quote/invoice/expense PDF alike - split into
      three independent pairs (`quote_document_header`/
      `quote_document_footer`, `invoice_document_header`/
      `invoice_document_footer`, `expense_document_header`/
      `expense_document_footer`) so each document type can say something
      different (e.g. a quote footer noting a 30-day validity window, an
      invoice footer giving payment terms, an expense footer noting it's
      for internal accounting only - the demo data now shows all three
      genuinely differing, not the same string copied three times).
      Migration 12: `ADD COLUMN` × 6 for the new fields, an `UPDATE`
      copying the one old value into all three new header columns and all
      three new footer columns (existing content preserved, not dropped),
      then `DROP COLUMN` × 2 for the old fields - same shape as migration
      5's `accounts.address` split.
- [x] `pdf.py`: `document_header_lines`/`document_footer_lines` (one
      shared field) replaced by `quote_header_lines`/`quote_footer_lines`
      and `invoice_`/`expense_` equivalents (six small pure functions,
      same unit-testable pattern as `business_profile_lines`/
      `bank_details_lines`). `_render()` no longer decides which field to
      read itself - it takes plain `header_lines`/`footer_lines` params,
      and `render_quote_pdf`/`render_invoice_pdf`/`render_expense_pdf`
      each compute theirs from their own pair before calling it, the same
      "caller decides what's type-specific" split Phase 26's
      `show_bank_details` already established.
- [x] `api/schemas.py`, `cli/main.py` (`settings show`/`set` - the CLI's
      `--document-header`/`--document-footer` became
      `--quote-header`/`--quote-footer`/`--invoice-header`/
      `--invoice-footer`/`--expense-header`/`--expense-footer`),
      `demo_data.py`, `web/src/types.ts`/`api.ts` all updated mechanically
      for the six-field shape.
- [x] `web/src/pages/SettingsPage.tsx`: the four `<fieldset>` sections
      (user/business/payment and tax/document settings) became actual
      tabs - a `role="tablist"` of four `role="tab"` buttons driving one
      `activeTab` state, each tab's content in a `role="tabpanel"` using
      the native `hidden` attribute (not conditional unmounting, so
      switching tabs never loses in-progress edits in another tab) with a
      single "Save settings" button always visible below the tabpanels,
      not per-tab - the required fields (first/last/business name) span
      tabs, so a per-tab independent save couldn't validate on its own
      even if built. Each tab's original `<fieldset>/<legend>` moved
      inside its tabpanel unchanged, preserving the existing `getByRole('group',
      { name: ... })` accessible-grouping e2e already relied on; the
      Document tab additionally nests three `<fieldset>/<legend>`
      sub-groups (Quotes/Invoices/Expenses, `.form-subsection` CSS), one
      per header/footer pair. New `.settings-tabs` CSS, same visual
      language as the main nav's active-link underline.
- [x] `web/e2e/settings.spec.ts` rewritten throughout: every test that
      touches fields from more than one section now clicks that section's
      tab first (fields inside a `hidden` tabpanel aren't visible, so
      Playwright's `.fill()` can't reach them without it); the first test
      now clicks through all four tabs asserting each becomes visible
      while the others go `not.toBeVisible()`, rather than asserting all
      four visible at once.
- [x] Full backend (293 tests, 98.33% coverage, 100% on `pdf.py`), frontend
      (32 unit tests, build/lint clean), and e2e (56 tests, settings.spec.ts
      additionally stress-tested with `--repeat-each=3 --workers=1` per
      its documented shared-singleton-profile race history) suites updated
      and passing. Manually rendered a quote, invoice, and expense PDF
      from the same demo profile via the CLI and confirmed each shows its
      own distinct header/footer text (and only the invoice shows bank
      details).

## Phase 28 — PDF line item description word-wrap + XML-escaping fix (done)

- [x] A long line item description (e.g. "Domain Registration -
      example.co.uk") overflowed the "Description" column into "Qty"
      instead of wrapping - reported from a real generated PDF, not just
      reasoning about it. `pdf.py`'s line items table now puts each
      description in a `Paragraph` (`_render()`) instead of a plain
      string - platypus wraps `Paragraph` content to the cell's width
      automatically and grows the row height to fit, where a plain string
      just draws past the column boundary. Added `VALIGN: TOP` to the
      table style so a wrapped multi-line description doesn't sit oddly
      against its row's single-line Qty/price/VAT/Total cells.
- [x] Wrapping free text in a `Paragraph` surfaced a latent, pre-existing
      bug the same fix had to guard against: reportlab's `Paragraph`
      interprets a small subset of HTML-like markup in its text, so
      unescaped user-authored text containing something that looks like
      an unclosed tag (confirmed by hand: a description mentioning
      `<br>`, or any unmatched `<...>`) crashes `doc.build()` outright
      with a `ValueError` - not a hypothetical, a real crash on plausible
      input (pasted-from-HTML text, or just typing `<` informally). New
      `pdf.py` helper `_text_paragraph()` (`Paragraph(escape(text),
      style)`) replaces every direct `Paragraph(...)` call across
      `_render()` that wraps free text originating from an account,
      business profile, or line item - not just the new description
      column - since they all shared the same unescaped-input risk once
      any one of them started going through `Paragraph`.
- [x] Full backend suite (295 tests, 98.33% coverage, 100% on `pdf.py`)
      updated and passing, including a new regression test using the
      exact confirmed-to-crash-pre-fix input. Manually reproduced the
      originally reported scenario (a domain-registration line item) via
      the CLI and confirmed it now wraps onto two lines within its column
      instead of overflowing.

## Phase 29 — "View invoice" link on a converted quote (done)

- [x] `QuoteDetailPage.tsx`'s "Convert to invoice" action already
      redirected straight to the new invoice at conversion time, but a
      converted quote visited later (from the quotes list, an account's
      detail page, etc.) had no way back to the invoice it became - no
      button, and no data to link one even if there were, since `Quote`
      stores no reverse `invoice_id`.
- [x] Rather than add a redundant, dual-write `invoice_id` field on
      `Quote` (a quote converts to at most one invoice, and
      `Invoice.quote_id` already records that relationship the other way),
      `InvoiceService.list_invoices` gained a `quote_id` filter -
      `Repository.list_invoices`/`SqliteRepository` down to `api/app.py`'s
      `GET /invoices?quote_id=`, the exact same "add a filter param"
      pattern as the existing `account_id`/`account_name`/`status`
      filters. Migration 13 added `idx_invoices_organisation_quote`,
      matching the "index every filter column list_invoices actually
      uses" precedent from Phase 24's pagination work.
- [x] `QuoteDetailPage.tsx` now fetches `api.listInvoices({ quoteId:
      quote.id, pageSize: 1 })` once a quote's status is `converted`, and
      shows a "View invoice" button alongside the existing PDF/Send/
      Convert actions when that lookup finds one.
- [x] Full backend (296 tests, 98.34% coverage) and e2e (57 tests,
      including a new test that navigates away from a just-converted
      quote and back before clicking "View invoice", not just checking
      the one-time post-conversion redirect) suites updated and passing.

## Phase 30 — HTML/CSS PDF rendering (WeasyPrint) + a configurable accent colour (done)

- [x] Compared the existing reportlab/platypus PDF output against a rough
      HTML/CSS mockup (logo mark, rounded status pill, alternating row
      shading, a tinted totals row) and preferred the HTML/CSS look -
      that styling isn't realistically achievable in platypus's
      flowable/table model, so `pdf.py`'s rendering *engine* was replaced
      wholesale: Jinja2 builds the HTML (`templates/document.html.jinja`,
      one shared template for quote/invoice/expense, mirroring `_render`'s
      existing "one function, three thin callers" shape), and
      [WeasyPrint](https://weasyprint.org/) turns that HTML/CSS into PDF
      bytes. `_render()`'s own signature is unchanged -
      `render_quote_pdf`/`render_invoice_pdf`/`render_expense_pdf` didn't
      need to change at all, and neither did the pure line-selection
      helpers (`business_profile_lines`/`account_address_lines`/
      `bank_details_lines`/the six header/footer functions) - only what
      `_render` does internally swapped engines.
- [x] `BusinessProfile` gained `accent_color` (migration 14, a nullable
      `#RRGGBB` hex string) - one shared brand colour across every
      quote/invoice/expense PDF a user generates (not a third
      per-document-type triple like the header/footer pairs - "this
      business's colour" doesn't vary by document type), surfaced as a
      colour-picker-plus-text-input pair on the Settings page's existing
      Document tab, above the Quotes/Invoices/Expenses sub-groups since
      it's shared across all three. Falls back to a fixed neutral
      constant when unset, so a PDF still looks finished before anyone
      visits Settings.
- [x] `accent_color` is the one `BusinessProfile` field whose format is
      actually validated (`^#[0-9a-fA-F]{6}$`, `ValidationFailed`
      otherwise) rather than accepted as free-form text like every other
      optional field on that model - it's interpolated directly into a
      CSS declaration in the rendered template rather than shown as
      escaped body text, so a malformed value is a real injection
      boundary, not just a cosmetic format check.
- [x] Jinja2's `autoescape=True` replaces `pdf.py`'s old hand-rolled
      `xml.sax.saxutils.escape()` helper (from the Phase 28 word-wrap fix)
      entirely - every free-text value flowing into the template is
      HTML-escaped automatically, with nothing bespoke left to remember
      to call per value. `weasyprint.HTML(string=html, base_url=None)` is
      deliberate too: with no filesystem/network base to resolve a
      `url()`/`<img src>` against, and the template itself never emitting
      one (no logo in this scope), external resource fetching is switched
      off entirely rather than merely unexploited.
- [x] WeasyPrint needs native system libraries (Pango/HarfBuzz), not just
      a `uv sync`-able package - added an `apt-get install` step to both
      the `backend` and `e2e` GitHub Actions CI jobs, and documented the
      equivalent one-time `apt-get install` for the Jenkins agent and the
      Proxmox LXC deploy target (`docs/deployment.md`'s "WeasyPrint's
      native dependency" section).
- [x] Full backend suite (308 tests, 98%+ coverage, 100% on `pdf.py`) and
      full e2e suite (57 tests, including the existing settings.spec.ts
      coverage extended to the new colour field) updated and passing;
      confirmed via `uv build` that the new template file is actually
      included in the built wheel.

## Phase 31 — Domains on an account (done)

- [x] This app is primarily used for web development client work, and an
      `Account` commonly owns one or more domains - previously that had
      nowhere to live beyond an `Expense`'s free-text description (which
      records money *spent*, not a domain's ongoing identity/expiry/
      registrar). Added a `Domain` entity, scoped to an `Account`: which
      domain, its expiry date, its registrar, and an `auto_renew` flag.
- [x] Structurally closest to `ExpenseAttachment`, not `Expense` - always
      accessed through its parent `Account`, no `organisation_id` column
      of its own (tenant ownership resolved via `AccountService.
      get_account` first). Unlike an attachment, it's user-edited data -
      `DomainService.update_domain` is a full replace, mirroring
      `AccountService.update_account`'s PUT semantics, so a renewal
      (new expiry) or a transfer (new registrar) updates the existing
      record in place rather than requiring delete-and-recreate.
      Migration 15 added the new `domains` table plus
      `idx_domains_account`.
- [x] `domain_name`/`expiry_date`/`registrar` are all required;
      `auto_renew` defaults `false` and is purely informational (nothing
      here talks to a registrar's API). `list_domains` orders
      soonest-expiry-first, not the newest-created-first convention every
      other list in this app uses - "what needs attention soonest" is the
      more useful default for this particular data.
- [x] API: `POST`/`GET /accounts/{id}/domains`, `PUT`/`DELETE
      .../domains/{domain_id}` (no single-`GET` route - list-only, same
      shape as `GET /expenses?account_id=`). CLI: `domain
      create/list/update/delete`, same `--user-id`/`--account-id` pattern
      as `expense`. Web UI: a "Domains" section on `AccountDetailPage.tsx`
      - an inline "Add domain" toggle plus per-row Edit/Delete, both
      backed by a new `components/DomainForm.tsx` sharing `AccountForm.
      tsx`'s exact prop shape (`initial`/`submitLabel`/`onSubmit`/
      `onDone`/`onCancel`) so the same component serves both add and
      in-place edit - no separate `/domains/:id` route, since a domain has
      no sub-resources or PDF of its own to justify one.
- [x] Full backend suite (331 tests, 98%+ coverage) and full e2e suite
      (58 tests, including a new accounts.spec.ts test covering add/edit/
      delete in one flow) updated and passing.

## Phase 32 — Managed domain registrars + a dropdown on the Domain form (done)

- [x] The `Domain` feature (Phase 31) recorded a registrar as free text -
      error-prone for a business managing many domains ("GoDaddy" vs
      "godaddy" vs "Go Daddy"). Added a `Registrar` entity - a managed
      list, editable from a new Settings tab - and changed the Domain
      form's Registrar field from a free-text input to a strict `<select>`
      sourced from that list (no "type a custom value" escape hatch, by
      request).
- [x] `Domain.registrar` deliberately **stays a plain string column, not a
      foreign key** - selecting a registrar submits its name as a string,
      exactly as before. This sidesteps a migration that would need to
      reconcile already-recorded free-text values against a new FK, and
      avoids orphan-handling if a registrar is later renamed/deleted after
      domains already reference it by name. The one consequence: if a
      domain's stored registrar string isn't among the current options
      (recorded before this feature existed, or its registrar was since
      renamed/deleted), the edit form injects it as an extra `<option>` so
      opening "Edit" never silently discards it.
- [x] `Registrar` is organisation-scoped, not account-scoped like `Domain`
      - it's a business-wide reference list, so it carries its own
      `organisation_id`, structurally closest to `Account`. Unlike
      `Account` it supports delete, since nothing holds a foreign key to
      it. Migration 16 added the `registrars` table plus
      `idx_registrars_organisation`. `list_registrars` orders
      alphabetically - the useful default for a dropdown, unlike every
      other `list_*` method's own ordering convention in this app.
- [x] API: `POST`/`GET /registrars`, `PUT`/`DELETE /registrars/{id}` -
      top-level, not nested under `/accounts` like `Domain`, since a
      registrar has no parent. CLI: `registrar create/list/update/delete`.
      Web UI: a fifth Settings tab, "Registrars" - deliberately not a
      fifth `BusinessProfileForm` tabpanel, since its add/edit/delete
      actions are immediate, each its own `<form>`
      (`components/RegistrarForm.tsx`), and nesting a `<form>` inside the
      profile tabs' shared one would be invalid HTML. This meant lifting
      the tab bar/`activeTab` state out of `BusinessProfileForm` and up
      into `SettingsPage` itself, so the Registrars panel could render as
      `BusinessProfileForm`'s sibling (outside its `<form>`) while still
      switching via the same tab bar.
- [x] `DomainForm.tsx` now takes the registrar list as a `registrars` prop
      (fetched once by `AccountDetailPage.tsx`, not per form instance);
      if the list is empty (and there's no existing value to fall back
      to), the field and submit button disable with a hint pointing at
      Settings, rather than presenting a dead-end empty `<select>`.
- [x] Full backend suite (349 tests, 98%+ coverage) and full e2e suite
      (59 tests, including a new settings.spec.ts registrar add/edit/
      delete test and accounts.spec.ts's domain test updated to pick a
      registrar from the dropdown) updated and passing.

## Phase 33 — "Back to account" links + a genuine expense date (done)

- [x] `QuoteDetailPage.tsx`/`InvoiceDetailPage.tsx`/`ExpenseDetailPage.tsx`
      each gained a small "← Back to {account}" link above the page
      header, navigating to `/accounts/{account_id}` - all three already
      fetched the account for their existing meta line, so this just
      reused that. A new `.back-link` style, not squeezed into the
      existing `.page-header` (a two-item `justify-content: space-between`
      row that doesn't have room for a third element).
- [x] `Expense.issue_date` (when the record was created) and the new
      `Expense.expense_date` (when the money was actually spent) now
      answer two different questions - previously conflated into one
      field that was really just "recorded date." `expense_date` defaults
      to today at creation but, unlike every other top-level `Expense`
      field, stays editable afterward
      (`ExpenseService.update_expense_date`, `PUT
      /expenses/{id}/expense-date`, CLI `expense set-date`) - entering a
      receipt today for something bought last week is exactly the case
      this exists for. Migration 17 added the column (same rebuild-free
      `NOT NULL DEFAULT ''` + backfill shape as migration 5's
      `accounts.address_line1` split - every existing expense's own
      `issue_date` is the best available `expense_date`).
- [x] `ExpenseService.monthly_totals` (the home dashboard's chart) now
      buckets by `expense_date`, not `issue_date` - the actual point of
      this phase. A backdated entry now lands in the month it happened,
      not the month it was typed in.
- [x] Web UI: `ExpenseNewPage.tsx` gained an "Expense date" field,
      pre-filled with today's *local* date (deliberately not
      `toISOString()`, which is UTC and can show the wrong calendar date
      near midnight) but still overridable. `ExpenseDetailPage.tsx` shows
      it alongside the existing "recorded {issue_date}" line, with a
      small inline "Edit" toggle - a lightweight toggle rather than the
      heavier `initial`/`onSubmit`/`onDone` form-component pattern
      `DomainForm`/`RegistrarForm` use, since this is the one editable
      field on the page.
- [x] Full backend suite (362 tests, 98%+ coverage, including a dedicated
      migration 17 frozen-schema backfill test and a regression test
      proving `monthly_totals` follows `expense_date` even when
      `issue_date` falls in a different month) and full e2e suite (60
      tests, including a new expenses.spec.ts test covering both the
      create-time date and the in-place edit) updated and passing.

## Phase 34 — Quote/invoice audit trail + issue-date-driven expiry/due dates (done)

- [x] New `ActivityEvent` model (`models.py`) - creation and status changes
      only, not every field edit - shared between `Quote` and `Invoice`,
      persisted into two new tables (`quote_events`/`invoice_events`,
      migration 18) via the same "one shape, two parent tables" pattern
      `LineItem` already establishes. `QuoteService`/`InvoiceService` each
      record one on every create/`send`/status-transition/`void`/`pay`/
      `convert_to_invoice` call, then re-fetch the full entity so the
      caller sees the just-recorded event without a second round-trip
      (same "insert child row, then re-fetch parent" shape
      `add_line_item` already used). Fetched newest-first via `ORDER BY
      rowid`, not `occurred_at` - the latter can tie under a fake/frozen
      test clock.
- [x] Web UI: a new `ActivityTimeline.tsx` component renders that trail as
      an "Activity" section at the bottom of `QuoteDetailPage.tsx`/
      `InvoiceDetailPage.tsx`, below the PDF viewer - the API already
      returns events newest-first, so no client-side sort.
- [x] `Quote.expiry_date` is no longer an independently-settable raw
      field - `QuoteService.create_quote` now takes an optional
      `issue_date` (defaults to today) and computes `expiry_date` as
      `issue_date + BusinessProfile.quote_validity_days`, a new
      per-business setting (migration 19, mirroring `payment_terms_days`
      exactly) exposed on the Settings page's "Payment and tax" tab.
      `QuoteNewPage.tsx` gained an "Issue date" field, pre-filled with
      today's local date via a `todayLocalDate()` helper lifted out of
      `ExpenseNewPage.tsx` into a shared `web/src/dates.ts` (Phase 33
      introduced the original, expense-only copy).
- [x] `QuoteService.convert_to_invoice` also takes an optional
      `issue_date` (defaults to today), letting the resulting invoice be
      backdated - the only place an `Invoice.issue_date` is ever set,
      since there's no standalone "create invoice" route/command.
      `QuoteDetailPage.tsx`'s "Convert to invoice" button gained an
      inline, optional date input for this.
- [x] `InvoiceService.send()`'s due-date calculation changed from
      `today + payment_terms_days` to `invoice.issue_date +
      payment_terms_days` - the actual point of the backdating feature
      above; without this fix a backdated invoice would still get a due
      date computed from today.
- [x] Full backend suite (375 tests, 98%+ coverage) and full e2e suite (63
      tests, including new quotes.spec.ts/invoices.spec.ts coverage for
      the issue-date field, the activity timeline, and backdated
      conversion) updated and passing.

## Phase 35 — Mobile-friendly web client (done)

- [x] `web/` had no responsive CSS at all before this - a single
      `@media (max-width: 640px)` block added to `index.css` covers the
      header/nav, every data table, forms/buttons, and the PDF modal.
- [x] `components/Layout.tsx` gained a hamburger toggle (`MenuIcon`/
      `CloseIcon`, new in `components/icons.tsx`) that collapses the nav
      links + theme toggle + settings + email + log out into a dropdown
      `.app-nav-drawer` below 640px - `display: contents` on desktop keeps
      it invisible in the box tree, unchanged from before. Every nav
      link/log-out action closes the drawer on click so it doesn't get
      stuck open across navigation.
- [x] Every `<table>` in the app (list pages, account-detail sub-lists,
      home dashboard, line items, expense attachments, registrars) is now
      wrapped in a new `.table-scroll` container - columns/markup
      unchanged, the wrapper just lets a table overflow and scroll
      horizontally instead of squashing or breaking the page layout.
- [x] Found and fixed a real bug during manual mobile-viewport
      verification: the Settings page's five-tab bar had no wrap/scroll
      handling and was forcing the *entire page* to overflow horizontally
      at phone widths - fixed by applying the same horizontal-scroll
      pattern to `.settings-tabs`.
- [x] Verified via `tsc`, lint, the full frontend unit/e2e suites (desktop
      viewport, unchanged pass rate), and a manual Playwright screenshot
      pass at a 390×844 viewport across Home/Accounts/Quote
      detail/Settings/the PDF modal.

## Phase 36 — Editable/removable expense line items (done)

- [x] Unlike `Quote`/`Invoice` (line items add-only, frozen by `send()`),
      an `Expense` has no draft/sent lifecycle to justify that freeze, so
      a mis-entered line item can now be fixed or removed directly -
      `ExpenseService.update_line_item`/`delete_line_item` (`core.py`),
      each fetching the expense, resolving the target item via a new
      private `_get_line_item` helper (`NotFound` if it isn't one of the
      expense's own items), mutating, and re-fetching - the same shape
      every other expense mutation here already uses.
      `update_line_item` re-validates `description`/`tax_rate` exactly
      like `add_line_item` and keeps the item's existing `id`/`position`.
- [x] `PUT`/`DELETE /expenses/{id}/line-items/{item_id}` (the delete route
      returns the updated `ExpenseOut`, not `204`, so the caller gets
      recomputed totals without a second request); CLI `expense
      update-item`/`delete-item`. `expense add-item` now echoes the new
      item's id (`Added line item <id>`) - needed to target a later
      update/delete, and the only expense `add-*` command that does.
- [x] Web UI: `components/LineItemsTable.tsx` (shared by Quote/Invoice/
      Expense detail pages) gained optional `onEdit`/`onDelete` props -
      only `ExpenseDetailPage.tsx` passes them, so Quote/Invoice line
      items keep rendering with no actions column at all. Its add-item
      form (`LineItemForm`) now also edits: a row's "Edit" button sets an
      `editingItem` state that pre-fills the form (via a `key` prop change
      that remounts it) and relabels the submit button "Update item"; a
      "Cancel" button (visible only while editing) discards the in-
      progress edit.
- [x] Full backend suite (390 tests, 98%+ coverage) and full e2e suite (66
      tests, including new expenses.spec.ts coverage for editing,
      cancelling an edit, and deleting a line item) updated and passing.

## Phase 37 — Configurable document number prefix/digits + "set next number" (done)

- [x] `Quote.number`/`Invoice.number`/`Expense.number` were always
      `Q-0001`/`INV-0001`/`EXP-0001` - a hardcoded prefix and 4-digit
      zero-pad baked into `SqliteRepository._next_number`. Now each is
      independently configurable per business, alongside the existing
      per-document-type header/footer fields: `quote_number_prefix`/
      `quote_number_digits`, `invoice_number_prefix`/
      `invoice_number_digits`, `expense_number_prefix`/
      `expense_number_digits` on `BusinessProfile` (migration 20 - see
      `docs/data-model.md`), only affecting numbers assigned from then on,
      never rewriting an already-issued one.
- [x] A separate "set next number" action per document type -
      `QuoteService.set_next_number`/`InvoiceService.set_next_number`/
      `ExpenseService.set_next_number` (`ValidationFailed` if
      `next_number < 1`), backed by a new `_set_next_number` on
      `SqliteRepository` that writes `next_number - 1` into the same
      `counters` table `_next_number` already uses. Confirmed with the
      user before building this: it's a one-time **jump**, not a
      persisted additive offset - "start at 67" means the very next
      document is `67` regardless of how many already exist, which only a
      direct counter-set achieves. `POST /quotes|invoices|expenses/
      next-number` (`204`), CLI `quote|invoice|expense set-next-number
      --next-number N`.
- [x] `send_quote`/`create_expense` API routes previously didn't resolve
      the caller's business profile at all (only `send_invoice` did, for
      `payment_terms_days`) - both now do, to read the matching
      prefix/digits.
- [x] Web UI: the Settings page's Document tab's three per-document-type
      sub-groups (Quotes/Invoices/Expenses) each gained a "Number prefix"/
      "Number digits" field pair (saved by the normal "Save settings"
      button) plus a separate, immediately-submitted "Next number" action
      (`NextNumberAction` in `SettingsPage.tsx` - a plain `<div>`, not a
      nested `<form>`, since it already sits inside
      `BusinessProfileForm`'s own form) with its own busy/error/success
      state.
- [x] Full backend suite (414 tests, 98%+ coverage) and e2e coverage in
      `settings.spec.ts` (the new prefix/digits fields save and reload,
      then reset back to the app's own defaults before the test ends -
      needed because `quotes.spec.ts`/`invoices.spec.ts`/
      `expenses.spec.ts` run concurrently with this file, not just within
      it - see below; a dedicated "set next number" test that resets to
      known defaults first, jumps to one past whatever the highest
      existing quote number already is (not a fixed constant, which
      collides with itself on a second local run against the same
      persisted demo database - see `CLAUDE.md`), and asserts the result
      is `>=` that rather than an exact match).
      Deliberately **did not** add live "custom prefix produces this exact
      number" e2e tests to `quotes.spec.ts`/`invoices.spec.ts`/
      `expenses.spec.ts` as originally planned - instead, running the
      full suite fresh surfaced that those files' own *pre-existing*
      tests (asserting an exact default-format `^Q-\d{4}$`/`^INV-\d{4}$`/
      `^EXP-\d{4}$` number) could actually fail against a concurrently-
      running `settings.spec.ts` worker, since the prefix is now a shared
      mutable field - not a hypothetical risk, an observed failure. Fixed
      by loosening those exact assertions to `/^\S+-\d+$/` (a number was
      assigned, not which format it's in), same "Deliberately not exact"
      reasoning `home.spec.ts`'s monthly chart already established for
      the reporting-currency race, now extended to this field - see
      `CLAUDE.md`. Custom-prefix-produces-this-string coverage stays in
      the backend/API/CLI test suites, which don't share mutable state
      across tests.

## Phase 38 — `init-db --reset` (done)

- [x] `invoice-system-cli init-db --reset` deletes the domain database
      file (accounts/quotes/invoices/expenses/business profiles/
      organisations/counters) and every uploaded expense-attachment PDF,
      then reinitialises from scratch - a clean slate without hand-deleting
      files. Deliberately leaves `auth.db` untouched (confirmed with the
      user before building this: resetting domain data shouldn't also log
      everyone out or force recreating logins) - if the demo login already
      exists there, its domain data is reseeded for that existing login
      rather than a duplicate attempt silently no-op-ing (see the
      `seed_demo_data` fix below). Irreversible, so it prompts for
      confirmation (`click.confirm`) unless `--yes`/`-y` is also passed,
      for scripted/non-interactive use.
- [x] Implementation note: the `cli` group's own callback already opens
      (and migrates) a `SqliteRepository` connection against the domain db
      *before* `init-db`'s own body runs, so `--reset` has to close that
      connection, delete the file/attachments directory, and rebuild a
      fresh `Application` against the same resolved paths (now stashed in
      `ctx.meta` from the `cli` group) - not something `init-db`'s body
      could do to an already-open connection.
- [x] Found and fixed a real bug while building this, not just a
      CLI-layer concern: `seed_demo_data`'s idempotency check only tested
      whether the demo login already existed in `auth.db`
      (`DuplicateUser`). Since `--reset` deliberately keeps `auth.db`, the
      demo login survives a reset - so the old check would hit
      `DuplicateUser` and bail out immediately, leaving a login that could
      authenticate but see zero domain data. Fixed by additionally
      checking `application.repository.get_organisation_id_for_user(user.id)`
      on a `DuplicateUser` and falling through to seed fresh domain data
      when that comes back `None` (this database has never seen this
      user) rather than returning `False` - a more correct idempotency
      check in general ("has *this* database already been seeded for this
      user"), which keeps the existing `test_seed_demo_data_is_idempotent`
      passing unchanged.
- [x] `tests/cli/test_cli.py` (reset wipes domain data/attachments but
      keeps the login; reset + demo reseeds domain data for the existing
      login; declining the confirmation prompt aborts without deleting
      anything), `tests/test_demo_data.py` (reseeding for an existing
      login against a fresh domain database). Full backend suite (418
      tests, 98.6%+ coverage), ruff clean.

## Fixed — Settings page silently failed to save with a blank field on a hidden tab

- [x] Surfaced by a real user report right after using `init-db --reset`
      (Phase 38 above): `init-db --reset` produces a genuinely blank
      `first_name`/`last_name`/`business_name`, and opening Settings on
      any tab other than the one holding the blank field made "Save
      settings" silently do nothing - no error, no request sent, just
      "An invalid form control with name='' is not focusable" in the
      browser console. Root cause predates `--reset` itself: every
      profile field submits through one shared `<form>` (see
      `SettingsPage.tsx`'s tabs Convention in `CLAUDE.md`), and several
      fields carried the native HTML `required` attribute - when one of
      those sits on a tab hidden via the `hidden` attribute, Chrome's
      constraint validation tries to focus it on submit, can't, and
      aborts the whole submission with no visible feedback.
- [x] Fixed by removing `required` from every field in the form
      (`first_name`/`last_name`/`business_name`/`payment_terms_days`/
      `quote_validity_days`/`currency`/`quote_number_digits`/
      `invoice_number_digits`/`expense_number_digits`) - safe because the
      server already independently validates all of them
      (`BusinessProfileService.save_profile`) and the page already
      surfaces that error inline; the browser's native validation was
      redundant *and* actively broken for a multi-tab single-form layout.
- [x] New e2e regression test in `settings.spec.ts`: blank a field, switch
      to a different tab, submit, and assert a real validation error
      appears (not a silent no-op) - reproduces the exact failure mode.
      Full e2e suite (68 tests) and frontend checks (tsc/lint/unit/build)
      all pass.

## Fixed — settings page tabs couldn't actually be saved independently

- [x] Follow-up to the fix above, from a second real user report: even
      with the native-`required`/hidden-tab-focus bug fixed, the settings
      page still couldn't save one tab without the *other* tabs already
      being filled in - filling in User first demanded Business already
      be set, and vice versa. Root cause: `first_name`/`last_name`/
      `business_name` were the only three `BusinessProfile` fields
      validated as non-blank with **no sensible default** to fall back to
      (`payment_terms_days`/`quote_validity_days`/`currency`/the three
      `*_number_digits` fields are also required, but each already has a
      real default constant, so their form state is never genuinely
      blank even on a brand-new profile - only these three ever actually
      trip this). Since the settings page is one shared full-profile
      `PUT` across all four tabs (see `CLAUDE.md`), a first-time user
      filling in just one tab left these three still blank in the
      request body, and the server rejected it outright.
- [x] Fixed by dropping the non-blank validation for these three fields
      entirely (`BusinessProfileService.save_profile`) - blank is now
      accepted and stored as `""` (staying a plain `str`, not normalised
      to `None` like other optional fields, since nothing downstream
      needs to tell "never set" apart from "set to blank" -
      `pdf.py`'s `business_profile_lines()` already just checks
      non-blank either way, and neither `first_name` nor `last_name` is
      ever shown on a PDF at all). `BusinessProfileIn`'s API schema
      gained matching `""` defaults so a `PUT` can omit them entirely
      too, not just send `""` explicitly. The CLI's `settings set
      --first-name`/`--last-name`/`--business-name` stay **required
      options** deliberately (unlike the web form, a CLI invocation has
      no memory of previously-saved values - a full-replace command that
      silently defaulted an omitted flag to blank would blank out
      already-saved data instead of just accepting an explicitly blank
      value).
- [x] Backend tests updated to assert blank is *accepted* rather than
      rejected (`tests/core/test_business_profile_service.py`,
      `tests/api/test_routes.py`, `tests/cli/test_cli.py`); two new e2e
      tests in `settings.spec.ts` replace the old "rejects a blank
      business name"/"rejects a blank first name" tests - one confirming
      blank values round-trip through a save+reload, one reproducing the
      exact reported bug (fill in Business while User is blank, save,
      switch to an unrelated tab, fill it in, save again - both must
      succeed). Full backend suite (419 tests, 98.6%+ coverage), full
      frontend checks, and full e2e suite (67 tests) all pass, including
      a `--repeat-each=3 --workers=1` stress run of `settings.spec.ts`
      itself (this project's own established way to shake out
      shared-singleton-profile races - see `CLAUDE.md`).

## Fixed — settings page polish + registrar usage/delete-safety (Phase 39)

- [x] The "Saved."/error message on the Settings page (one shared `<form>`
      across all four profile tabs) touched the "Save settings" button
      directly below it with no spacing - `.settings-form > .form-error,
      .settings-form > .form-success { margin-bottom: 0.8rem }` added to
      `index.css` (scoped to direct children of `.settings-form` only, not
      the global `.form-error`/`.form-success` classes used elsewhere).
- [x] That same message used to keep showing after switching to a
      completely different tab, looking like it was about whatever's now
      on screen - `BusinessProfileForm` now clears it in a `useEffect`
      keyed on `activeTab`.
- [x] The Registrars tab - a separate, self-contained list with its own
      immediate add/edit/delete actions, not one of `BusinessProfileForm`'s
      own fields - was still showing that form's trailing "Save settings"
      button and any leftover message below the registrars table, since
      that trailing block sits outside all five tabpanels (so no
      individual tabpanel's own `hidden` attribute covered it). Now
      explicitly hidden while `activeTab === 'Registrars'`.
- [x] Registrars now show how many domains (and, in turn, how many
      distinct accounts) currently name them - `RegistrarUsage`
      (models.py), `RegistrarService.list_registrars_with_usage`/
      `get_registrar_usage`, `SqliteRepository.count_domains_by_registrar`
      (one `GROUP BY domains.registrar` query, joined to `accounts` for
      organisation scoping since `Domain` has no `organisation_id` of its
      own). `GET /registrars` (and the create/update responses) now
      include `domain_count`/`account_count` on every `RegistrarOut`.
      Matched by the registrar's *current* name, so a renamed registrar's
      usage count doesn't include domains that still record its old name
      - a deliberate, accepted tradeoff matching how `DomainForm.tsx`
      already handles registrar-name drift at the UI layer, not a new bug.
- [x] Deleting a registrar that's still in use is now blocked - a new
      `Conflict` exception (`errors.py`, 409) raised by
      `RegistrarService.delete_registrar` when `domain_count > 0`, and the
      web UI disables that row's "Delete" button client-side too (with a
      `title` explaining why) rather than only surfacing the server's
      rejection after a click - both layers guard this independently, the
      same "don't only rely on one" pattern already used for the settings
      page's required-field validation above.
- [x] New tests throughout: `tests/core/test_registrar_service.py`
      (usage counts, per-organisation isolation, name-drift-on-rename,
      delete blocked/then-succeeds-once-clear), `tests/storage/
      test_sqlite_repository.py` (the counting query itself),
      `tests/api/test_routes.py` (counts on every registrar response,
      409 on a blocked delete), `tests/cli/test_cli.py` (`registrar list`
      shows counts too, for CLI/API parity; delete blocked). New
      `web/e2e/settings.spec.ts` tests for the message-clearing fix, the
      Registrars-tab-has-no-Save-button fix, and the domain-count/
      delete-blocked UI behaviour. Full backend suite (430 tests, 98.6%+
      coverage), full frontend checks, and full e2e suite (70 tests) all
      pass, including a `--repeat-each=3 --workers=1` stress run of
      `settings.spec.ts` itself.

## Phase 40 — Domains as a first-class top-level section (done)

- [x] `Domain` moved from "always created through a parent `Account`" to
      a standalone, organisation-scoped resource - structurally the same
      shape as `Registrar` now, plus an *optional* link to one `Account`
      at a time. A domain can exist unlinked (bought speculatively, or
      simply not assigned yet) - confirmed with the user before building
      this, along with the one-account-at-a-time (not many-to-many)
      relationship shape. Migration 21 (rebuild-and-swap): `domains`
      gained its own `organisation_id` (backfilled via a join to each
      domain's existing account) and `account_id` relaxed from `NOT NULL`
      to nullable - see `docs/data-model.md`.
- [x] Linking/unlinking is a dedicated action
      (`DomainService.link_domain`/`unlink_domain`, `POST
      /domains/{id}/link|unlink`, CLI `domain link|unlink`), deliberately
      separate from `update_domain` (which only ever replaces a domain's
      own fields, never its account link) - same "dedicated action, not
      bundled into a general update" shape as `InvoiceService.pay`/`void`
      or `set_next_number` elsewhere in this app. Re-linking an
      already-linked domain to a different account is allowed directly,
      no forced unlink-first step. New `DomainWithAccount` (models.py) -
      every `DomainService` mutation returns a domain alongside its
      linked account's name (or `null`), computed at request time, so the
      UI never needs a second lookup to show the link.
      `count_domains_by_registrar` was simplified as part of the same
      migration - it used to join `domains` to `accounts` purely to
      resolve organisation scoping (the only way to do it before domains
      had their own `organisation_id`), which would have silently
      excluded unlinked domains from `domain_count` too, not just
      `account_count` - filtering directly on the new column fixes that
      before it could ever actually manifest as a bug.
- [x] New standalone `web/src/pages/DomainsPage.tsx` (route `/domains`,
      nav link between Accounts and Quotes) - the central place to manage
      both domains and registrars, two stacked sections on one page (no
      sub-tabs, deliberately - avoids reintroducing the shared-tab-state
      issues just fixed on the Settings page). Registrars moved here from
      the Settings page's old fifth tab entirely.
      `AccountDetailPage.tsx`'s own "Domains" section is now link/unlink
      only (a "Link domain" picker offering currently-unlinked domains,
      same self-contained immediate-action shape as
      `SettingsPage.tsx`'s `NextNumberAction`; each row's only action is
      "Unlink", which clears the link without deleting the domain) - full
      create/edit/delete lives on the Domains page only.
- [x] API routes moved from nested (`/accounts/{id}/domains...`) to
      top-level `/domains` (matching `Registrar`'s existing shape,
      including no single-`GET` route - list is the only read path); CLI
      `domain create`/`domain list` swapped their required `account_id`
      positional argument for an optional `--account-id`.
- [x] Extensive test updates across every layer for the new
      organisation-scoped, link/unlink shape:
      `tests/core/test_domain_service.py` (rewritten - unlinked creation,
      link/re-link/unlink, name-drift), `tests/storage/
      test_sqlite_repository.py` (rewritten CRUD test + a new migration-21
      test building a database frozen at migration 20 and confirming the
      backfill), `tests/api/test_routes.py` and `tests/cli/test_cli.py`
      (new routes/commands, link/unlink flows). New `web/e2e/domains.spec.ts`
      (domain CRUD, registrar CRUD moved here from `settings.spec.ts`,
      the linked-account display); `web/e2e/accounts.spec.ts`'s old
      domain-CRUD test replaced with a link/unlink one;
      `web/e2e/settings.spec.ts` lost its Registrars tab entirely (down
      to four tabs). Full backend suite (442 tests, 98.7%+ coverage),
      full frontend checks, and full e2e suite (71 tests) all pass,
      including a `--repeat-each=3 --workers=1` stress run of
      `domains.spec.ts` itself.
- [x] Found in passing, not fixed (pre-existing, unrelated to this
      phase): `accounts.spec.ts`'s "the search box filters the accounts
      list" test can fail under `--repeat-each --workers=2` stress
      testing - it asserts its own freshly-created account is visible on
      the accounts list's first page *before* searching, which can be
      pushed past page 1 by concurrent bulk account creation from another
      spec's own stress-test repeats. Reproduces with `accounts.spec.ts`
      alone, unrelated to domains/registrars - left as a known gap for a
      future fix, same as the pre-existing `quote_validity_days` cross-test
      leak noted in an earlier phase.

## Phase 41 — Editable/removable draft quote line items + quote details (done)

- [x] Reported as a bug ("can't update quotes that are in a draft
      state") - turned out to be a real gap, not a misunderstanding: a
      draft `Quote`'s line items could only ever be added, never edited
      or removed, and none of the quote's own fields (`currency`/
      `issue_date`) could be changed after creation at all. Confirmed
      scope with the user before building: quote-field editing limited to
      `currency`/`issue_date` (not `account_id` - a quote stays pointed at
      the account it was created for), and line-item edit/delete
      restricted to `draft` only, matching the existing add-line-item
      gate (not extended to `sent`/`accepted` - those stay frozen).
- [x] `QuoteService.update_line_item`/`delete_line_item` (`core.py`) -
      the same "fetch, 404 via a private `_get_line_item` helper if
      `item_id` isn't one of the quote's own items, mutate, re-fetch"
      shape `ExpenseService`'s own line-item mutators already established
      (Phase 36), but gated behind `_get_draft_quote` (the same guard
      `add_line_item` already uses) rather than being unconditional -
      `InvalidTransition` (409) once the quote is no longer `draft`.
      `QuoteService.update_quote(organisation_id, quote_id, *, currency,
      issue_date, quote_validity_days=None)` - also draft-only, full
      replace of just those two fields; `expiry_date` is recomputed from
      the new `issue_date` the same way `create_quote` computes it
      initially, not left stale.
- [x] `PUT /quotes/{id}` and `PUT`/`DELETE /quotes/{id}/line-items/
      {item_id}` (the delete route returns the updated `QuoteOut`, not
      `204`, same pattern as the expense line-item delete route); CLI
      `quote update --currency --issue-date`, `quote update-item`/
      `quote delete-item`. `quote add-item` now also echoes the new
      item's id (`Added line item <id>`) - needed to target a later
      `update-item`/`delete-item`, matching `expense add-item`'s existing
      behaviour (which is no longer the only `add-*` command that does).
- [x] Web UI: `QuoteDetailPage.tsx`'s meta line grows an inline "Edit"
      toggle (shown only while draft) for `currency`/`issue_date`, same
      lightweight local-state pattern as `ExpenseDetailPage.tsx`'s
      expense-date toggle. `LineItemsTable.tsx`'s existing `onEdit`/
      `onDelete` props (added in Phase 36 for `ExpenseDetailPage.tsx`) are
      now also passed by `QuoteDetailPage.tsx`, conditionally on
      `quote.status === 'draft'` (the same condition already gating
      `onAdd`) - the actions column disappears the moment a quote is
      sent. `InvoiceDetailPage.tsx` passes neither, unchanged - an
      `Invoice`'s line items are still only ever populated once, at
      conversion time.
- [x] Full backend suite (462 tests, 98.7%+ coverage) and full e2e suite
      (74 tests) updated and passing, including a
      `--repeat-each=3 --workers` concurrent stress run of
      `quotes.spec.ts` alongside `settings.spec.ts` - caught and fixed a
      real race in the new e2e coverage itself (asserting a fixed 30-day
      default expiry date, when `quote_validity_days` is a shared,
      mutable `BusinessProfile` field a concurrent `settings.spec.ts` run
      can change mid-test - see the "Deliberately not exact" gotcha in
      `CLAUDE.md`). Fixed by reading the profile's current
      `quote_validity_days` right before computing the expected expiry,
      not by asserting the default.

Update the checkboxes and phase status as work lands — this file is read as
ground truth for "what's done," not aspirational copy.
