# Invoice System — web

React + TypeScript + Vite SPA for the backend in `../src/invoice_system/`.
A home dashboard (overdue/outstanding invoices, a monthly paid-vs-outstanding
totals chart, all-time stats), accounts (create/edit), quotes (draft → sent
→ convert to invoice, each line item with its own VAT rate), invoices
(send/void/mark as paid), PDF download, and a settings page for your own
business profile, behind login.

## Develop

```
npm install
npm run dev      # http://localhost:5173, talks to the API at http://127.0.0.1:8000
```

The API base URL is `VITE_API_BASE_URL` (default `http://127.0.0.1:8000`) —
see `.env.example`. Start the backend first (`../docs/development.md`),
which by default seeds a demo login (`demo@example.test` /
`demo-password-123`) plus a year of demo data; there is no signup screen.

`npm run dev:lan` (same as `dev`, plus Vite's `--host`) binds every network
interface instead of just `localhost`, so another device on the same
network can reach it — set `VITE_API_BASE_URL` to this machine's LAN
address first and start the API with `--host 0.0.0.0` too. See
`../docs/development.md` for the full walkthrough and the security caveat.

## Test / build

```
npm test          # vitest - unit tests: api.ts, HomePage's overdue/outstanding logic, MonthlyTotalsChart, a login/routing integration test
npm run test:e2e  # playwright - login/home/accounts/quotes/invoices/settings, one spec each
npm run build     # tsc -b && vite build
```

`test:e2e` needs a Chromium build once: `npx playwright install chromium`.
It's self-contained — `playwright.config.ts`'s `webServer` entries launch a
*throwaway* backend (`e2e/start-backend.sh`: fresh SQLite files under
`e2e/.tmp/`, one seeded login user, `uv run uvicorn ...` on `:8199`) and this
app itself (Vite on `:5199`) before running, and tear both down after — it
never touches your real dev databases or dev-server ports. Needs `uv` on
`PATH` (see `../docs/development.md`) since it shells out to the Python
backend. `npm run test:e2e:ui` opens Playwright's UI mode for debugging a
failure; a failed run's trace/screenshot land in `test-results/` (gitignored).

## Where things are

- `src/api.ts` — the **only** module that talks HTTP to the backend (see
  `CLAUDE.md` at the repo root). Attaches `Authorization: Bearer <token>` to
  every call, throws a typed `ApiError` on failure, and calls a single
  "unauthorized" handler on any 401 so `AuthContext` can react in one place.
- `src/auth/AuthContext.tsx` — owns the token (persisted to `localStorage`)
  and the current user; `useAuth()` everywhere else.
- `src/hooks/useAsync.ts` — the shared "call an async function, track
  loading/error/data" hook every page uses instead of reinventing it.
- `src/components/` — `Layout` (nav + logout), `ProtectedRoute` (redirects
  to `/login`), `StatusBadge`, `LineItemsTable` (shared by quote/invoice
  detail pages; the add-item form, including its VAT-rate `<select>`, only
  renders when its `onAdd` prop is passed, since invoices don't expose that
  route — see `../docs/api.md`; also renders the VAT column and
  Subtotal/VAT/Total footer from the `subtotal`/`taxTotal`/`total` props).
- `src/pages/` — one file per route (`App.tsx` wires them up).
  `HomePage.tsx` exports its `isOverdue`/`isOutstanding` filters (not just
  the component) specifically so `HomePage.test.ts` can unit-test the
  date logic against fixed dates, without a fake clock reaching the e2e
  layer (see the note below on why e2e can't produce a genuinely overdue
  invoice). It also renders `MonthlyTotalsChart` and the "All-time stats"
  section (currently just accounts registered, from `GET /stats`).
  `AccountsPage.tsx`'s `AccountForm` is shared between "New account" and
  per-row "Edit" (a row swaps itself for the form in place on Edit, no
  separate `/accounts/:id` route) - the same fields, same validation,
  differing only in initial values and the submit handler.
- `src/components/MonthlyTotalsChart.tsx` — the home dashboard's paid-vs-
  outstanding bar chart. Plain CSS bars (`<div>`s with a `height: N%`
  inline style), not a charting library — 12 months, two series, doesn't
  need one. `Number()`-parses the decimal-string totals purely to compute
  that percentage; the exact string stays on each bar's `title` attribute
  and is never sent anywhere (see `CLAUDE.md`'s money convention — that
  rule is about not doing stored/round-tripped arithmetic on money, not
  about never computing a display proportion). Unit-tested
  (`MonthlyTotalsChart.test.tsx`) for the scaling math and rendered output.
- `e2e/` — Playwright, one spec file per feature area (`login`, `home`,
  `accounts`, `quotes`, `invoices`, `settings.spec.ts`) rather than one long
  combined flow, so each
  can be read/run/extended on its own as the app grows. `fixtures.ts` is
  what makes that possible: each fixture (`testAccount`, `draftQuote`,
  `sentQuote`, `draftInvoice`, `sentInvoice`, `reportingCurrency`) sets up
  its slice of backend state directly through the API, not the UI, so
  `quotes.spec.ts` isn't the thing that has to create an account first,
  `invoices.spec.ts` isn't the thing that has to drive a quote through
  send-and-convert first, and no spec depends on another one having run —
  safe to run in parallel (29 tests, 6 workers, under 7s) or in any order.
  `home.spec.ts` only checks that a freshly-sent invoice shows up under
  "Outstanding" (not Overdue) — nothing in the app can backdate a
  `due_date` (always computed server-side as today plus a positive
  `payment_terms_days`, see `CLAUDE.md`), so a genuinely overdue invoice
  can't be produced through the API/CLI/UI at all; that half of the
  derivation logic is covered at the unit level instead
  (`src/pages/HomePage.test.ts`). Its monthly-totals-chart test is
  similarly deliberate about what it does and doesn't assert: the chart
  sums invoices **system-wide**, not per-account, so concurrent tests all
  contribute to the same buckets — it checks structure (12 months, a
  currency-shaped group name) and that paying an invoice removes it from
  Outstanding, not exact totals (see `CLAUDE.md`'s "Deliberately not
  exact" gotcha for the specific cross-file currency race this avoids).
  `apiFetch` is exported from `fixtures.ts` for tests that need a one-off
  API call beyond the fixture set (`home.spec.ts` uses it to build an
  invoice in the profile's actual reporting currency).
  Two exceptions to the "safe to run in parallel" claim above, both
  because `BusinessProfile` is a singleton per user (see `CLAUDE.md`), not
  a created-per-test record like an account: `settings.spec.ts` itself —
  its tests share state with each other by nature, each still sets its own
  known values up front rather than asserting anything about "untouched"
  state (found the hard way, by stress-testing with `--repeat-each` before
  trusting it — see the comment at the top of that file) — and
  `home.spec.ts`'s chart test, which reads the *current* reporting
  currency via `reportingCurrency` (a read-only `GET`, never a write, so it
  can't itself race with `settings.spec.ts`) rather than assuming one, and
  only asserts the chart's group name is *some* currency, not a specific
  value. `constants.ts` is where the seeded test user's
  credentials and the two throwaway ports live, imported by both
  `playwright.config.ts` and `fixtures.ts` so there's one source of truth.
  `start-backend.sh` is the throwaway-backend script `playwright.config.ts`
  launches as a `webServer`.

Money stays a string end-to-end, same as the API — it's only ever displayed,
never parsed into a float (see `CLAUDE.md`).
