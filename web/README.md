# Invoice System — web

React + TypeScript + Vite SPA for the backend in `../src/invoice_system/`.
Accounts, quotes (draft → sent → convert to invoice), invoices (send/void),
and PDF download, behind login.

## Develop

```
npm install
npm run dev      # http://localhost:5173, talks to the API at http://127.0.0.1:8000
```

The API base URL is `VITE_API_BASE_URL` (default `http://127.0.0.1:8000`) —
see `.env.example`. Start the backend first (`../docs/development.md`) and
create a login account with `uv run sessionkit add you@example.com` from the
repo root; there is no signup screen.

## Test / build

```
npm test          # vitest - unit tests, api.ts + a login/routing integration test
npm run test:e2e  # playwright - full account -> quote -> invoice browser flow
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
  detail pages; the add-item form only renders when its `onAdd` prop is
  passed, since invoices don't expose that route — see `../docs/api.md`).
- `src/pages/` — one file per route (`App.tsx` wires them up).
- `e2e/` — Playwright smoke test + the throwaway-backend script and shared
  constants it and `playwright.config.ts` both import from
  (`e2e/constants.ts`), so the seeded test user's credentials live in
  exactly one place.

Money stays a string end-to-end, same as the API — it's only ever displayed,
never parsed into a float (see `CLAUDE.md`).
