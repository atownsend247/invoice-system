# Development

## First run

```
uv sync
uv run invoice-system-cli init-db   # creates invoice_system.db, applies migrations
```

No seed data by default — create the first account via the CLI or API (see
below).

## Serve the API

```
uv run uvicorn invoice_system.api.app:app --reload
```

Defaults to `invoice_system.db` in the working directory; override with
`INVOICE_SYSTEM_DB=/path/to/db.sqlite3`. Interactive docs at
`http://127.0.0.1:8000/docs`.

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
SQLite file; default is `invoice_system.db` in the working directory.

## Running tests

```
uv run pytest --cov=src/invoice_system --cov-report=term-missing
```

Run the full suite before calling a change finished, not just the file(s)
touched — see `testing-and-ci.md` for layout and fixtures. Coverage floor is
90% (`pyproject.toml`).

No `web/` yet — see `docs/roadmap.md`.

## Environment

- `INVOICE_SYSTEM_DB` — path to the SQLite file used by the API (`api/app.py`
  lifespan). The CLI takes the same thing as the `--db` flag instead.
