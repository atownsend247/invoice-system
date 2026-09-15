# Invoice System

A small business/freelancer billing tool: Clients → Invoices → Line items,
with invoices moving through `draft → sent → paid` (branching to `overdue`
or `void`) as payments are recorded.

**Status: pre-code.** This repo currently holds the project's `CLAUDE.md`
and reference docs only — see `docs/roadmap.md` for what's next.

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
