# Development

## First run

```
uv sync
uv run invoice-system-cli init-db
```

Creates `storage/db/invoice_system.db`, applies migrations, and (by
default) seeds a year of demo data — accounts, quotes/invoices in a mix of
statuses, and a demo login (`demo@example.test` / `demo-password-123`) in
`storage/db/auth.db`. Log in with that straight away; there's nothing else
to set up. Safe to re-run — seeding is a no-op once the demo user exists.
Everything persistent this app writes (both databases, uploaded
expense-attachment PDFs, and — reserved for future use — logs) lives under
that one `storage/` directory by default — see "Where persistent data
lives" below.

For an empty database instead (e.g. before deploying somewhere real), pass
`--no-demo` and create your own login:

```
uv run invoice-system-cli init-db --no-demo
uv run sessionkit add you@example.com --db storage/db/auth.db   # prompts for a password
```

The domain data (accounts/quotes/invoices) and login accounts live in two
separate SQLite files — see `CLAUDE.md`. No signup route; manage login
accounts with the `sessionkit` CLI (`add`, `list`, `passwd`, `delete`,
`2fa-disable` — `uv run sessionkit --help`), not through this app.

To wipe accumulated local test data and start over, `uv run
invoice-system-cli init-db --reset` deletes the domain database and every
uploaded expense-attachment file, then reinitialises (reseeding demo data
by default, same as a first run). It leaves login accounts untouched, so
you don't need to recreate your own login (or the demo one) afterward.
This is irreversible — it prompts for confirmation unless `--yes`/`-y` is
also passed.

## Where persistent data lives

Every kind of persistent data this app writes lives under one base
directory (`storage/` by default, in the working directory) — see
`src/invoice_system/paths.py`'s `StoragePaths`:

```
storage/
├── db/
│   ├── invoice_system.db   # domain data - accounts, quotes, invoices, expenses
│   └── auth.db             # sessionkit's login/session data
├── attachments/            # uploaded expense-attachment PDFs (see docs/api.md)
└── logs/                   # reserved for future use - nothing writes here yet
```

`--storage-dir PATH` (CLI, before the subcommand) / `INVOICE_SYSTEM_STORAGE_DIR`
(API) move the whole thing elsewhere at once. `--db`/`--attachments-dir`
(CLI) and `INVOICE_SYSTEM_DB`/`INVOICE_SYSTEM_AUTH_DB`/
`INVOICE_SYSTEM_ATTACHMENTS_DIR` (API) still exist underneath that as
individual overrides — for the rare case a specific file/directory needs
to live somewhere else entirely (e.g. attachments on different storage
than the databases) — and always win over the storage-dir-derived default
when set. `storage/` is gitignored; back it up as a unit (see
`docs/deployment.md`'s "Where persistent data lives" for the deployed
equivalent).

## Serve the API

```
uv run uvicorn invoice_system.api.app:app --reload
```

Defaults to `storage/db/invoice_system.db` / `storage/db/auth.db` in the
working directory (see "Where persistent data lives" below); override the
whole `storage/` location with `INVOICE_SYSTEM_STORAGE_DIR=/path/to/dir`,
or an individual file/directory with `INVOICE_SYSTEM_DB=/path/to/db.sqlite3`
/ `INVOICE_SYSTEM_AUTH_DB=/path/to/auth.sqlite3`. Interactive docs at
`http://127.0.0.1:8000/docs`. Every route except `/healthz` and
`POST /auth/login` needs `Authorization: Bearer <token>` — log in first:

```
curl -s -X POST http://127.0.0.1:8000/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email": "you@example.com", "password": "..."}'
# -> {"token": "...", "expires_at": "...", "user": {...}}
```

To reach the API from another device on the same network (a phone, another
computer) instead of just this machine, bind it to every interface:

```
uv run uvicorn invoice_system.api.app:app --reload --host 0.0.0.0
```

`CORSMiddleware` already allows every origin by default (see `CLAUDE.md`),
so nothing else needs to change on the API side for a browser on another
device to call it — but anyone else on the same network/wifi can reach it
too for as long as it's running, not just your own other devices. Only do
this on a network you trust. Combine with `npm run dev:lan` below so the
web client is reachable from other devices too.

## Use the CLI

Every `account`/`quote`/`invoice` command takes a **required** `--user-id`
(find it via `uv run sessionkit list`) — the CLI has no login session to
resolve "which organisation" from, so it resolves that from an explicit
user id instead (auto-creating that user's `Organisation` on first use, same
as the API does from a Bearer token — see `docs/data-model.md`'s
"Multi-tenancy"). Two different `--user-id`s see two entirely separate sets
of accounts/quotes/invoices.

