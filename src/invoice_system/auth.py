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


def build_auth_service(db_path: str | Path = DEFAULT_AUTH_DB_PATH) -> AuthService:
    # check_same_thread=False: the API layer runs sync handlers in a worker
    # thread pool, not the thread that opens this connection at startup -
    # same reason SqliteRepository uses it (see storage/sqlite_repository.py).
    return AuthService(SqliteAuthStore.open(str(db_path), check_same_thread=False))
