# Development

## First run

```
uv sync
uv run invoice-system-cli init-db          # creates invoice_system.db, applies migrations
uv run sessionkit add you@example.com      # creates auth.db, prompts for a password
```

The domain data (accounts/quotes/invoices) and login accounts live in two
separate SQLite files — see `CLAUDE.md`. No signup route; manage login
accounts with the `sessionkit` CLI (`add`, `list`, `passwd`, `delete`,
`2fa-disable` — `uv run sessionkit --help`), not through this app.

## Serve the API

```
uv run uvicorn invoice_system.api.app:app --reload
```

Defaults to `invoice_system.db` / `auth.db` in the working directory;
override with `INVOICE_SYSTEM_DB=/path/to/db.sqlite3` /
`INVOICE_SYSTEM_AUTH_DB=/path/to/auth.sqlite3`. Interactive docs at
`http://127.0.0.1:8000/docs`. Every route except `/healthz` and
`POST /auth/login` needs `Authorization: Bearer <token>` — log in first:

```
curl -s -X POST http://127.0.0.1:8000/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email": "you@example.com", "password": "..."}'
# -> {"token": "...", "expires_at": "...", "user": {...}}
```

## Use the CLI

```
uv run invoice-system-cli --help
uv run invoice-system-cli account create --business-name "Acme Co" \
    --email billing@acme.test --address "1 Main St"
uv run invoice-system-cli quote create --account-id 1
uv run invoice-system-cli quote add-item 1 --description "Design work" \
    --quantity 10 --unit-price 50.00
uv run invoice-system-cli quote send 1
uv run invoice-system-cli quote pdf 1 -o quote.pdf
uv run invoice-system-cli quote convert 1
uv run invoice-system-cli invoice send 1
uv run invoice-system-cli invoice pdf 1 -o invoice.pdf
```

`--db PATH` (before the subcommand) points any command at a different
SQLite file; default is `invoice_system.db` in the working directory. The
CLI is a local, trusted tool and is **not** behind login (unlike the API) —
see `CLAUDE.md`.

## Serve the web client

```
cd web
npm install
npm run dev
```

Requires the Node version pinned in `web/.node-version` (nodenv/similar
picks it up automatically in that directory) — see `CLAUDE.md` gotchas if
`npm install`/`vitest` fails with "Cannot find native binding". Vite prints
the actual port (defaults to `:5173`, picks another if that's taken) and
binds `localhost`, which can resolve to the IPv6 loopback only — use
`http://localhost:<port>`, not `127.0.0.1`, if a direct request seems to
hang. It talks to the API at `VITE_API_BASE_URL` (default
`http://127.0.0.1:8000`) — override in `web/.env.local` (gitignored) if
your API is elsewhere. Log in with a user created via `sessionkit add`
above; there is no signup screen.

## Running tests

```
uv run pytest --cov=src/invoice_system --cov-report=term-missing
```

Run the full suite before calling a change finished, not just the file(s)
touched — see `testing-and-ci.md` for layout and fixtures. Coverage floor is
90% (`pyproject.toml`).

```
uv run ruff check .      # lint
uv run ruff format .     # format - CI only checks (--check), doesn't fix
```

```
cd web && npm test
cd web && npm run lint   # oxlint
```

## Environment

- `INVOICE_SYSTEM_DB` — path to the domain SQLite file used by the API
  (`api/app.py` lifespan). The CLI takes the same thing as the `--db` flag
  instead.
- `INVOICE_SYSTEM_AUTH_DB` — path to sessionkit's SQLite file used by the
  API (default `auth.db`). The `sessionkit` CLI takes the same thing as its
  own `--db` flag or `$SESSIONKIT_DB` instead.
- `INVOICE_SYSTEM_CORS_ORIGINS` — comma-separated allowed origins for the
  API's CORS policy (default `*` — see `CLAUDE.md`).
- `VITE_API_BASE_URL` — the web client's API base URL (default
  `http://127.0.0.1:8000`), read at build/dev-server time.
