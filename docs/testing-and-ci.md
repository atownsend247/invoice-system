# Testing and CI

## Test layout

- `tests/` mirrors `src/<package>/` 1:1 — a `tests/core/`, `tests/api/`,
  `tests/storage/`, etc. for every subpackage, plus a root `conftest.py`
  holding fixtures shared across all of them. When the source gets restructured
  into subpackages, move the tests to match in the same change — a source tree
  and a test tree that have drifted apart are a constant "which file was that
  in again" tax.
- Shared fixtures in the root `conftest.py`: a `FakeClock` (settable /
  steppable `now()`), a `FakeHasher` or equivalent fast fake for any other
  injected ambient dependency, an in-memory storage fixture (`:memory:`
  SQLite, or equivalent), and — for a web API — both an authenticated and an
  unauthenticated test client, so "does this route require auth" is a
  one-line assertion instead of hand-rolled setup per test.
- Prefer a fake implementation of a Protocol over mocking library internals.
  The Protocol boundary exists specifically so tests can swap in something
  real-but-fast instead of stubbing methods on the concrete class.
- Run the **full** suite before calling a change finished, not just the
  file(s) touched — cheap regression insurance, especially across the
  service/API/CLI boundary where one shared rule can silently diverge.

## Web client tests

`web/` has its own test runner (Vitest) for unit/integration tests, plus a
Playwright end-to-end suite (`web/e2e/`) that drives a real browser against
a throwaway instance of the actual backend + frontend (own SQLite files, own
ports, torn down after) — not mocked, not the same thing as the Vitest
integration test that mocks `api.ts`. See `web/README.md` for commands; it's
excluded from the Python coverage numbers below entirely (separate
toolchain, separate CI job — see CI shape).

## Coverage

- Enforce a floor in CI (e.g. `fail_under = 90` for `coverage.py`), applied to
  first-party source only — exclude thin launchers (`__main__.py`, a one-line
  ASGI app factory call) explicitly rather than writing a test whose only job
  is to hit that line.
- When a new standalone package is added to the repo (see
  `extracting-reusable-packages.md`), add it to the coverage `source` list and
  its own `tests/<package>/` directory immediately — it's easy to forget and
  end up with a silently uncovered package inflating the aggregate number.

## CI shape

- Split jobs by concern (backend / frontend / anything else that has its own
  toolchain) so a frontend-only change doesn't wait on a Python install, and
  vice versa.
- Publish results where they're easy to see without downloading an artifact:
  a coverage table in the job summary, a PR comment with the diff, a "Test
  Results" check run from the JUnit/equivalent output.
- Cancel superseded runs for the same branch (`concurrency` +
  `cancel-in-progress: true`) — a few seconds of setup cost, saves real minutes
  on a repo that gets pushed to often.

## Generated, committed artifacts

Pattern for anything derived from code but kept in git for review-diffability
(an OpenAPI schema dump, a generated changelog, a lockfile someone might hand-
edit by mistake):

1. One command regenerates it from source, no running server / external state
   required (e.g. build the app in-process against an in-memory database and
   dump its schema, rather than requiring a live server to scrape it from).
2. CI re-runs that command and does a `diff --exit-code` against the committed
   copy — fails loudly with the regeneration command in the error message if
   it's stale. This is the default: **verify and fail**, don't have CI push a
   fix back automatically, particularly if the maintainer pushes straight to
   the trunk branch — a bot commit landing behind their back means their next
   push needs an unexpected pull first, for a net loss.
3. Optional: a local pre-commit hook (opt-in via
   `git config core.hooksPath .githooks`, not forced on every clone) that
   regenerates and stages the file automatically when a commit touches the
   relevant source paths, so the CI failure in (2) becomes rare instead of the
   normal path.
4. If you want it published somewhere (a docs site, an API reference page),
   build that as a separate step from a fresh checkout of the *verified*
   artifact, and gate actual publishing (e.g. to a hosted pages site) behind
   whatever's true of the repo (public vs. private, who's allowed to deploy) -
   don't assume publishing is always wanted just because building is.
