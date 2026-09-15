# Architecture

The shape, independent of language/framework. `invoice-system` implements
this as Python 3.13 + FastAPI + Pydantic + SQLite + a React/Vite SPA, but
nothing here is specific to that stack — swap layers as needed and note the
swap in your own copy of this file.

## Layers

```
  web client  ─┐
               ├─▶  API layer  ─┐
  CLI          ─┘               ├─▶  core domain service  ─▶  Repository (Protocol)  ─▶  storage
                                 │
              cross-cutting     ─┘   (its own service + its own Protocol; see below)
              concern (e.g. auth)
```

- **Core domain service** — one class/module per bounded concern
  (`InvoiceService`-shaped: a stateless-ish class with an injected
  repository, clock, and any other collaborators). Every domain rule,
  validation, and aggregation lives here and nowhere else. It raises typed
  exceptions (a small hierarchy under one base) instead of knowing about HTTP
  status codes or CLI exit codes.
- **`Repository` Protocol** — the storage contract the core service depends
  on. Structural typing (Python `Protocol`, an interface in a typed language,
  a Go interface) rather than a base class to subclass — any object with the
  right methods satisfies it, which is what makes a fake/in-memory
  implementation trivial for tests. The concrete implementation (SQLite,
  Postgres, whatever) does persistence only: no business rules, no decisions
  beyond "insert this row" / "run this query".
- **API layer** — thin. A route handler unpacks the request, calls exactly
  one core-service method, and serialises the result. It does not itself
  validate business rules (that's the service's job — the service raising
  `SomethingNotFound` and the route mapping that exception type to `404` is
  the whole of the route's "logic"). One place maps exception types → status
  codes, applied consistently, not scattered `try/except` per route.
- **CLI layer** — thin in the same sense: it opens a service over the same
  storage, calls its methods, and formats output / maps exceptions to exit
  codes. It is not a second implementation of any rule the API layer already
  enforces.
- **Cross-cutting concerns that aren't the domain** (accounts and sessions
  is the running example) get their **own** service + their **own** narrower
  Protocol, over the *same* storage if convenient, rather than being folded
  into the domain service or duplicated per entry point. If it's generic
  enough that an unrelated project could use it unchanged, treat that as a
  design constraint from the start (no imports of anything domain-specific)
  even before you actually extract it — see
  `extracting-reusable-packages.md`.

## Dependency injection that actually gets used

Two things are worth injecting into *every* service, because skipping this is
the single most common cause of flaky or unwritable tests:

- **A clock** — `Callable[[], datetime]` (or equivalent), defaulting to the
  real clock, overridden by a fixed/steppable fake in tests. Every place the
  service would otherwise call "now" calls `self._clock()` instead.
- **Anything else ambient and non-deterministic** the service touches
  directly — a password hasher, a random token generator, an external API
  client. Same pattern: a Protocol/interface, a real default, a fast
  deterministic fake for tests.

## Error handling

- One small exception hierarchy per concern, rooted at a base (`AppError`,
  `AuthError`, ...). Subclasses carry meaning (`NotFound`, `Duplicate`,
  `ValidationFailed`, ...), not formatting — the message is for a human, the
  *type* is what a caller branches on.
- Exactly one place per entry point maps exception type → response shape
  (HTTP status + body for a web API; exit code + stderr message for a CLI).
  Walk the exception's MRO / type hierarchy so a subclass falls back to its
  parent's mapping if it isn't listed explicitly.
- A service never imports its caller's response types (no `HTTPException` in
  the domain layer). The mapping lives entirely in the entry-point layer.

## Storage & migrations

- One frozen baseline schema (applied with `CREATE TABLE IF NOT EXISTS` so
  it's harmless against an existing database) plus a strictly forward-only,
  numbered list of migrations. A migration runner applies whatever's pending
  above the database's recorded version and nothing else. Never edit a
  migration that's shipped; append a new one.
- If a single connection/handle is shared across threads or async workers,
  put the locking **inside** the repository implementation (one lock per
  connection, every method acquires it) rather than trusting every caller to
  remember.
- Prefer storing values as their most precision-safe representation (decimal
  as string, not float) and validate/reject the unsafe form at the boundary
  rather than silently coercing it.

## Web client (if there is one)

- Exactly one module owns every HTTP call to the backend. Components /
  pages never call `fetch` directly — they call a typed function from that
  module, so the wire format only has to be gotten right in one place.
- A small shared hook wraps "call an async function, track loading/error/data"
  so every page doesn't reinvent it.
- Keep precision-sensitive values (money, etc.) as strings client-side too —
  don't parse them into a float just to render them; only parse at the point
  you need to do arithmetic, and do that arithmetic with a decimal library.
