"""Where this app's persistent data lives on disk - one base directory
(`INVOICE_SYSTEM_STORAGE_DIR` / CLI `--storage-dir`, default `storage/`),
not scattered relative paths in the working directory. See CLAUDE.md.

Not to be confused with the `storage/` *package* (`schema.py`,
`sqlite_repository.py`) - that's the SQL persistence layer's code; this
module is about the base *directory* every kind of persistent file (SQLite
databases today, uploaded expense-attachment PDFs, and a `logs/`
subdirectory reserved for future logging output) is grouped under on disk.

This is a CLI/API entry-point concern, not a domain one:
`core.py`/`factory.py`/`auth.py` still just take whatever concrete path
they're given (a plain `db_path`/`attachments_dir` string, same as
always) - only `cli/main.py` and `api/app.py` know this base-directory
convention exists, resolving concrete paths from it before calling into
`build_application`/`build_auth`.
"""

from pathlib import Path

DEFAULT_STORAGE_DIR = "storage"


class StoragePaths:
    """Derives every concrete persistent-data path from one base
    directory. `INVOICE_SYSTEM_DB`/`INVOICE_SYSTEM_AUTH_DB`/
    `INVOICE_SYSTEM_ATTACHMENTS_DIR` (API) and `--db`/`--attachments-dir`
    (CLI) still exist as explicit per-path overrides - see api/app.py's
    `lifespan` and cli/main.py's `cli` group - so this only ever supplies
    a *default*, never forces every file under the same base."""

    def __init__(self, base_dir: str | Path = DEFAULT_STORAGE_DIR) -> None:
        self.base_dir = Path(base_dir)

    @property
    def db_dir(self) -> Path:
        return self.base_dir / "db"

    @property
    def domain_db_path(self) -> Path:
        return self.db_dir / "invoice_system.db"

    @property
    def auth_db_path(self) -> Path:
        return self.db_dir / "auth.db"

    @property
    def attachments_dir(self) -> Path:
        return self.base_dir / "attachments"

    @property
    def logs_dir(self) -> Path:
        # Reserved for future logging output - nothing writes here yet;
        # kept here so the on-disk layout is already in place once
        # something does, rather than bolting a fourth base path on later.
        return self.base_dir / "logs"

    def ensure_db_dir(self) -> None:
        """Unlike `AttachmentStore.save()`, which creates its own
        directory lazily on first upload, both SQLite files' parent
        directory has to exist *before* `sqlite3.connect()`/
        `SqliteAuthStore.open()` will create the file itself - so this
        needs calling eagerly, once, before either database is opened."""
        self.db_dir.mkdir(parents=True, exist_ok=True)
