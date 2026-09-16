"""Wiring for sessionkit, the login/session cross-cutting concern.

Deliberately separate from `factory.py`: `AuthService` has its own storage
(a dedicated SQLite file, not `invoice_system.db`) and its own lifecycle.
`core.py` never imports this module - see the architecture rules in
CLAUDE.md. Users are managed with the `sessionkit` CLI (bundled with the
dependency), not through this app - see docs/development.md.
"""

from pathlib import Path

from sessionkit import AuthService, SqliteAuthStore

DEFAULT_AUTH_DB_PATH = "auth.db"


class Auth:
    """Bundles the service with the store, since `AuthService` never closes
    its store itself (sessionkit's own convention - see its CLAUDE.md)."""

    def __init__(self, service: AuthService, store: SqliteAuthStore) -> None:
        self.service = service
        self._store = store

    def close(self) -> None:
        self._store.close()

    def __enter__(self) -> "Auth":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def build_auth(db_path: str | Path = DEFAULT_AUTH_DB_PATH) -> Auth:
    # check_same_thread=False is SqliteAuthStore's default as of sessionkit
    # v0.1.2+ (every method is serialised on its own lock) - relied on here
    # rather than passed explicitly, since the API layer runs sync handlers
    # in a worker thread pool, not the thread that opens this connection.
    store = SqliteAuthStore.open(str(db_path))
    return Auth(AuthService(store), store)
