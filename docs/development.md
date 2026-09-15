# Development

**Status: pre-code.** Nothing below is runnable yet — this is the intended
setup for the stack chosen in `architecture.md` (Python 3.13 + FastAPI +
SQLite, `uv` for dependency management; React/Vite for the SPA in `web/`).
Correct this doc the moment real tooling lands and these commands diverge
from it.

## First run

```
uv sync                          # install backend deps from pyproject.toml
uv run invoice-system-cli init-db  # create the SQLite file, apply migrations
uv run uvicorn invoice_system.api.app:app --reload  # serve the API
```

```
cd web && npm install && npm run dev  # serve the SPA
```

No seed data by default — the first account is created via the CLI or a
signup route (TBD in `api.md` once auth is scaffolded).

## Running tests

```
uv run pytest --cov=src/invoice_system --cov-report=term-missing
```

Run the full suite before calling a change finished, not just the file(s)
touched — see `testing-and-ci.md` for layout and fixtures.

```
cd web && npm test
```

## Environment

No required environment variables yet. `DATABASE_URL`/equivalent will be
added here once storage config becomes more than a single local SQLite file.
