# Extracting a reusable package

A playbook for the moment a cross-cutting concern (accounts/sessions/auth was
the running example) turns out to be generic enough that a different project
could use it unchanged. Worth doing deliberately rather than after the fact —
retrofitting isolation onto code that's grown tangled with the domain is far
more work than keeping it isolated from the start.

## Signs it's a good candidate

- It doesn't reference any domain noun (no "invoice", "client", "line item" —
  or whatever your domain's equivalents are — anywhere in its imports or its
  language).
- Its dependencies are generic (a hashing library, a TOTP library) not
  anything app-specific.
- You can describe what it does in one sentence without mentioning the app it
  currently lives in.

## The extraction

1. **New package, same repo, own top-level directory under `src/`** — not a
   subpackage of the app. Give it its own `errors.py` with its own exception
   base (do **not** have its errors inherit the host app's base exception
   type — the two concerns shouldn't be typed as the same thing, even though
   it's tempting for a one-line `except` clause to keep working unchanged).
2. **Narrow storage Protocol** just for what this package needs (not the
   app's whole `Repository`). The host app's concrete storage class then
   satisfies *both* Protocols structurally — no inheritance change required,
   because Python (and similar structurally-typed systems) doesn't need it.
   If your language needs explicit interface declaration, declare both.
3. **Ship a bundled reference storage implementation** (e.g.
   `SqliteAuthStore` alongside the app's own `SqliteRepository`) for other
   adopters who don't already have a database — but don't rewire the host
   app onto it. The host app's existing, already-tested storage class stays
   exactly as it was; it just now also satisfies the new package's Protocol.
4. **Don't touch the host app's schema/migrations** as part of the
   extraction. If the new package's tables already exist in the host's
   database (created by the host's own migrations), leave that ownership
   where it is — repossessing schema ownership mid-extraction is a separate,
   riskier piece of work with its own migration-compatibility story, and
   isn't required to get the reuse benefit.
5. **Re-export shims at the old import paths** in the host app (e.g. the old
   `app.auth` module becomes two lines: `from newpackage import AuthService`)
   so nothing else in the host app has to change its imports. Update the
   handful of places that need to know about the new package's *specific*
   error types explicitly (an error-to-status-code map is the usual one);
   everything importing the old re-exported names keeps working.
6. **Own tests, mirroring the new package**, not folded into the host app's
   test tree — `tests/<newpackage>/`. Test the new package against its own
   bundled storage implementation; keep (or add) a small "does the host's
   storage class still satisfy the new Protocol" conformance test in the host
   app's test tree so a future refactor of either side can't silently break
   the contract.
7. **Its own doc** (`docs/<newpackage>.md`): what it does, its public surface,
   how to bring your own storage, and — importantly — the literal steps to
   lift it into a fully separate repository/package later (add a real
   `pyproject.toml`/`package.json`/etc. with its actual dependencies declared,
   remove it from the host's build config, depend on the published version
   instead). Write this even if you have no plan to publish it soon; it's
   what proves the isolation is real, and it's cheap to write while the
   boundaries are fresh in your head.
8. **Ship in the same build artifact for now.** A second top-level package in
   the same wheel/bundle is nearly free and gets you 95% of the value
   (genuine isolation, a clean extraction path) without the overhead of
   managing a second published package, a second version number, and a second
   release process before you have a second consumer that needs it.
