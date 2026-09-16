from pathlib import Path

DEFAULT_ATTACHMENTS_DIR = "attachments"


class AttachmentStore:
    """Filesystem storage for uploaded expense-attachment bytes - a
    cross-cutting concern, not domain logic (same reasoning as `pdf.py` -
    see CLAUDE.md's architecture rules), so `core.py`'s `ExpenseService`
    depends on this through plain constructor injection rather than
    importing file I/O directly. Deliberately not a database BLOB: keeping
    uploaded bytes off the SQLite file (see `models.ExpenseAttachment`,
    which holds only metadata) means the database stays small and easy to
    back up/migrate regardless of how many or how large the uploaded
    receipts are - the tradeoff (a second thing to back up alongside the
    `.db` files) is accepted deliberately, not an oversight.

    Only ever keyed by an already-generated attachment id (a UUID4, see
    ids.py) - never a caller-supplied filename - so there is nothing here
    to sanitise for path-traversal safety; a UUID can't contain a path
    separator or a `..` segment in the first place."""

    def __init__(self, base_dir: str | Path) -> None:
        self._base_dir = Path(base_dir)

    def save(self, attachment_id: str, data: bytes) -> None:
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._path(attachment_id).write_bytes(data)

    def read(self, attachment_id: str) -> bytes:
        return self._path(attachment_id).read_bytes()

    def delete(self, attachment_id: str) -> None:
        self._path(attachment_id).unlink(missing_ok=True)

    def _path(self, attachment_id: str) -> Path:
        return self._base_dir / f"{attachment_id}.pdf"
