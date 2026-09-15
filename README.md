# Invoice System

A freelancer/small-business billing tool: Account (the business you invoice)
→ Quote → Invoice, where a quote converts into an invoice rather than the
two being created independently. Both are exportable as PDFs.

**Status: backend done, no web client yet.** Python backend (SQLite storage,
FastAPI behind login via [sessionkit](https://github.com/atownsend247/bb-py-sessionkit),
plus a mirrored CLI) is implemented and tested — see `docs/development.md`
to run it and `docs/roadmap.md` for what's next.

## Docs

- [`CLAUDE.md`](CLAUDE.md) — conventions and architecture rules for anyone
  (human or agent) working in this repo.
- [`docs/development.md`](docs/development.md) — how to run it.
- [`docs/architecture.md`](docs/architecture.md) — layering, storage,
  dependency injection, error handling.
- [`docs/data-model.md`](docs/data-model.md) — entities and relationships.
- [`docs/api.md`](docs/api.md) — endpoint reference.
- [`docs/roadmap.md`](docs/roadmap.md) — phase status.
- [`docs/testing-and-ci.md`](docs/testing-and-ci.md) — test layout, fixtures,
  coverage, CI shape.
- [`docs/extracting-reusable-packages.md`](docs/extracting-reusable-packages.md)
  — playbook for carving a cross-cutting concern into its own package.