Every id in this app (`--user-id` included) is a UUID4 string, not a small
sequential number — there's nothing to guess, but there's also nothing to
type from memory: an `account`/`quote`/`invoice` id only exists once a prior
command has printed it, so a real session copies it from that command's
output into the next one, exactly like the example below (each command
prints the id of whatever it just created — `Created account <id>: ...`,
`Created quote <id> (draft)`, `Converted quote <id> to invoice <id>` — see
`cli/main.py` for the exact wording):

```
uv run invoice-system-cli --help
uv run sessionkit list
# -> e9f1c2a0-...  you@example.com

uv run invoice-system-cli account create --user-id e9f1c2a0-... --business-name "Acme Co" \
    --email billing@acme.test --address-line1 "1 Main St" --town-or-city London \
    --postcode "SW1A 1AA"
# -> Created account 3b7d4e10-...: Acme Co

uv run invoice-system-cli account update 3b7d4e10-... --user-id e9f1c2a0-... \
    --business-name "Acme Co Ltd" --email billing@acme.test --address-line1 "1 Main St"

uv run invoice-system-cli quote create --user-id e9f1c2a0-... --account-id 3b7d4e10-...
# -> Created quote 6a2f88c4-... (draft)

uv run invoice-system-cli quote add-item 6a2f88c4-... --user-id e9f1c2a0-... \
    --description "Design work" --quantity 10 --unit-price 50.00 --tax-rate 0.20
uv run invoice-system-cli quote send 6a2f88c4-... --user-id e9f1c2a0-...
uv run invoice-system-cli quote pdf 6a2f88c4-... -o quote.pdf --user-id e9f1c2a0-...
uv run invoice-system-cli quote convert 6a2f88c4-... --user-id e9f1c2a0-...
# -> Converted quote 6a2f88c4-... to invoice 91d0aa77-...

uv run invoice-system-cli invoice send 91d0aa77-... --user-id e9f1c2a0-...
uv run invoice-system-cli invoice pay 91d0aa77-... --user-id e9f1c2a0-...
uv run invoice-system-cli invoice pdf 91d0aa77-... -o invoice.pdf --user-id e9f1c2a0-...

uv run invoice-system-cli expense create --user-id e9f1c2a0-... --account-id 3b7d4e10-...
# -> Created expense c4e91d02-... (EXP-0001) - the number is assigned
#    immediately, unlike "quote create" above: an expense has no draft
#    state to defer it past (see CLAUDE.md).

uv run invoice-system-cli expense add-item c4e91d02-... --user-id e9f1c2a0-... \
    --description "Domain renewal" --quantity 1 --unit-price 12.00 --tax-rate 0.20
uv run invoice-system-cli expense list --user-id e9f1c2a0-...
uv run invoice-system-cli expense monthly-totals --user-id e9f1c2a0-...
uv run invoice-system-cli expense pdf c4e91d02-... -o expense.pdf --user-id e9f1c2a0-...

uv run invoice-system-cli expense attachment add c4e91d02-... --user-id e9f1c2a0-... \
    --file ./receipt.pdf
# -> Uploaded attachment 2255ee4c-... : receipt.pdf (48213 bytes)
uv run invoice-system-cli expense attachment list c4e91d02-... --user-id e9f1c2a0-...
uv run invoice-system-cli expense attachment download c4e91d02-... 2255ee4c-... \
    -o downloaded-receipt.pdf --user-id e9f1c2a0-...
uv run invoice-system-cli expense attachment delete c4e91d02-... 2255ee4c-... \
    --user-id e9f1c2a0-...

uv run invoice-system-cli stats --user-id e9f1c2a0-...
```

(`...`-truncated above purely for readability — a real id is a full UUID4,
e.g. `e9f1c2a0-4b3d-4e7a-9c1f-2d6b8a0e5f31`. See `docs/data-model.md`'s
"Opaque ids" for why every id in this app moved from a sequential integer
to a UUID4.)

`--tax-rate` (default `0`) is a fraction, not a percentage - `0.20` for 20%
VAT, `0.05` for 5%, valid range `[0, 1]`.

`--storage-dir PATH` (before the subcommand) points every command at a
different base storage directory (default `storage/` in the working
directory — see "Where persistent data lives" above); `--db PATH`/
`--attachments-dir PATH` (also before the subcommand) individually
override the domain database/attachments location within it. The
CLI is a local, trusted tool and is **not** behind login (unlike the API) —
see `CLAUDE.md`.

Your own business profile (shown as "From" on PDFs, drives the invoice due
date, and — via `--document-header`/`--document-footer` — gets inserted
into every quote/invoice PDF you generate, above the title and below the
totals table respectively) is managed with `settings`, keyed by an
explicit `--user-id` (find it via `uv run sessionkit list`) since the CLI
has no login session to resolve it from:

