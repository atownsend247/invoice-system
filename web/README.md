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
npm test          # vitest
npm run build     # tsc -b && vite build
```

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

Money stays a string end-to-end, same as the API — it's only ever displayed,
never parsed into a float (see `CLAUDE.md`).