```
uv run invoice-system-cli settings set --user-id e9f1c2a0-... \
    --first-name Ada --last-name Lovelace \
    --business-name "Acme Consulting" --address-line1 "1 Main St" \
    --town-or-city London --postcode "SW1A 1AA" \
    --payment-terms-days 14 --currency GBP \
    --utr 1234567890 --vat-number GB123456789 \
    --bank-account-name "Acme Consulting Ltd" \
    --bank-sort-code "12-34-56" --bank-account-number 12345678 \
    --document-header "Acme Consulting" \
    --document-footer "Thank you for your business!"
uv run invoice-system-cli settings show --user-id e9f1c2a0-...
```

`currency` (default `GBP`) is the *reporting* currency the home dashboard's
monthly-totals chart sums in — independent of the `--currency` you pass to
`quote create` for an individual quote/invoice. `invoice monthly-totals`
resolves it from the profile the same way `invoice send`/`quote pdf` resolve
payment terms/the "From" party:

```
uv run invoice-system-cli invoice monthly-totals --user-id e9f1c2a0-...
```

`--user-id` on `invoice send`, `quote pdf`, and `invoice pdf` does double
duty: besides resolving the organisation (required, as above), it also pulls
in that user's payment terms / "From" details:

```
uv run invoice-system-cli invoice send 91d0aa77-... --user-id e9f1c2a0-...
uv run invoice-system-cli quote pdf 6a2f88c4-... -o quote.pdf --user-id e9f1c2a0-...
```

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
hang. It talks to the API at `VITE_API_BASE_URL` if set, otherwise a
default derived from whatever host the page itself was loaded from
(`defaultApiBaseUrl()` in `api.ts`) — `http://127.0.0.1:8000` when that's
`localhost`/`127.0.0.1`, or the same host on port 8000 otherwise. Override
with `VITE_API_BASE_URL` in `web/.env.local` (gitignored) if your API is
genuinely elsewhere (a different port, a different machine). Log in with
the demo user (`demo@example.test` / `demo-password-123`, if `init-db` ran
without `--no-demo`) or one created via `sessionkit add`; there is no
signup screen.

To reach the web client from another device on the same network, use
`npm run dev:lan` instead of `npm run dev` (it's the same `vite` command
with `--host` added, which binds every interface instead of just
`localhost` — Vite then prints both the `Local` and `Network` URLs to use),
with the backend also started with `--host 0.0.0.0` (see above). That's
it — you don't need to set `VITE_API_BASE_URL` yourself: loading the page
from `http://192.168.1.23:5173` makes it default to
`http://192.168.1.23:8000` for the API automatically, following whatever
host the page itself was loaded from. Same caveat as the API: anyone on
the network can reach it while it's running, so only do this somewhere you
trust.

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

- `INVOICE_SYSTEM_STORAGE_DIR` — base directory for all persistent data
  (default `storage/`) used by the API (`api/app.py` lifespan) — see
  "Where persistent data lives" above. The CLI takes the same thing as the
  `--storage-dir` flag instead. The three vars below still override an
  individual path/directory within it, same as `--db`/`--attachments-dir`
  do for the CLI.
- `INVOICE_SYSTEM_DB` — path to the domain SQLite file used by the API
  (`api/app.py` lifespan; defaults to `<storage-dir>/db/invoice_system.db`).
  The CLI takes the same thing as the `--db` flag instead.
- `INVOICE_SYSTEM_AUTH_DB` — path to sessionkit's SQLite file used by the
  API, and by `invoice-system-cli init-db`'s demo-data seeding (both
  default `<storage-dir>/db/auth.db`). The `sessionkit` CLI takes the same
  thing as its own `--db` flag or `$SESSIONKIT_DB` instead.
- `INVOICE_SYSTEM_ATTACHMENTS_DIR` — directory uploaded expense-attachment
  PDFs are stored in (default `<storage-dir>/attachments`). The CLI takes
  the same thing as the `--attachments-dir` flag instead.
- `INVOICE_SYSTEM_CORS_ORIGINS` — comma-separated allowed origins for the
  API's CORS policy (default `*` — see `CLAUDE.md`).
- `VITE_API_BASE_URL` — the web client's API base URL, read at
  build/dev-server time. Optional — unset, it defaults to whatever host the
  page was loaded from, on port 8000 (`defaultApiBaseUrl()` in `api.ts`;
  `127.0.0.1` specifically for `localhost`/`127.0.0.1`, so `npm run dev:lan`
  works without this needing to be set at all).
